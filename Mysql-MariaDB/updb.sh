#!/bin/bash

# Demandez à l'utilisateur le chemin de la sauvegarde
echo -n "Entrez le chemin vers votre backup: "
read CHEMIN

# Demandez à l'utilisateur son nom d'utilisateur, son mot de passe et le nom de sa base de données
echo -n "Entrez le nom de votre utilisateur : "
read user

echo -n "Entrez le mot de passe pour l'utilisateur $user : "
read -s passwd
echo

echo -n "Entrez la basse de donnée : "
read dbname

# Vérifiez si le chemin existe
if [ ! -d "$CHEMIN" ]; then
    echo "Le chemin $CHEMIN n'existe pas."
    exit 1
fi

# Trouvez le fichier .sql le plus récent dans le répertoire de sauvegarde
latest_db=$(ls -lrt "$CHEMIN" | grep "\.sql\.gz" | tail -n 1 | awk '{print $9}')

# Vérifiez si un fichier .sql.gz a été trouvé
if [ -z "$latest_db" ]; then
    echo "Aucun fichier .sql.gz n'a été trouvé dans le répertoire $CHEMIN."
    exit 1
fi

# Décompressez le fichier .sql.gz le plus récent
gunzip "$CHEMIN/$latest_db"

# Trouvez le fichier .sql le plus récent dans le répertoire de sauvegarde
latest_sql=$(ls -lrt "$CHEMIN" | grep "\.sql" | tail -n 1 | awk '{print $9}')

# Importez le fichier .sql le plus récent dans la base de données spécifiée
echo "Importation de la sauvegarde $latest_sql dans la base de données $dbname..."
mysql $user:$passwd@$dbname < "$CHEMIN/$latest_sql"

# Vérifiez si l'importation s'est déroulée sans erreur
if [ $? -eq 0 ]; then
    echo "La sauvegarde a été importée avec succès."
else
    echo "Une erreur s'est produite lors de l'importation de la sauvegarde."
fi

# Trapez SIGINT et affichez un message d'avertissement
trap 'echo "Interruption détectée. Le script va se terminer."; exit 1' SIGINT