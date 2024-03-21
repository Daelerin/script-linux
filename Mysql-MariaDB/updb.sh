#!/bin/sh
echo -n "Entrez le chemin vers votre backup"
read CHEMIN

latest_backup=$(ls -lrt $CHEMIN | grep ".tar.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
tar -zxvf $CHEMIN/$latest_backup -C /

echo -n "Entrez le nom de votre utilisateur : "
read user
echo -n "Entrez le mot de passe pour l'utilisateur $user"
read -s passwd
echo -n "Entrez la basse de donnée : "
read dbname

latest_db=$(ls -lrt $CHEMIN | grep ".sql.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
gunzip $CHEMIN/$latest_db
echo $latest_db


latest_sql=$(ls -lrt $CHEMIN | grep ".sql" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
mysql $user $mdp $bdd < $CHEMIN/$latest_sql
echo $latest_sql