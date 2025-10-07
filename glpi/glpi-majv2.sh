#!/bin/bash

# Installation de curl si non présent
if ! command -v curl &>/dev/null; then
    echo "Installation de curl"
    if command -v lsb_release &>/dev/null; then
        distribution=$(lsb_release -i -s)
    elif [ -f /etc/os-release ]; then
        distribution=$(grep ^ID= /etc/os-release | cut -d= -f2 | tr -d '"')
    else
        echo "Impossible de détecter la distribution."
        exit 1
    fi

    if [[ "$distribution" =~ ^(Ubuntu|Debian|debian|ubuntu)$ ]]; then
        apt update
        apt install -y curl
    elif [[ "$distribution" =~ ^(CentOS|centos|RedHat|redhat|rhel|almalinux|rocky)$ ]]; then
        yum install -y curl
    else
        echo "La distribution $distribution n'est pas prise en charge pour l'installation de curl."
        exit 1
    fi
fi

trap 'echo "Signal SIGINT, SIGTERM ou SIGQUIT reçu. Sortie..."; exit 1' SIGINT SIGTERM SIGQUIT

echo "Backup des fichiers de configuration, du répertoire 'files', du marketplace et des plugins"
backup_dir="$HOME/backup"
mkdir -p "$backup_dir"
date_suffix=$(date +"%Y-%m-%d_%H-%M-%S")
archive_name="$backup_dir/backup-$date_suffix.tar.gz"

tar -czf "$archive_name" \
    /var/www/glpi/config \
    /var/www/glpi/files \
    /var/www/glpi/marketplace \
    /var/www/glpi/plugins

echo "Archive de backup créée : $archive_name"

echo "Téléchargement de la mise à jour"
tmpdir="${TMPDIR:-/tmp}"
mkdir -p "$tmpdir"

maj_url=$(curl -s "https://api.github.com/repos/glpi-project/glpi/releases/latest" | grep -o 'https[^"]*tgz' | head -n 1)
if [ -z "$maj_url" ]; then
    echo "Impossible de récupérer l'URL de la dernière version."
    exit 1
fi

wget -O "$tmpdir/glpi.tgz" "$maj_url" || { echo "Échec du téléchargement de la mise à jour"; exit 1; }

echo "Arrêt du service web"
systemctl stop apache2

cd /var/www || { echo "Le répertoire /var/www n'existe pas"; exit 1; }

if [ -d "glpi" ]; then
    mv glpi "glpi.old_$date_suffix"
    mkdir glpi
    tar -zxf "$tmpdir/glpi.tgz" -C glpi --strip-components=1 || { echo "Échec de l'extraction de la mise à jour"; exit 1; }
    cp -r "glpi.old_$date_suffix/config" glpi/
    cp -r "glpi.old_$date_suffix/files" glpi/
    cp -r "glpi.old_$date_suffix/marketplace" glpi/
    cp -r "glpi.old_$date_suffix/plugins" glpi/
    chown -R www-data:www-data glpi/
else
    echo "Le répertoire de GLPI n'existe pas."
    exit 1
fi

rm -f "$tmpdir/glpi.tgz"
systemctl start apache2

echo "Mise à jour prête. Lance GLPI via navigateur ou exécute php bin/console db:update pour finir la migration."

read -p "Voulez-vous supprimer l'ancien dossier GLPI (glpi.old_$date_suffix) ? (o/n) " cleanup
if [[ $cleanup =~ ^[oO]$ ]]; then
    rm -rf "/var/www/glpi.old_$date_suffix"
    echo "Ancien dossier GLPI supprimé."
fi

read -p "Voulez-vous supprimer les backup ? (o/n) " answer
if [[ $answer =~ ^[oO]$ ]]; then
    if [ -d "$backup_dir" ]; then
        echo "Suppression de tous les fichiers de backup."
        rm -f "$backup_dir"/*
    else
        echo "Le répertoire de backup n'existe pas."
    fi
fi

exit 0
