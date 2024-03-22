#!/bin/bash

# installation de curl si il n'est pas présent
if ! command -v curl &> /dev/null
then
    echo "Installation de curl"
    distribution=$(lsb_release -i -s)
    if [ "$distribution" = "Ubuntu" ] || [ "$distribution" = "Debian" ]; then
        apt update
        apt install -y curl
    elif [ "$distribution" = "CentOS" ] || [ "$distribution" = "RedHat" ]; then
        yum install -y curl
    else
        echo "La distribution $distribution n'est pas prise en charge pour l'installation de curl."
        exit 1
    fi
fi

# gestion des signaux
trap 'echo "Signal SIGINT, SIGOUT ou SIGTERM reçu. Sortie..."; exit 1' SIGINT SIGOUT SIGTERM

printf "Backup des fichiers de configuration, du répertoire 'files', du marketplace et des plugins\n"

backup_dir="$HOME/backup"
mkdir -p "$backup_dir"

date_suffix=$(date +"%Y-%m-%d_%H-%M-%S")
archive_name="$backup_dir/backup-$date_suffix.tar.gz"

tar -czf "$archive_name" /var/www/glpi/config
tar -czf "$archive_name" /var/www/glpi/files
tar -czf "$archive_name" /var/www/glpi/marketplace
tar -czf "$archive_name" /var/www/glpi/plugins

printf "Archive de backup créée : %s\n" "$archive_name"

printf "Téléchargement de la mise à jour \n"
tmpdir="$TMPDIR"
# Récupère l'URL de la dernière version disponible dans le dépôt GitHub de GLPI
maj_url=$(curl -s "https://api.github.com/repos/glpi-project/glpi/releases/latest" | grep -o 'https.*tgz' | head -n 1)
wget -O "$tmpdir/glpi.tgz" "$maj_url" || { echo "Échec du téléchargement de la mise à jour"; exit 1; }

printf "Extraction de la mise à jour vers /var/www/glpi/\n"
cd /var/www || { echo "Le répertoire de GLPI n'existe pas"; exit 1; }
if [ -d "glpi" ]; then
    cd glpi || { echo "Le répertoire de GLPI n'existe pas"; exit 1; }
    tar -zxf "$tmpdir/glpi.tgz" --strip-components 1 || { echo "Échec de l'extraction de la mise à jour"; exit 1; }
    rm "$tmpdir/glpi.tgz"
else
    echo "Le répertoire de GLPI n'existe pas";
fi

printf "Rapatriment des backups\n"
cd /var/www/glpi || { echo "Le répertoire de GLPI n'existe pas"; exit 1; }
if [ -f "$backup_dir/backup-$date_suffix.tar.gz" ]; then
    tar -zxf "$backup_dir/backup-$date_suffix.tar.gz" || { echo "Échec de la restauration de la sauvegarde"; exit 1; }
    chmod -R www-data:www-data /var/www/glpi/
else
    echo "Aucune sauvegarde trouvée avec le suffixe $date_suffix";
fi

printf "Mise à jour du backend terminée passée par l'interface web pour la suite. \n"

# On demande à l'utilisateur s'il veut supprimer les sauvegardes
echo "Voulez-vous supprimer les sauvegardes ? (o/n)"
read answer
if [[ $answer =~ ^[oO]$ ]]; then
    if [ -d "$backup_dir" ]; then
        printf "Suppression de tous les fichiers de backup.\n"
        rm -f "$backup_dir"/*
    else
        echo "Le répertoire de backup n'existe pas";
    fi
fi

exit 0;