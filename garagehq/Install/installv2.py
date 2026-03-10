#!/usr/bin/env python3
"""
Garage S3 - Script d'installation, désinstallation et réinstallation.
Usage:
    python3 install.py --install
    python3 install.py --uninstall [--keep-data]
    python3 install.py --reinstall [--keep-data]
"""

import os
import sys
import subprocess
import shutil
import re
import argparse
import getpass
import secrets
import time
import io
from dataclasses import dataclass, field
from typing import Optional

import requests

# ── Encodage UTF-8 forcé pour le terminal ─────────────────────────────────
if sys.stdin.encoding != 'utf-8':
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Constantes ────────────────────────────────────────────────────────────
GARAGE_BIN     = "/usr/local/bin/garage"
WEBUI_BIN      = "/usr/local/bin/garage-webui"
CONFIG_DIR     = "/etc/garage"
CONFIG_FILE    = f"{CONFIG_DIR}/garage.toml"
WEBUI_ENV      = f"{CONFIG_DIR}/webui.env"
SERVICE_GARAGE = "/etc/systemd/system/garage.service"
SERVICE_WEBUI  = "/etc/systemd/system/garage-webui.service"
GITEA_API      = "https://git.deuxfleurs.fr/api/v1/repos/Deuxfleurs/garage/releases?limit=50&page=1"
GITHUB_WEBUI   = "https://api.github.com/repos/khairul169/garage-webui/releases/latest"


# ═════════════════════════════════════════════════════════════════════════════
# Dataclass de configuration
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class InstallConfig:
    data_dir:       str  = ""
    meta_dir:       str  = ""
    address:        str  = ""
    zone:           str  = "dc1"
    capacity:       str  = "100"
    key_name:       str  = "admin-key"
    garage_version: str  = ""
    rpc_secret:     str  = field(default_factory=lambda: secrets.token_hex(32))
    admin_token:    str  = field(default_factory=lambda: secrets.token_hex(32))
    install_webui:  bool = False
    webui_version:  str  = ""
    webui_auth:     bool = False
    webui_user:     str  = ""
    webui_hash:     str  = ""
    ak:             str  = "(a creer manuellement)"
    sk:             str  = "(a creer manuellement)"


# ═════════════════════════════════════════════════════════════════════════════
# Utilitaires statiques
# ═════════════════════════════════════════════════════════════════════════════
class Utils:

    @staticmethod
    def check_root():
        if sys.platform != "win32" and os.geteuid() != 0:
            print("Ce script doit etre execute en tant que root.", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def check_deps(cmds: list):
        for cmd in cmds:
            if shutil.which(cmd) is None:
                print(f"Dependance manquante : {cmd}")
                sys.exit(1)

    @staticmethod
    def is_valid_ipv4(ip: str) -> bool:
        if not re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", ip):
            return False
        return all(0 <= int(p) <= 255 for p in ip.split('.'))

    @staticmethod
    def semver_key(tag: str) -> tuple:
        return tuple(int(x) for x in tag.lstrip("v").split('.'))

    @staticmethod
    def run(cmd: list, **kwargs):
        return subprocess.run(cmd, check=True, **kwargs)

    @staticmethod
    def call(cmd: list, **kwargs) -> int:
        return subprocess.call(cmd, **kwargs)

    @staticmethod
    def ask(prompt: str, default: str = "") -> str:
        val = input(prompt).strip()
        return val if val else default

    @staticmethod
    def confirm(prompt: str) -> bool:
        return input(prompt).strip().lower() == "o"


# ═════════════════════════════════════════════════════════════════════════════
# Collecte interactive de la configuration
# ═════════════════════════════════════════════════════════════════════════════
class ConfigCollector:

    def collect(self) -> InstallConfig:
        cfg = InstallConfig()
        cfg.data_dir       = self._ask_dir("Chemin du repertoire de donnees Garage : ")
        cfg.meta_dir       = self._ask_dir("Chemin du repertoire de metadonnees Garage : ")
        cfg.address        = self._ask_ip()
        cfg.garage_version = self._fetch_garage_version()
        cfg.zone           = Utils.ask("Zone/datacenter (ex: dc1) : ", "dc1")
        cfg.capacity       = Utils.ask("Capacite en Go (ex: 100) : ", "100")
        cfg.key_name       = Utils.ask("Nom de la cle d'acces S3 (ex: admin-key) : ", "admin-key")
        cfg.install_webui  = Utils.confirm("Installer garage-webui ? (o/n) : ")
        if cfg.install_webui:
            cfg.webui_version = self._fetch_webui_version()
            cfg.webui_auth    = Utils.confirm("Activer l'authentification sur le webui ? (o/n) : ")
            if cfg.webui_auth:
                cfg.webui_user, cfg.webui_hash = self._ask_webui_auth()
        return cfg

    def _ask_dir(self, prompt: str) -> str:
        path = input(prompt).strip()
        if not os.path.isdir(path):
            print(f"Le repertoire {path} n'existe pas, creation...")
            try:
                os.makedirs(path)
            except Exception as e:
                print(f"Erreur : {e}")
                sys.exit(1)
        return path

    def _ask_ip(self) -> str:
        if Utils.confirm("Detection automatique de l'adresse IP ? (o/n) : "):
            while True:
                try:
                    ip = subprocess.check_output(
                        "ip -o -4 addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1",
                        shell=True, text=True
                    ).strip()
                except Exception:
                    ip = ""
                print(f"IP detectee : {ip}")
                if Utils.confirm("Valider cette IP ? (o/n) : ") and Utils.is_valid_ipv4(ip):
                    return ip
                ip = input("Saisissez l'IP manuellement : ").strip()
                if Utils.is_valid_ipv4(ip):
                    return ip
                print("IP invalide.")
        else:
            while True:
                ip = input("IP du serveur : ").strip()
                if Utils.is_valid_ipv4(ip):
                    return ip
                print("IP invalide.")

    def _fetch_garage_version(self) -> str:
        print("Recherche de la derniere version stable de Garage...")
        try:
            r = requests.get(GITEA_API, headers={"Accept": "application/json"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            stable = [
                x for x in data
                if not x.get("prerelease") and not x.get("draft")
                and re.match(r'^v?\d+\.\d+\.\d+$', x["tag_name"])
            ]
            if not stable:
                print("Aucune release stable trouvee.")
                sys.exit(1)
            latest = sorted(stable, key=lambda x: Utils.semver_key(x["tag_name"]), reverse=True)[0]
            version = latest["tag_name"].lstrip("v")
            print(f"Version de Garage selectionnee : v{version}")
            return version
        except Exception as e:
            print(f"Erreur lors de la recuperation de la version Garage : {e}")
            sys.exit(1)

    def _fetch_webui_version(self) -> str:
        try:
            r = requests.get(GITHUB_WEBUI, headers={"Accept": "application/vnd.github+json"}, timeout=10)
            r.raise_for_status()
            version = r.json()["tag_name"].lstrip("v")
            print(f"Version de garage-webui selectionnee : v{version}")
            return version
        except Exception as e:
            print(f"Impossible de recuperer la version de garage-webui : {e}")
            return ""

    def _ask_webui_auth(self) -> tuple:
        if shutil.which('htpasswd') is None:
            print("Installation de apache2-utils (htpasswd)...")
            Utils.run(['apt', 'install', '-y', 'apache2-utils'], stdout=subprocess.DEVNULL)
        user = Utils.ask("Nom d'utilisateur webui : ", "admin")
        while True:
            pwd  = getpass.getpass("Mot de passe webui : ")
            pwd2 = getpass.getpass("Confirmez le mot de passe : ")
            if pwd == pwd2:
                break
            print("Les mots de passe ne correspondent pas.")
        try:
            h = subprocess.check_output(
                ['htpasswd', '-bnBC', '10', user, pwd], text=True
            ).strip()
            print("Hash d'authentification genere.")
            return user, h
        except Exception as e:
            print(f"Erreur generation hash : {e}")
            return user, ""


# ═════════════════════════════════════════════════════════════════════════════
# Installateur
# ═════════════════════════════════════════════════════════════════════════════
class GarageInstaller:

    def __init__(self, cfg: InstallConfig):
        self.cfg = cfg

    def run(self):
        print("\n" + "="*60)
        print("INSTALLATION DE GARAGE")
        print("="*60)
        self._create_system_user()
        self._download_garage()
        self._write_config()
        self._setup_garage_service()
        self._configure_layout()
        self._create_s3_key()
        if self.cfg.install_webui:
            self._install_webui()
        self._print_summary()

    def _create_system_user(self):
        print("\n[1/7] Creation de l'utilisateur systeme...")
        if Utils.call(['getent', 'group', 'garage'], stdout=subprocess.DEVNULL) != 0:
            Utils.run(['groupadd', '-r', 'garage'])
        if Utils.call(['id', 'garage'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            Utils.run(['useradd', '-r', '-g', 'garage', '-s', '/sbin/nologin',
                       '-d', '/var/lib/garage', 'garage'])
        Utils.run(['chown', 'garage:garage', self.cfg.data_dir])
        Utils.run(['chown', 'garage:garage', self.cfg.meta_dir])

    def _download_garage(self):
        print(f"\n[2/7] Telechargement de Garage v{self.cfg.garage_version}...")
        url = (f"https://garagehq.deuxfleurs.fr/_releases/v{self.cfg.garage_version}"
               f"/x86_64-unknown-linux-musl/garage")
        if Utils.call(['wget', '-qO', GARAGE_BIN, url]) != 0:
            print("Echec du telechargement de Garage.")
            sys.exit(1)
        Utils.run(['chmod', '+x', GARAGE_BIN])

    def _write_config(self):
        print(f"\n[3/7] Ecriture de la configuration dans {CONFIG_FILE}...")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        major = int(self.cfg.garage_version.split('.')[0])
        replication = 'replication_factor = 1' if major >= 2 else 'replication_mode = "none"'
        content = f"""metadata_dir = "{self.cfg.meta_dir}"
data_dir = "{self.cfg.data_dir}"

db_engine = "lmdb"

{replication}

rpc_bind_addr = "0.0.0.0:3901"
rpc_public_addr = "{self.cfg.address}:3901"
rpc_secret = "{self.cfg.rpc_secret}"

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
admin_token = "{self.cfg.admin_token}"
"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        Utils.run(['chmod', '640', CONFIG_FILE])
        Utils.run(['chown', 'root:garage', CONFIG_FILE])

    def _setup_garage_service(self):
        print("\n[4/7] Creation et demarrage du service systemd garage...")
        content = f"""[Unit]
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
        with open(SERVICE_GARAGE, 'w', encoding='utf-8') as f:
            f.write(content)
        Utils.run(['systemctl', 'daemon-reload'])
        Utils.run(['systemctl', 'enable', 'garage'])
        Utils.run(['systemctl', 'start', 'garage'])
        print("Service garage demarre. Attente de 3 secondes...")
        time.sleep(3)

    def _configure_layout(self):
        print("\n[5/7] Configuration du layout du cluster...")
        try:
            node_id = subprocess.check_output(
                [GARAGE_BIN, '-c', CONFIG_FILE, 'node', 'id'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            short_id = node_id.split('@')[0][:8] if '@' in node_id else node_id[:8]
            print(f"Node ID : {node_id}")
            Utils.run([GARAGE_BIN, '-c', CONFIG_FILE, 'layout', 'assign',
                       '-z', self.cfg.zone, '-c', f'{self.cfg.capacity}G', short_id])
            Utils.run([GARAGE_BIN, '-c', CONFIG_FILE, 'layout', 'apply', '--version', '1'])
            print("Layout applique.")
        except Exception as e:
            print(f"Attention : layout a configurer manuellement : {e}")

    def _create_s3_key(self):
        print(f"\n[6/7] Creation de la cle S3 '{self.cfg.key_name}'...")
        try:
            out = subprocess.check_output(
                [GARAGE_BIN, '-c', CONFIG_FILE, 'key', 'create', self.cfg.key_name],
                text=True
            )
            print(out)
            ak = re.search(r'Key ID:\s+(\S+)', out)
            sk = re.search(r'Secret key:\s+(\S+)', out)
            if ak and sk:
                self.cfg.ak = ak.group(1)
                self.cfg.sk = sk.group(1)
            else:
                self.cfg.ak, self.cfg.sk = "(voir ci-dessus)", "(voir ci-dessus)"
        except Exception as e:
            print(f"Erreur creation cle S3 : {e}")

    def _install_webui(self):
        print(f"\n[7/7] Installation de garage-webui v{self.cfg.webui_version}...")
        if not self.cfg.webui_version:
            print("Version webui inconnue, installation annulee.")
            return
        try:
            r = requests.get(GITHUB_WEBUI, headers={"Accept": "application/vnd.github+json"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            url = next(
                (a["browser_download_url"] for a in data.get("assets", [])
                 if "linux-amd64" in a["name"]),
                (f"https://github.com/khairul169/garage-webui/releases/download/"
                 f"v{self.cfg.webui_version}/garage-webui-v{self.cfg.webui_version}-linux-amd64")
            )
        except Exception:
            url = (f"https://github.com/khairul169/garage-webui/releases/download/"
                   f"v{self.cfg.webui_version}/garage-webui-v{self.cfg.webui_version}-linux-amd64")

        if Utils.call(['wget', '-qO', WEBUI_BIN, url]) != 0:
            print("Echec du telechargement de garage-webui.")
            return
        Utils.run(['chmod', '+x', WEBUI_BIN])

        env = f"PORT=3909\nCONFIG_PATH={CONFIG_FILE}\nAPI_BASE_URL=http://127.0.0.1:3903\n"
        if self.cfg.webui_auth and self.cfg.webui_hash:
            env += f"AUTH_USER_PASS={self.cfg.webui_hash}\n"
        with open(WEBUI_ENV, 'w', encoding='utf-8') as f:
            f.write(env)
        Utils.run(['chmod', '640', WEBUI_ENV])
        Utils.run(['chown', 'root:garage', WEBUI_ENV])

        svc = f"""[Unit]
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
        with open(SERVICE_WEBUI, 'w', encoding='utf-8') as f:
            f.write(svc)
        Utils.run(['systemctl', 'daemon-reload'])
        Utils.run(['systemctl', 'enable', 'garage-webui'])
        Utils.run(['systemctl', 'start', 'garage-webui'])
        print("garage-webui installe et demarre.")

    def _print_summary(self):
        cfg  = self.cfg
        addr = cfg.address
        print("\n" + "="*60)
        print("INSTALLATION TERMINEE")
        print("="*60)
        print(f"  Version Garage : v{cfg.garage_version}")
        print(f"  Config         : {CONFIG_FILE}")
        print(f"  Donnees        : {cfg.data_dir}")
        print(f"  Metadonnees    : {cfg.meta_dir}")
        print(f"  RPC Secret     : {cfg.rpc_secret}")
        print(f"  Admin Token    : {cfg.admin_token}")
        print(f"  Access Key ID  : {cfg.ak}")
        print(f"  Secret Key     : {cfg.sk}")
        print(f"\n  API S3         : http://{addr}:3900")
        print(f"  Web statique   : http://{addr}:3902")
        print(f"  Admin API      : http://{addr}:3903")
        if cfg.install_webui:
            print(f"  Interface Web  : http://{addr}:3909")
            if cfg.webui_user:
                print(f"  WebUI User     : {cfg.webui_user}")
            print(f"  WebUI Token    : {cfg.admin_token}")
        print("\nLogs :")
        print("  journalctl -xeu garage -n 20")
        if cfg.install_webui:
            print("  journalctl -xeu garage-webui -n 20")
        print("\nCreer un bucket :")
        print(f"  garage -c {CONFIG_FILE} bucket create mon-bucket")
        print(f"  garage -c {CONFIG_FILE} bucket allow --read --write --key {cfg.key_name} mon-bucket")


# ═════════════════════════════════════════════════════════════════════════════
# Désinstallateur
# ═════════════════════════════════════════════════════════════════════════════
class GarageUninstaller:

    def run(self, keep_data: bool = False):
        print("\n" + "="*60)
        print("DESINSTALLATION DE GARAGE")
        print("="*60)
        if not keep_data:
            print("\n  ATTENTION : toutes les donnees seront supprimees !")
            if not Utils.confirm("Confirmer la suppression complete ? (o/n) : "):
                print("Desinstallation annulee.")
                return
        # Lit les chemins avant de supprimer la config
        data_dirs = self._get_data_dirs_from_toml()
        self._stop_services()
        self._remove_binaries()
        self._remove_services()
        self._remove_config()
        self._remove_user()
        if not keep_data:
            self._remove_data(data_dirs)
        print("\nDesinstallation terminee.")

    def get_data_dirs(self) -> list:
        return self._get_data_dirs_from_toml()

    def _stop_services(self):
        print("\n[1/5] Arret des services...")
        for svc in ['garage-webui', 'garage']:
            Utils.call(['systemctl', 'stop',    svc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Utils.call(['systemctl', 'disable', svc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _remove_binaries(self):
        print("[2/5] Suppression des binaires...")
        for f in [GARAGE_BIN, WEBUI_BIN]:
            if os.path.isfile(f):
                os.remove(f)
                print(f"  Supprime : {f}")

    def _remove_services(self):
        print("[3/5] Suppression des services systemd...")
        for f in [SERVICE_GARAGE, SERVICE_WEBUI]:
            if os.path.isfile(f):
                os.remove(f)
                print(f"  Supprime : {f}")
        Utils.run(['systemctl', 'daemon-reload'])

    def _remove_config(self):
        print("[4/5] Suppression de la configuration...")
        if os.path.isdir(CONFIG_DIR):
            shutil.rmtree(CONFIG_DIR)
            print(f"  Supprime : {CONFIG_DIR}")

    def _remove_user(self):
        print("[5/5] Suppression de l'utilisateur systeme...")
        Utils.call(['userdel',  'garage'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        Utils.call(['groupdel', 'garage'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _remove_data(self, data_dirs: list):
        print("\nSuppression des donnees...")
        if not data_dirs:
            print("  Aucun chemin de donnees trouve.")
            return
        for d in data_dirs:
            if d and os.path.isdir(d):
                shutil.rmtree(d)
                print(f"  Supprime : {d}")

    def _get_data_dirs_from_toml(self) -> list:
        dirs = []
        if not os.path.isfile(CONFIG_FILE):
            return dirs
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            for key in ['metadata_dir', 'data_dir']:
                m = re.search(rf'^{key}\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if m:
                    dirs.append(m.group(1))
        except Exception:
            pass
        return dirs


# ═════════════════════════════════════════════════════════════════════════════
# Réinstallateur
# ═════════════════════════════════════════════════════════════════════════════
class GarageReinstaller:

    def run(self, keep_data: bool = True):
        print("\n" + "="*60)
        print("REINSTALLATION DE GARAGE")
        print("="*60)

        uninstaller = GarageUninstaller()
        # Sauvegarde les chemins avant désinstallation
        saved_dirs = uninstaller.get_data_dirs()
        uninstaller.run(keep_data=keep_data)

        print("\nConfiguration de la nouvelle installation...")
        cfg = ConfigCollector().collect()

        # Pré-remplit les chemins de données si keep_data
        if keep_data and saved_dirs:
            if len(saved_dirs) >= 1 and not cfg.meta_dir:
                cfg.meta_dir = saved_dirs[0]
            if len(saved_dirs) >= 2 and not cfg.data_dir:
                cfg.data_dir = saved_dirs[1]

        GarageInstaller(cfg).run()


# ═════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Gestionnaire d'installation de Garage S3",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--install',   action='store_true', help='Installer Garage')
    group.add_argument('--uninstall', action='store_true', help='Desinstaller Garage')
    group.add_argument('--reinstall', action='store_true', help='Reinstaller Garage')
    parser.add_argument('--keep-data', action='store_true',
                        help='Conserver les donnees lors de la desinstallation/reinstallation')
    args = parser.parse_args()

    Utils.check_root()
    Utils.check_deps(['wget', 'getent', 'id', 'chmod', 'chown', 'ip',
                      'awk', 'cut', 'head', 'journalctl'])

    if args.install:
        cfg = ConfigCollector().collect()
        GarageInstaller(cfg).run()

    elif args.uninstall:
        GarageUninstaller().run(keep_data=args.keep_data)

    elif args.reinstall:
        GarageReinstaller().run(keep_data=args.keep_data)


if __name__ == "__main__":
    main()