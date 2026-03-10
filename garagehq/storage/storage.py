#!/usr/bin/env python3
"""
Script de configuration du stockage SAN FC.
Gère : multipath, LVM (PV → VG → LV), formatage et montage.

Usage:
    python3 storage.py --setup
    python3 storage.py --teardown [--keep-data]
    python3 storage.py --status
"""

import os
import sys
import subprocess
import shutil
import re
import argparse
import time
import io
from dataclasses import dataclass, field
from typing import Optional

# ── Encodage UTF-8 ────────────────────────────────────────────────────────
if sys.stdin.encoding != 'utf-8':
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Constantes ────────────────────────────────────────────────────────────
MULTIPATH_CONF = "/etc/multipath.conf"
FSTAB          = "/etc/fstab"
FSTAB_MARKER   = "# === GARAGE STORAGE ==="


# ═════════════════════════════════════════════════════════════════════════════
# Dataclass de configuration
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class StorageConfig:
    # Multipath
    devices:      list  = field(default_factory=list)  # ex: ['/dev/sdb', '/dev/sdc']
    wwids:        list  = field(default_factory=list)  # WWID des LUNs
    mpath_names:  list  = field(default_factory=list)  # ex: ['mpatha', 'mpathb']

    # LVM
    vg_name:      str   = "vg_garage"
    lv_data_name: str   = "lv_data"
    lv_meta_name: str   = "lv_meta"
    lv_data_size: str   = ""   # ex: "900G" ou "100%FREE"
    lv_meta_size: str   = ""   # ex: "50G"
    stripe_count: int   = 1    # 1 = pas de striping, >1 = striping sur N LUNs

    # Filesystem
    fs_data:      str   = "xfs"   # xfs / ext4 / btrfs
    fs_meta:      str   = "ext4"  # ext4 / btrfs

    # Points de montage
    mount_data:   str   = "/data"
    mount_meta:   str   = "/data/meta"


# ═════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ═════════════════════════════════════════════════════════════════════════════
class Utils:

    @staticmethod
    def check_root():
        if sys.platform != "win32" and os.geteuid() != 0:
            print("Ce script doit etre execute en tant que root.", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def check_deps(cmds: list):
        missing = [c for c in cmds if shutil.which(c) is None]
        if missing:
            print(f"Dependances manquantes : {', '.join(missing)}")
            print("Installez-les avec : apt install multipath-tools lvm2 xfsprogs btrfs-progs")
            sys.exit(1)

    @staticmethod
    def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, **kwargs)

    @staticmethod
    def run_out(cmd: list, **kwargs) -> str:
        return subprocess.check_output(cmd, text=True, **kwargs).strip()

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

    @staticmethod
    def hr(title: str = ""):
        if title:
            print(f"\n{'='*60}")
            print(f"  {title}")
            print(f"{'='*60}")
        else:
            print("-" * 60)

    @staticmethod
    def install_packages(pkgs: list):
        print(f"Installation des paquets : {' '.join(pkgs)}...")
        Utils.run(['apt', 'install', '-y'] + pkgs, stdout=subprocess.DEVNULL)


# ═════════════════════════════════════════════════════════════════════════════
# Détection des LUNs FC
# ═════════════════════════════════════════════════════════════════════════════
class StorageDetector:

    def detect_fc_luns(self) -> list:
        """Retourne la liste des disques FC détectés via multipath ou /sys."""
        print("Scan des LUNs FC disponibles...")
        luns = []

        # Méthode 1 : multipath -ll
        try:
            out = Utils.run_out(['multipath', '-ll'], stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                # Ligne de device type : mpatha (360...) dm-0
                m = re.match(r'^(\w+)\s+\(([0-9a-f]+)\)', line)
                if m:
                    luns.append({
                        'name':   m.group(1),
                        'wwid':   m.group(2),
                        'device': f"/dev/mapper/{m.group(1)}"
                    })
        except Exception:
            pass

        # Méthode 2 : lsblk si multipath vide
        if not luns:
            try:
                out = Utils.run_out(
                    ['lsblk', '-d', '-o', 'NAME,TYPE,TRAN,SIZE,MODEL', '--json'],
                    stderr=subprocess.DEVNULL
                )
                import json
                data = json.loads(out)
                for dev in data.get('blockdevices', []):
                    if dev.get('tran') in ['fc', 'sas', 'scsi']:
                        luns.append({
                            'name':   dev['name'],
                            'wwid':   self._get_wwid(f"/dev/{dev['name']}"),
                            'device': f"/dev/{dev['name']}",
                            'size':   dev.get('size', '?'),
                            'model':  dev.get('model', '?')
                        })
            except Exception:
                pass

        # Méthode 3 : fallback sur tous les disques non-système
        if not luns:
            try:
                out = Utils.run_out(['lsblk', '-d', '-o', 'NAME,SIZE,TYPE', '-n'])
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] not in ['sda', 'vda', 'nvme0n1']:
                        if parts[2] == 'disk' if len(parts) > 2 else True:
                            luns.append({
                                'name':   parts[0],
                                'wwid':   self._get_wwid(f"/dev/{parts[0]}"),
                                'device': f"/dev/{parts[0]}",
                                'size':   parts[1] if len(parts) > 1 else '?'
                            })
            except Exception:
                pass

        return luns

    def _get_wwid(self, device: str) -> str:
        """Récupère le WWID d'un device via /lib/udev/scsi_id."""
        try:
            return Utils.run_out(
                ['/lib/udev/scsi_id', '--page=0x83', '--whitelisted', device],
                stderr=subprocess.DEVNULL
            )
        except Exception:
            return "inconnu"

    def show_luns(self, luns: list):
        if not luns:
            print("  Aucun LUN FC detecte.")
            return
        print(f"\n  {'#':<4} {'Device':<20} {'WWID':<35} {'Taille':<10} {'Modele'}")
        print("  " + "-" * 80)
        for i, lun in enumerate(luns):
            print(f"  {i:<4} {lun['device']:<20} {lun.get('wwid','?'):<35} "
                  f"{lun.get('size','?'):<10} {lun.get('model','')}")


# ═════════════════════════════════════════════════════════════════════════════
# Configuration Multipath
# ═════════════════════════════════════════════════════════════════════════════
class MultipathConfigurator:

    def setup(self, cfg: StorageConfig):
        Utils.hr("CONFIGURATION MULTIPATH")

        # Installation
        if shutil.which('multipath') is None:
            Utils.install_packages(['multipath-tools'])

        # Configuration de base
        self._write_multipath_conf(cfg)

        # Activation du service
        Utils.run(['systemctl', 'enable', 'multipathd'])
        Utils.run(['systemctl', 'restart', 'multipathd'])
        time.sleep(2)

        # Scan et flush
        Utils.call(['multipath', '-F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        Utils.run(['multipath'], stdout=subprocess.DEVNULL)
        time.sleep(2)

        print("Multipath configure et demarre.")
        self._show_status()

    def _write_multipath_conf(self, cfg: StorageConfig):
        """Écrit /etc/multipath.conf avec les WWIDs des LUNs sélectionnés."""
        blacklist_exceptions = ""
        for wwid in cfg.wwids:
            if wwid and wwid != "inconnu":
                blacklist_exceptions += f"""
    wwid "{wwid}"
"""

        content = f"""defaults {{
    user_friendly_names yes
    find_multipaths     yes
    polling_interval    10
    path_selector       "round-robin 0"
    failback            immediate
    no_path_retry       fail
}}

blacklist {{
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^hd[a-z]"
    devnode "^sda"
}}

blacklist_exceptions {{
{blacklist_exceptions}
}}

devices {{
    device {{
        vendor          ".*"
        product         ".*"
        path_grouping_policy multibus
        getuid_callout  "/lib/udev/scsi_id --whitelisted --device=/dev/%n"
        path_checker    readsector0
        path_selector   "round-robin 0"
        hardware_handler "0"
        failback        immediate
        rr_weight       priorities
        no_path_retry   fail
    }}
}}
"""
        with open(MULTIPATH_CONF, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Configuration multipath ecrite dans {MULTIPATH_CONF}")

    def _show_status(self):
        print("\nStatut multipath :")
        Utils.call(['multipath', '-ll'])

    def teardown(self):
        print("Arret de multipathd...")
        Utils.call(['systemctl', 'stop',    'multipathd'], stderr=subprocess.DEVNULL)
        Utils.call(['systemctl', 'disable', 'multipathd'], stderr=subprocess.DEVNULL)
        Utils.call(['multipath', '-F'], stderr=subprocess.DEVNULL)


# ═════════════════════════════════════════════════════════════════════════════
# Configuration LVM
# ═════════════════════════════════════════════════════════════════════════════
class LVMConfigurator:

    def setup(self, cfg: StorageConfig):
        Utils.hr("CONFIGURATION LVM")

        if shutil.which('pvcreate') is None:
            Utils.install_packages(['lvm2'])

        devices = cfg.devices
        stripe  = cfg.stripe_count

        # PV
        print(f"\nCreation des Physical Volumes sur : {', '.join(devices)}")
        for dev in devices:
            Utils.run(['pvcreate', '-ff', '-y', dev])
            print(f"  PV cree : {dev}")

        # VG
        print(f"\nCreation du Volume Group '{cfg.vg_name}'...")
        Utils.run(['vgcreate', cfg.vg_name] + devices)
        print(f"  VG cree : {cfg.vg_name}")

        # LV data
        print(f"\nCreation du LV donnees '{cfg.lv_data_name}' ({cfg.lv_data_size})...")
        lv_data_cmd = ['lvcreate', '-y', '-n', cfg.lv_data_name, '-L', cfg.lv_data_size]
        if stripe > 1:
            lv_data_cmd += ['-i', str(stripe), '-I', '256']
            print(f"  Striping actif sur {stripe} devices (stripe size: 256K)")
        lv_data_cmd.append(cfg.vg_name)
        Utils.run(lv_data_cmd)
        print(f"  LV cree : /dev/{cfg.vg_name}/{cfg.lv_data_name}")

        # LV meta
        print(f"\nCreation du LV metadonnees '{cfg.lv_meta_name}' ({cfg.lv_meta_size})...")
        Utils.run(['lvcreate', '-y', '-n', cfg.lv_meta_name, '-L', cfg.lv_meta_size, cfg.vg_name])
        print(f"  LV cree : /dev/{cfg.vg_name}/{cfg.lv_meta_name}")

        self._show_status(cfg)

    def _show_status(self, cfg: StorageConfig):
        print("\nStatut LVM :")
        Utils.call(['vgs',  cfg.vg_name])
        Utils.call(['lvs',  cfg.vg_name])

    def teardown(self, cfg: StorageConfig):
        print(f"Suppression du VG '{cfg.vg_name}'...")
        Utils.call(['vgchange', '-an', cfg.vg_name], stderr=subprocess.DEVNULL)
        Utils.call(['vgremove', '-ff', '-y', cfg.vg_name], stderr=subprocess.DEVNULL)
        for dev in cfg.devices:
            Utils.call(['pvremove', '-ff', '-y', dev], stderr=subprocess.DEVNULL)
            print(f"  PV supprime : {dev}")


# ═════════════════════════════════════════════════════════════════════════════
# Configuration Filesystem et montage
# ═════════════════════════════════════════════════════════════════════════════
class FilesystemConfigurator:

    FS_PACKAGES = {
        'xfs':   'xfsprogs',
        'btrfs': 'btrfs-progs',
        'ext4':  'e2fsprogs',
    }

    def setup(self, cfg: StorageConfig):
        Utils.hr("FORMATAGE ET MONTAGE")

        self._ensure_fs_tools(cfg.fs_data)
        self._ensure_fs_tools(cfg.fs_meta)

        dev_data = f"/dev/{cfg.vg_name}/{cfg.lv_data_name}"
        dev_meta = f"/dev/{cfg.vg_name}/{cfg.lv_meta_name}"

        # Formatage
        print(f"\nFormatage {dev_data} en {cfg.fs_data}...")
        self._mkfs(dev_data, cfg.fs_data, label="garage-data")

        print(f"Formatage {dev_meta} en {cfg.fs_meta}...")
        self._mkfs(dev_meta, cfg.fs_meta, label="garage-meta")

        # Création des points de montage
        os.makedirs(cfg.mount_data, exist_ok=True)
        os.makedirs(cfg.mount_meta, exist_ok=True)

        # Montage
        print(f"\nMontage {dev_data} sur {cfg.mount_data}...")
        Utils.run(['mount', dev_data, cfg.mount_data])

        print(f"Montage {dev_meta} sur {cfg.mount_meta}...")
        Utils.run(['mount', dev_meta, cfg.mount_meta])

        # Ajout dans /etc/fstab
        self._add_fstab(cfg)

        print("\nFilesystems montes et persistes dans /etc/fstab.")
        Utils.call(['df', '-h', cfg.mount_data, cfg.mount_meta])

    def _mkfs(self, device: str, fs: str, label: str = ""):
        if fs == 'xfs':
            cmd = ['mkfs.xfs', '-f']
            if label:
                cmd += ['-L', label[:12]]  # XFS limite à 12 chars
            cmd.append(device)
        elif fs == 'btrfs':
            cmd = ['mkfs.btrfs', '-f']
            if label:
                cmd += ['-L', label]
            cmd.append(device)
        else:  # ext4
            cmd = ['mkfs.ext4', '-F']
            if label:
                cmd += ['-L', label]
            cmd.append(device)
        Utils.run(cmd)

    def _ensure_fs_tools(self, fs: str):
        pkg = self.FS_PACKAGES.get(fs)
        if pkg and shutil.which(f"mkfs.{fs}") is None:
            Utils.install_packages([pkg])

    def _get_uuid(self, device: str) -> str:
        try:
            return Utils.run_out(['blkid', '-s', 'UUID', '-o', 'value', device])
        except Exception:
            return ""

    def _add_fstab(self, cfg: StorageConfig):
        dev_data = f"/dev/{cfg.vg_name}/{cfg.lv_data_name}"
        dev_meta = f"/dev/{cfg.vg_name}/{cfg.lv_meta_name}"

        uuid_data = self._get_uuid(dev_data)
        uuid_meta = self._get_uuid(dev_meta)

        # Détermine les options de montage selon le filesystem
        opts_data = self._mount_opts(cfg.fs_data)
        opts_meta = self._mount_opts(cfg.fs_meta)

        entry_data = (f"UUID={uuid_data}" if uuid_data else dev_data)
        entry_meta = (f"UUID={uuid_meta}" if uuid_meta else dev_meta)

        fstab_block = f"""
{FSTAB_MARKER}
{entry_data}  {cfg.mount_data}  {cfg.fs_data}  {opts_data}  0 2
{entry_meta}  {cfg.mount_meta}  {cfg.fs_meta}  {opts_meta}  0 2
# === END GARAGE STORAGE ===
"""
        # Supprime un éventuel ancien bloc
        self._remove_fstab_block()

        with open(FSTAB, 'a', encoding='utf-8') as f:
            f.write(fstab_block)
        print(f"Entrees ajoutees dans {FSTAB}")

    def _mount_opts(self, fs: str) -> str:
        opts = {
            'xfs':   'defaults,noatime',
            'btrfs': 'defaults,noatime,compress=zstd',
            'ext4':  'defaults,noatime',
        }
        return opts.get(fs, 'defaults')

    def _remove_fstab_block(self):
        if not os.path.isfile(FSTAB):
            return
        with open(FSTAB, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        skip = False
        for line in lines:
            if FSTAB_MARKER in line:
                skip = True
            if '# === END GARAGE STORAGE ===' in line:
                skip = False
                continue
            if not skip:
                new_lines.append(line)
        with open(FSTAB, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    def teardown(self, cfg: StorageConfig):
        print("Demontage des filesystems...")
        for mount in [cfg.mount_meta, cfg.mount_data]:
            if os.path.ismount(mount):
                Utils.call(['umount', '-f', mount], stderr=subprocess.DEVNULL)
                print(f"  Demonte : {mount}")
        self._remove_fstab_block()
        print("Entrees supprimees de /etc/fstab")


# ═════════════════════════════════════════════════════════════════════════════
# Collecte interactive de la configuration
# ═════════════════════════════════════════════════════════════════════════════
class StorageConfigCollector:

    def __init__(self):
        self.detector = StorageDetector()

    def collect(self) -> StorageConfig:
        cfg = StorageConfig()
        Utils.hr("CONFIGURATION DU STOCKAGE SAN FC")

        # Détection des LUNs
        luns = self.detector.detect_fc_luns()
        print(f"\n{len(luns)} LUN(s) detecte(s) :")
        self.detector.show_luns(luns)

        if not luns:
            print("\nAucun LUN detecte automatiquement.")
            cfg.devices = self._ask_manual_devices()
        else:
            cfg.devices, cfg.wwids, cfg.mpath_names = self._select_luns(luns)

        # Striping ?
        if len(cfg.devices) > 1:
            if Utils.confirm(f"\nActiver le striping LVM sur {len(cfg.devices)} LUNs ? (o/n) : "):
                cfg.stripe_count = len(cfg.devices)
                print(f"  Striping actif sur {cfg.stripe_count} devices.")

        # VG/LV
        cfg.vg_name      = Utils.ask("\nNom du Volume Group (ex: vg_garage) : ", "vg_garage")
        cfg.lv_data_name = Utils.ask("Nom du LV donnees (ex: lv_data) : ", "lv_data")
        cfg.lv_meta_name = Utils.ask("Nom du LV metadonnees (ex: lv_meta) : ", "lv_meta")

        # Tailles
        total = self._get_total_size_gb(cfg.devices)
        print(f"\nCapacite totale disponible : ~{total} GB")
        cfg.lv_meta_size = Utils.ask("Taille du LV metadonnees (ex: 50G) : ", "50G")
        cfg.lv_data_size = Utils.ask(
            f"Taille du LV donnees (ex: {max(1, total-60)}G ou 100%FREE) : ",
            f"{max(1, total-60)}G"
        )

        # Filesystem
        print("\nFilesystems disponibles : xfs, ext4, btrfs")
        cfg.fs_data = Utils.ask("Filesystem pour les donnees (xfs recommande) : ", "xfs")
        cfg.fs_meta = Utils.ask("Filesystem pour les metadonnees (ext4 recommande) : ", "ext4")

        # Points de montage
        cfg.mount_data = Utils.ask("\nPoint de montage donnees : ", "/data")
        cfg.mount_meta = Utils.ask("Point de montage metadonnees : ", "/data/meta")

        # Résumé
        self._show_summary(cfg)
        if not Utils.confirm("\nConfirmer la configuration ? (o/n) : "):
            print("Configuration annulee.")
            sys.exit(0)

        return cfg

    def _select_luns(self, luns: list) -> tuple:
        devices, wwids, names = [], [], []
        if len(luns) == 1:
            print("\nUn seul LUN detecte, selection automatique.")
            devices.append(luns[0]['device'])
            wwids.append(luns[0].get('wwid', ''))
            names.append(luns[0].get('name', ''))
            return devices, wwids, names

        print("\nSelectionner les LUNs a utiliser (ex: 0 1 2 ou 'tous') :")
        choice = input("Numeros des LUNs : ").strip().lower()
        if choice == 'tous':
            indices = range(len(luns))
        else:
            try:
                indices = [int(x) for x in choice.split()]
            except ValueError:
                print("Selection invalide, utilisation du premier LUN.")
                indices = [0]

        for i in indices:
            if 0 <= i < len(luns):
                devices.append(luns[i]['device'])
                wwids.append(luns[i].get('wwid', ''))
                names.append(luns[i].get('name', ''))

        return devices, wwids, names

    def _ask_manual_devices(self) -> list:
        print("Saisissez les devices manuellement (ex: /dev/sdb /dev/sdc)")
        raw = input("Devices (separes par des espaces) : ").strip()
        devices = raw.split()
        valid = []
        for d in devices:
            if os.path.exists(d):
                valid.append(d)
            else:
                print(f"  Attention : {d} introuvable, ignore.")
        if not valid:
            print("Aucun device valide. Abandon.")
            sys.exit(1)
        return valid

    def _get_total_size_gb(self, devices: list) -> int:
        total = 0
        for dev in devices:
            try:
                size_bytes = int(Utils.run_out(
                    ['blockdev', '--getsize64', dev], stderr=subprocess.DEVNULL
                ))
                total += size_bytes // (1024 ** 3)
            except Exception:
                pass
        return total

    def _show_summary(self, cfg: StorageConfig):
        Utils.hr("RESUME DE LA CONFIGURATION")
        print(f"  Devices       : {', '.join(cfg.devices)}")
        print(f"  Striping      : {'oui (' + str(cfg.stripe_count) + ' devices)' if cfg.stripe_count > 1 else 'non'}")
        print(f"  VG            : {cfg.vg_name}")
        print(f"  LV donnees    : {cfg.lv_data_name} ({cfg.lv_data_size}) [{cfg.fs_data}] → {cfg.mount_data}")
        print(f"  LV meta       : {cfg.lv_meta_name} ({cfg.lv_meta_size}) [{cfg.fs_meta}] → {cfg.mount_meta}")


# ═════════════════════════════════════════════════════════════════════════════
# Orchestrateur Setup
# ═════════════════════════════════════════════════════════════════════════════
class StorageSetup:

    def run(self):
        cfg = StorageConfigCollector().collect()

        multipath = MultipathConfigurator()
        lvm       = LVMConfigurator()
        fs        = FilesystemConfigurator()

        multipath.setup(cfg)
        lvm.setup(cfg)
        fs.setup(cfg)

        self._print_summary(cfg)

    def _print_summary(self, cfg: StorageConfig):
        Utils.hr("STOCKAGE CONFIGURE")
        print(f"  Donnees    : {cfg.mount_data}  ({cfg.fs_data})")
        print(f"  Metadonnees: {cfg.mount_meta}  ({cfg.fs_meta})")
        print(f"\nVous pouvez maintenant lancer l'installation de Garage :")
        print(f"  python3 install.py --install")
        print(f"\n  → Donnees    : {cfg.mount_data}")
        print(f"  → Metadonnees: {cfg.mount_meta}")


# ═════════════════════════════════════════════════════════════════════════════
# Orchestrateur Teardown
# ═════════════════════════════════════════════════════════════════════════════
class StorageTeardown:

    def run(self, keep_data: bool = False):
        Utils.hr("SUPPRESSION DU STOCKAGE")

        cfg = self._build_cfg_from_fstab()

        if not cfg:
            print("Impossible de lire la configuration depuis /etc/fstab.")
            cfg = StorageConfig()
            cfg.vg_name    = Utils.ask("Nom du VG a supprimer : ", "vg_garage")
            cfg.mount_data = Utils.ask("Point de montage donnees : ", "/data")
            cfg.mount_meta = Utils.ask("Point de montage metadonnees : ", "/data/meta")
            cfg.devices    = self._get_pv_devices(cfg.vg_name)

        if not keep_data:
            print("\n  ATTENTION : toutes les donnees seront supprimees !")
            if not Utils.confirm("Confirmer la suppression ? (o/n) : "):
                print("Suppression annulee.")
                return

        fs        = FilesystemConfigurator()
        lvm       = LVMConfigurator()
        multipath = MultipathConfigurator()

        fs.teardown(cfg)
        lvm.teardown(cfg)
        multipath.teardown()

        print("\nStockage supprime.")

    def _build_cfg_from_fstab(self) -> Optional[StorageConfig]:
        """Reconstruit la config depuis /etc/fstab."""
        if not os.path.isfile(FSTAB):
            return None
        try:
            with open(FSTAB, 'r') as f:
                content = f.read()
            if FSTAB_MARKER not in content:
                return None

            cfg = StorageConfig()
            # Extrait les points de montage
            lines = [l for l in content.splitlines()
                     if FSTAB_MARKER not in l and 'END GARAGE' not in l
                     and l.strip() and not l.startswith('#')]
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    if 'data' in parts[1] and 'meta' not in parts[1]:
                        cfg.mount_data = parts[1]
                        cfg.fs_data    = parts[2]
                    elif 'meta' in parts[1]:
                        cfg.mount_meta = parts[1]
                        cfg.fs_meta    = parts[2]

            # Devine le VG depuis les LVs montés
            try:
                out = Utils.run_out(['lvs', '--noheadings', '-o', 'vg_name'], stderr=subprocess.DEVNULL)
                vgs = list(set(out.split()))
                if vgs:
                    cfg.vg_name = vgs[0]
                    cfg.devices = self._get_pv_devices(cfg.vg_name)
            except Exception:
                pass

            return cfg
        except Exception:
            return None

    def _get_pv_devices(self, vg_name: str) -> list:
        try:
            out = Utils.run_out(
                ['pvs', '--noheadings', '-o', 'pv_name', '--select', f'vg_name={vg_name}'],
                stderr=subprocess.DEVNULL
            )
            return [d.strip() for d in out.splitlines() if d.strip()]
        except Exception:
            return []


# ═════════════════════════════════════════════════════════════════════════════
# Affichage du statut
# ═════════════════════════════════════════════════════════════════════════════
class StorageStatus:

    def show(self):
        Utils.hr("STATUT DU STOCKAGE")

        print("\n--- Multipath ---")
        Utils.call(['multipath', '-ll'])

        print("\n--- LVM ---")
        Utils.call(['pvs'])
        Utils.call(['vgs'])
        Utils.call(['lvs'])

        print("\n--- Filesystems montes ---")
        Utils.call(['df', '-h', '-t', 'xfs', '-t', 'ext4', '-t', 'btrfs'])

        print("\n--- HBA Fibre Channel ---")
        self._show_fc_hba()

    def _show_fc_hba(self):
        hba_path = "/sys/class/fc_host"
        if not os.path.isdir(hba_path):
            print("  Aucun HBA FC detecte.")
            return
        for hba in os.listdir(hba_path):
            wwpn_file = f"{hba_path}/{hba}/port_name"
            state_file = f"{hba_path}/{hba}/port_state"
            try:
                wwpn  = open(wwpn_file).read().strip()
                state = open(state_file).read().strip()
                print(f"  {hba} : WWPN={wwpn}  etat={state}")
            except Exception:
                print(f"  {hba} : informations indisponibles")


# ═════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Configuration du stockage SAN FC pour Garage",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--setup',    action='store_true', help='Configurer le stockage SAN FC')
    group.add_argument('--teardown', action='store_true', help='Supprimer le stockage')
    group.add_argument('--status',   action='store_true', help='Afficher le statut du stockage')
    parser.add_argument('--keep-data', action='store_true',
                        help='Conserver les donnees lors du teardown')
    args = parser.parse_args()

    Utils.check_root()
    Utils.check_deps(['lsblk', 'blockdev'])

    if args.setup:
        StorageSetup().run()
    elif args.teardown:
        StorageTeardown().run(keep_data=args.keep_data)
    elif args.status:
        StorageStatus().show()


if __name__ == "__main__":
    main()