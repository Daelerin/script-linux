#!/usr/bin/env python3
import os
import sys
import subprocess
import getpass
import shutil
import re
import requests

def check_dep(cmd):
    if shutil.which(cmd) is None:
        print(f"{cmd} est requis mais non trouvé.")
        sys.exit(1)

# Vérification des dépendances
for cmd in ['wget', 'dpkg', 'getent', 'id', 'chmod', 'chown', 'mv', 'mkdir', 'ip', 'awk', 'cut', 'head', 'journalctl']:
    check_dep(cmd)

# Vérification des droits root (Linux/Unix uniquement)
if hasattr(os, "geteuid") and os.geteuid() != 0:
    print("Ce script doit être exécuté en tant que root.", file=sys.stderr)
    sys.exit(1)

# Fonction pour récupérer l'URL du dernier .deb MinIO
def get_latest_minio_deb():
    archive_url = "https://dl.min.io/server/minio/release/linux-amd64/archive/"
    try:
        response = requests.get(archive_url)
        response.raise_for_status()
        deb_files = re.findall(r'href="(minio_\d+\.0\.0_amd64\.deb)"', response.text)
        if not deb_files:
            print("Aucun fichier .deb trouvé sur le site de MinIO.")
            sys.exit(1)
        latest_deb = sorted(
            deb_files,
            key=lambda x: int(re.search(r'minio_(\d+)\.0\.0_amd64\.deb', x).group(1)),
            reverse=True
        )[0]
        return f"{archive_url}{latest_deb}", latest_deb
    except requests.RequestException as e:
        print(f"Échec de la récupération des versions : {e}")
        sys.exit(1)

# Saisie du chemin du volume
repo = input("Entrez le chemin du volume : ").strip()

# Création du répertoire si besoin
if not os.path.isdir(repo):
    print(f"Le répertoire {repo} n'existe pas, création...")
    try:
        os.makedirs(repo)
    except Exception as e:
        print(f"Erreur lors de la création du répertoire: {e}")
        sys.exit(1)

# Création du groupe et de l'utilisateur si besoin
if subprocess.call(['getent', 'group', 'minio-user'], stdout=subprocess.DEVNULL) != 0:
    subprocess.run(['groupadd', '-r', 'minio-user'], check=True)
if subprocess.call(['id', 'minio-user'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
    subprocess.run(['useradd', '-r', '-g', 'minio-user', '-s', '/sbin/nologin', 'minio-user'], check=True)
subprocess.run(['chown', 'minio-user:minio-user', repo], check=True)

# Téléchargement et installation du dernier paquet MinIO
MINIO_DEB = "/tmp/minio.deb"
minio_url, minio_filename = get_latest_minio_deb()
print(f"Téléchargement de la dernière version : {minio_url}")
if subprocess.call(['wget', '-qO', MINIO_DEB, minio_url]) != 0:
    print("Échec du téléchargement de MinIO.")
    sys.exit(1)
if subprocess.call(['dpkg', '-i', MINIO_DEB]) != 0:
    print("Échec de l'installation de MinIO.")
    sys.exit(1)

# Modification des variables d'environnement en pur Python
var_defaut = "/etc/default/minio"
if not os.path.isfile(var_defaut):
    print(f"Le fichier {var_defaut} n'existe pas !")
    sys.exit(1)

# Sécurisation du fichier d'environnement
subprocess.run(['chmod', '640', var_defaut], check=True)
subprocess.run(['chown', 'root:minio-user', var_defaut], check=True)

user = input("Entrez le nom d'utilisateur admin pour la console : ").strip()

# Saisie masquée du mot de passe
while True:
    password = getpass.getpass("Entrez le mot de passe admin : ")
    password2 = getpass.getpass("Confirmez le mot de passe : ")
    if password == password2:
        break
    print("Les mots de passe ne correspondent pas. Réessayez.")

def update_env_file(filename, updates):
    # Lis toutes les lignes
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Modifie les lignes selon updates (dict)
    new_lines = []
    for line in lines:
        matched = False
        for key, value in updates.items():
            if line.strip().startswith(f"{key}="):
                new_lines.append(f'{key}="{value}"\n')
                matched = True
                break
        if not matched:
            new_lines.append(line)
    # Ajoute les clés manquantes
    for key, value in updates.items():
        if not any(l.strip().startswith(f"{key}=") for l in lines):
            new_lines.append(f'{key}="{value}"\n')
    # Écris le fichier
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

update_env_file(var_defaut, {
    "MINIO_ROOT_USER": user,
    "MINIO_ROOT_PASSWORD": password,
    "MINIO_VOLUMES": repo
})

# Création du certificat auto-signé
CERTGEN = "/tmp/certgen-linux-amd64"
certgen_url = "https://github.com/minio/certgen/releases/latest/download/certgen-linux-amd64"
if subprocess.call(['wget', '-qO', CERTGEN, certgen_url]) != 0:
    print("Échec du téléchargement de certgen.")
    sys.exit(1)
subprocess.run(['chmod', '+x', CERTGEN], check=True)

# Détection automatique ou saisie de l'adresse IP
def is_valid_ipv4(ip):
    if not re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", ip):
        return False
    parts = [int(x) for x in ip.split('.')]
    return all(0 <= part <= 255 for part in parts)

multi_ip = input("Voulez-vous détecter automatiquement l'adresse IP (o/n) : ").strip().lower()

if multi_ip == "n":
    # L'utilisateur souhaite choisir l'IP manuellement
    while True:
        address = input("Quelle est l'IP de votre serveur ? : ").strip()
        if is_valid_ipv4(address):
            break
        print("Adresse IP invalide, veuillez réessayer.")
else:
    # Détection automatique avec validation utilisateur
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
            break
        else:
            address = input("Veuillez saisir l'adresse IP à utiliser : ").strip()
            if is_valid_ipv4(address):
                break
            print("Adresse IP invalide, veuillez réessayer.")

# Génération du certificat
subprocess.run([CERTGEN, "-host", f"127.0.0.1,localhost,{address}"], check=True)

# Préparation du dossier certs
CERT_DIR = "/home/minio-user/.minio/certs"
os.makedirs(CERT_DIR, exist_ok=True)
try:
    shutil.move("public.crt", CERT_DIR)
    shutil.move("private.key", CERT_DIR)
except Exception as e:
    print(f"Erreur lors du déplacement des certificats : {e}")
    sys.exit(1)
subprocess.run(['chown', '-R', 'minio-user:minio-user', "/home/minio-user/.minio"], check=True)

# Nettoyage des fichiers temporaires
for f in [MINIO_DEB, CERTGEN]:
    try:
        os.remove(f)
    except Exception:
        pass

print("Installation complète. Voici les dernières lignes du journal MinIO :")
subprocess.call(['journalctl', '-xeu', 'minio', '-n', '7'])

print("Accédez à la console MinIO avec :")
print(f"  Utilisateur : {user}")
print("  Mot de passe : (celui que vous avez choisi)")
print(f"  URL : https://{address}:9000")
