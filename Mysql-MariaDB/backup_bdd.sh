#!/bin/bash

# script de sauvegarde automatique

# Demande des variables à l'utilisateur
echo -n "Entrez le chemin vers le dossier de sauvegarde: "
read path_backup
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
  echo "Interrupted, cleaning up..."
  exit 1
}

# Creation du fichier de backup
backup_file="$path_backup/bdd$(hostname)-$(date '+%Y%m%d').sql.gz"

# dump de la base de données
mysqldump --default-character-set=latin1 -u "$user" -p"$mdp" "$bdd" | gzip > "$backup_file"
tar -czf "$backup_file" "$path_backup/$bdd$(hostname)-$(date '+%Y%m%d').sql"

if [ $? -eq 0 ]; then
    echo "La sauvegarde a été effectuée avec succès dans $backup_file"
else
    echo "Une erreur s'est produite lors de la sauvegarde."
    exit 1
fi