#!/bin/sh

# Demandez à l'utilisateur le chemin de la sauvegarde
echo -n "Entrez le chemin vers votre backup"
read CHEMIN

# Extrayez le fichier .tar.gz le plus récent dans le répertoire racine
latest_backup=$(ls -lrt $CHEMIN | grep ".tar.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2)
tar -zxvf $CHEMIN/$latest_backup -C /

# Demandez à l'utilisateur son nom d'utilisateur, son mot de passe et le nom de sa base de données
echo -n "Entrez le nom de votre utilisateur : "
read user
echo -n "Entrez le mot de passe pour l'utilisateur $user"
read -s passwd
echo -n "Entrez la basse de donnée : "
read dbname

# Importez le fichier .sql le plus récent dans la base de données spécifiée
latest_db=$(ls -lrt $CHEMIN | grep ".sql.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2)
gunzip $CHEMIN/$latest_db
mysql $user $passwd $dbname < $CHEMIN/$(ls -lrt $CHEMIN | grep ".sql" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2)