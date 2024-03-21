#!/bin/sh
CHEMIN="/home/stg/backup/wiki"

latest_backup=$(ls -lrt $CHEMIN | grep ".tar.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
tar -zxvf $CHEMIN/$latest_backup -C /

user="-uyouruser"
mdp="-pyourpassword"
bdd="yourdb"

latest_db=$(ls -lrt $CHEMIN | grep ".sql.gz" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
gunzip $CHEMIN/$latest_db
echo $latest_db


latest_sql=$(ls -lrt $CHEMIN | grep ".sql" | tail -n 1 | cut -d ":" -f 2 | cut -d " " -f 2);
mysql $user $mdp $bdd < $CHEMIN/$latest_sql
echo $latest_sql

