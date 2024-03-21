#!/bin/bash

# script de sauvegarde automatique

# Demande des variables à l'utilisateur
path_backup= "/tmp" # Chemin ou sera stocké le fichié de backup 
if [ ! -d "$path_backup" ]; then
    echo "Le chemin vers le dossier de sauvegarde doit être un dossier existant."
    exit 1
fi

echo -n "Entrez l'utilisateur MySQL: "
read user

echo -n "Entrez le mot de passe MySQL (masqué): "
read -s mdp
echo

echo -n "Entrez le nom de la base de données: "
read bdd

# Check de l'existance de la base de données
if ! mysql -u "$user" -p"$mdp" -e "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '$bdd';" > /dev/null 2>&1; then
    echo "La base de données spécifiée n'existe pas."
    exit 1
fi

# Trap interruptions du signal
trap cleanup SIGINT SIGTERM

cleanup() {
  echo "Interrupion, nettoyage encours..."
  exit 1
}

# Creation du fichier de backup
backup_file="$path_backup/bdd$(hostname)-$(date '+%Y%m%d').sql.gz"

# dump de la base de données
mysqldump --default-character-set=latin1 -u "$user" -p"$mdp" "$bdd" | gzip > "$backup_file"

if [ $? -eq 0 ]; then
    echo "La sauvegarde a été effectuée avec succès dans $backup_file"
    echo -n "supprésion du scipt"
    rm backup_bdd.sh
else
    echo "Une erreur s'est produite lors de la sauvegarde."
    exit 1
fi