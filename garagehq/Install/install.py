#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import re
import requests
import io
import secrets
import time

# Force l'encodage UTF-8 pour stdin/stdout/stderr
if sys.stdin.encoding != 'utf-8':
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def check_dep(cmd):
    if shutil.which(cmd) is None:
        print(f"{cmd} est requis mais non trouvé.")
        sys.exit(1)

# Vérification des dépendances (dpkg retiré, non nécessaire pour Garage)
for cmd in ['wget', 'getent', 'id', 'chmod', 'chown', 'mv', 'mkdir', 'ip', 'awk', 'cut', 'head', 'journalctl']:
    check_dep(cmd)

# Vérification des droits root (compatible Linux uniquement)
if sys.platform != "win32" and os.geteuid() != 0:
    print("Ce script doit être exécuté en tant que root.", file=sys.stderr)
    sys.exit(1)


def get_latest_garage():
    """Récupère la dernière version stable de Garage via l'API Gitea de Deuxfleurs."""
    api_url = "https://git.deuxfleurs.fr/api/v1/repos/Deuxfleurs/garage/releases?limit=50&page=1"
    try:
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            print("Aucune release trouvée sur git.deuxfleurs.fr")
            sys.exit(1)

        # Filtre les pre-releases et drafts, puis trie par version sémantique
        stable_releases = [
            r for r in data
            if not r.get("prerelease", False)
            and not r.get("draft", False)
            and re.match(r'^v?\d+\.\d+\.\d+$', r["tag_name"])  # ex: v2.2.0 uniquement
        ]
        if not stable_releases:
            print("Aucune release stable trouvée.")
            sys.exit(1)

        # Tri par version sémantique (major, minor, patch)
        def semver_key(release):
            tag = release["tag_name"].lstrip("v")
            parts = tag.split(".")
            return tuple(int(x) for x in parts)

        latest = sorted(stable_releases, key=semver_key, reverse=True)[0]
        version = latest["tag_name"].lstrip("v")
        binary_url = (
            f"https://garagehq.deuxfleurs.fr/_releases/v{version}"
            f"/x86_64-unknown-linux-musl/garage"
        )
        print(f"Dernière version stable de Garage : v{version}")
        return binary_url, version
    except requests.RequestException as e:
        print(f"Échec de la récupération de la version Garage : {e}")
        sys.exit(1)
    except (KeyError, IndexError, ValueError) as e:
        print(f"Erreur de parsing de la réponse : {e}")
        sys.exit(1)


def is_valid_ipv4(ip):
    if not re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", ip):
        return False
    parts = [int(x) for x in ip.split('.')]
    return all(0 <= part <= 255 for part in parts)


def build_config(meta_repo, repo, address, rpc_secret, admin_token, version):
    """Génère le contenu du garage.toml selon la version majeure."""
    major = int(version.split('.')[0])

    # v1.x → replication_mode, v2.x+ → replication_factor
    if major >= 2:
        replication_line = 'replication_factor = 1'
    else:
        replication_line = 'replication_mode = "none"'

    return f"""metadata_dir = "{meta_repo}"
data_dir = "{repo}"

db_engine = "lmdb"

{replication_line}

rpc_bind_addr = "0.0.0.0:3901"
rpc_public_addr = "{address}:3901"
rpc_secret = "{rpc_secret}"

[s3_api]
s3_region = "garage"
api_bind_addr = "0.0.0.0:3900"
root_domain = ".s3.garage.localhost"

[s3_web]
bind_addr = "0.0.0.0:3902"
root_domain = ".web.garage.localhost"
index = "index.html"

[admin]
api_bind_addr = "0.0.0.0:3903"
admin_token = "{admin_token}"
"""


# --- Saisie des répertoires ---
repo = input("Entrez le chemin du repertoire de donnees Garage : ").strip()
if not os.path.isdir(repo):
    print(f"Le répertoire {repo} n'existe pas, création...")
    try:
        os.makedirs(repo)
    except Exception as e:
        print(f"Erreur lors de la création du répertoire : {e}")
        sys.exit(1)

meta_repo = input("Entrez le chemin du repertoire de metadonnees Garage : ").strip()
if not os.path.isdir(meta_repo):
    print(f"Le répertoire {meta_repo} n'existe pas, création...")
    try:
        os.makedirs(meta_repo)
    except Exception as e:
        print(f"Erreur lors de la création du répertoire : {e}")
        sys.exit(1)

# --- Utilisateur système ---
if subprocess.call(['getent', 'group', 'garage'], stdout=subprocess.DEVNULL) != 0:
    subprocess.run(['groupadd', '-r', 'garage'], check=True)
if subprocess.call(['id', 'garage'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
    subprocess.run(['useradd', '-r', '-g', 'garage', '-s', '/sbin/nologin', '-d', '/var/lib/garage', 'garage'], check=True)

subprocess.run(['chown', 'garage:garage', repo], check=True)
subprocess.run(['chown', 'garage:garage', meta_repo], check=True)

# --- Téléchargement du binaire ---
GARAGE_BIN = "/usr/local/bin/garage"
garage_url, garage_version = get_latest_garage()
print(f"Téléchargement de Garage v{garage_version}...")
if subprocess.call(['wget', '-qO', GARAGE_BIN, garage_url]) != 0:
    print("Échec du téléchargement de Garage.")
    sys.exit(1)
subprocess.run(['chmod', '+x', GARAGE_BIN], check=True)

# --- Détection de l'adresse IP ---
auto_ip = input("Detection automatique de l'adresse IP ? (o/n) : ").strip().lower()
if auto_ip == "n":
    while True:
        address = input("Quelle est l'IP de votre serveur ? : ").strip()
        if is_valid_ipv4(address):
            break
        print("Adresse IP invalide, veuillez réessayer.")
else:
    while True:
        try:
            address = subprocess.check_output(
                "ip -o -4 addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1",
                shell=True, text=True
            ).strip()
        except Exception:
            address = ""
        print(f"Adresse IP détectée automatiquement : {address}")
        valid = input("Validez-vous cette IP ? (o/n) : ").strip().lower()
        if valid == "o":
            if is_valid_ipv4(address):
                break
            print("IP detectee invalide, saisissez-la manuellement.")
        address = input("Saisissez l'adresse IP a utiliser : ").strip()
        if is_valid_ipv4(address):
            break
        print("Adresse IP invalide, veuillez réessayer.")

# --- Génération de la configuration ---
rpc_secret = secrets.token_hex(32)
admin_token = secrets.token_hex(32)
CONFIG_DIR = "/etc/garage"
CONFIG_FILE = f"{CONFIG_DIR}/garage.toml"
os.makedirs(CONFIG_DIR, exist_ok=True)

with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
    f.write(build_config(meta_repo, repo, address, rpc_secret, admin_token, garage_version))

subprocess.run(['chmod', '640', CONFIG_FILE], check=True)
subprocess.run(['chown', 'root:garage', CONFIG_FILE], check=True)
print(f"Configuration écrite dans {CONFIG_FILE}")

# --- Service systemd ---
SERVICE_FILE = "/etc/systemd/system/garage.service"
service_content = f"""[Unit]
Description=Garage S3-compatible object store
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=garage
Group=garage
ExecStart={GARAGE_BIN} -c {CONFIG_FILE} server
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
"""
with open(SERVICE_FILE, 'w', encoding='utf-8') as f:
    f.write(service_content)

subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'enable', 'garage'], check=True)
subprocess.run(['systemctl', 'start', 'garage'], check=True)
print("Service Garage démarré.")

time.sleep(3)

# --- Statut et layout ---
print("\n--- Statut du nœud Garage ---")
subprocess.call([GARAGE_BIN, '-c', CONFIG_FILE, 'status'])

print("\n--- Layout du cluster ---")
try:
    node_id_output = subprocess.check_output(
        [GARAGE_BIN, '-c', CONFIG_FILE, 'node', 'id'],
        text=True, stderr=subprocess.DEVNULL
    ).strip()
    short_node_id = node_id_output.split('@')[0][:8] if '@' in node_id_output else node_id_output[:8]
    print(f"Node ID : {node_id_output}")

    zone = input("\nNom de la zone/datacenter (ex: dc1) : ").strip() or "dc1"
    capacity = input("Capacite en Go (ex: 100) : ").strip() or "100"
    subprocess.run([
        GARAGE_BIN, '-c', CONFIG_FILE,
        'layout', 'assign', '-z', zone, '-c', f'{capacity}G', short_node_id
    ], check=True)
    subprocess.run([GARAGE_BIN, '-c', CONFIG_FILE, 'layout', 'apply', '--version', '1'], check=True)
    print("Layout appliqué.")
except Exception as e:
    print(f"Attention : configuration manuelle du layout requise : {e}")

# --- Clé d'accès S3 ---
print("\n--- Création d'une clé d'accès S3 ---")
key_name = input("Nom de la cle d'acces (ex: admin-key) : ").strip() or "admin-key"
ak, sk = "(à créer manuellement)", "(à créer manuellement)"
try:
    key_output = subprocess.check_output(
        [GARAGE_BIN, '-c', CONFIG_FILE, 'key', 'create', key_name],
        text=True
    )
    print(key_output)
    access_key = re.search(r'Key ID:\s+(\S+)', key_output)
    secret_key = re.search(r'Secret key:\s+(\S+)', key_output)
    if access_key and secret_key:
        ak = access_key.group(1)
        sk = secret_key.group(1)
    else:
        ak, sk = "(voir ci-dessus)", "(voir ci-dessus)"
except Exception as e:
    print(f"Erreur lors de la création de la clé : {e}")

# --- Installation de garage-webui ---
def get_latest_garage_webui():
    """Récupère la dernière version de garage-webui via l'API GitHub."""
    api_url = "https://api.github.com/repos/khairul169/garage-webui/releases/latest"
    try:
        response = requests.get(api_url, headers={"Accept": "application/vnd.github+json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        version = data["tag_name"].lstrip("v")
        # Cherche le bon asset linux-amd64
        for asset in data.get("assets", []):
            if "linux-amd64" in asset["name"]:
                return asset["browser_download_url"], version
        # Fallback si nom d'asset non trouvé
        return (
            f"https://github.com/khairul169/garage-webui/releases/download/"
            f"{data['tag_name']}/garage-webui-v{version}-linux-amd64"
        ), version
    except Exception as e:
        print(f"Avertissement : impossible de récupérer garage-webui automatiquement : {e}")
        return None, None

print("\n--- Installation de garage-webui ---")
install_webui = input("Installer l'interface web garage-webui ? (o/n) : ").strip().lower()
webui_installed = False
webui_user = ""
if install_webui == "o":
    WEBUI_BIN = "/usr/local/bin/garage-webui"
    WEBUI_ENV = "/etc/garage/webui.env"
    webui_url, webui_version = get_latest_garage_webui()
    if webui_url:
        print(f"Téléchargement de garage-webui v{webui_version}...")
        if subprocess.call(['wget', '-qO', WEBUI_BIN, webui_url]) == 0:
            subprocess.run(['chmod', '+x', WEBUI_BIN], check=True)

            # --- Authentification ---
            auth_line = ""
            enable_auth = input("Activer l'authentification sur le webui ? (o/n) : ").strip().lower()
            if enable_auth == "o":
                if shutil.which('htpasswd') is None:
                    print("Installation de apache2-utils pour htpasswd...")
                    subprocess.run(['apt', 'install', '-y', 'apache2-utils'],
                                   stdout=subprocess.DEVNULL, check=True)
                webui_user = input("Nom d'utilisateur webui : ").strip() or "admin"
                import getpass
                while True:
                    webui_pass = getpass.getpass("Mot de passe webui : ")
                    webui_pass2 = getpass.getpass("Confirmez le mot de passe : ")
                    if webui_pass == webui_pass2:
                        break
                    print("Les mots de passe ne correspondent pas.")
                try:
                    hash_output = subprocess.check_output(
                        ['htpasswd', '-bnBC', '10', webui_user, webui_pass],
                        text=True
                    ).strip()
                    auth_line = f"AUTH_USER_PASS={hash_output}"
                    print("Hash d'authentification généré.")
                except Exception as e:
                    print(f"Erreur lors de la génération du hash : {e}")
                    auth_line = ""

            # --- Fichier d'environnement ---
            env_content = f"""PORT=3909
CONFIG_PATH={CONFIG_FILE}
API_BASE_URL=http://127.0.0.1:3903
"""
            if auth_line:
                env_content += f"{auth_line}\n"

            with open(WEBUI_ENV, 'w', encoding='utf-8') as f:
                f.write(env_content)
            subprocess.run(['chmod', '640', WEBUI_ENV], check=True)
            subprocess.run(['chown', 'root:garage', WEBUI_ENV], check=True)

            # --- Service systemd ---
            WEBUI_SERVICE = "/etc/systemd/system/garage-webui.service"
            webui_service_content = f"""[Unit]
Description=Garage Web UI
After=garage.service
Requires=garage.service

[Service]
EnvironmentFile={WEBUI_ENV}
ExecStart={WEBUI_BIN}
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""
            with open(WEBUI_SERVICE, 'w', encoding='utf-8') as f:
                f.write(webui_service_content)
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', 'garage-webui'], check=True)
            subprocess.run(['systemctl', 'start', 'garage-webui'], check=True)
            print(f"garage-webui v{webui_version} installe et demarre.")
            webui_installed = True
        else:
            print("Echec du telechargement de garage-webui. A installer manuellement.")
    else:
        print("Impossible de recuperer garage-webui. A installer manuellement.")

# --- Résumé ---
print("\n" + "="*60)
print("Installation de Garage terminée !")
print("="*60)
print(f"  Version        : v{garage_version}")
print(f"  Config         : {CONFIG_FILE}")
print(f"  Données        : {repo}")
print(f"  Métadonnées    : {meta_repo}")
print(f"  RPC Secret     : {rpc_secret}")
print(f"  Admin Token    : {admin_token}")
print(f"  Access Key ID  : {ak}")
print(f"  Secret Key     : {sk}")
print(f"\n  API S3         : http://{address}:3900")
print(f"  Web statique   : http://{address}:3902")
print(f"  Admin API      : http://{address}:3903")
if webui_installed:
    print(f"  Interface Web  : http://{address}:3909")
    if webui_user:
        print(f"  WebUI User     : {webui_user}")
    print(f"  WebUI Token    : {admin_token}")
print("\nPour voir les logs :")
print("  journalctl -xeu garage -n 20")
if webui_installed:
    print("  journalctl -xeu garage-webui -n 20")
    print(f"\nConnexion garage-webui :")
    print(f"  URL   : http://{address}:3909")
    if webui_user:
        print(f"  Login : {webui_user} / (mot de passe choisi)")
    print(f"  Token : {admin_token}")
    print(f"  (coller le token dans le champ 'Admin Token' de l'interface)")
print("\nPour créer un bucket :")
print(f"  garage -c {CONFIG_FILE} bucket create mon-bucket")
print(f"  garage -c {CONFIG_FILE} bucket allow --read --write --key {key_name} mon-bucket")