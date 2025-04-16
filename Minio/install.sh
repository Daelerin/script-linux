#!/bin/sh

echo "Entrez le chemin du volume"
read repo

# création de l'utilisateur et du groupe local
groupadd -r minio-user
useradd -r -g minio-user -s /sbin/nologin minio-user
chown minio-user:minio-user "$repo"

# installation du paquet
wget https://dl.min.io/server/minio/release/linux-amd64/archive/minio_20250408154124.0.0_amd64.deb -O /tmp/minio.deb
dpkg -i /tmp/minio.deb

# modification des variables d'environnement
var_defaut="/etc/default/minio"
echo "Entrez le nom d'utilisateur que vous voulez utiliser pour l'admin de la console"
read user
echo "Entrez le mot de passe que vous voulez utiliser"
read password

# Remplace uniquement la valeur après le =
sed -i "s/^MINIO_ROOT_USER=.*/MINIO_ROOT_USER=\"$user\"/" "$var_defaut"
sed -i "s/^MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=\"$password\"/" "$var_defaut"
sed -i "s/^MINIO_VOLUMES=.*/MINIO_VOLUMES=\"$repo\"/" "$var_defaut"

#Création du certificat auto-signé 
wget https://github.com/minio/certgen/releases/latest/download/certgen-linux-amd64 -O /tmp/certgen
echo"quelle est l'ip de votre serveur ? : "
read address
./certgen-linux-amd64 -host "127.0.0.1, localhost, $address"
mkdir /home/minio-user/.minio/certs
mv /tmp/public.crt /home/minio-user/.minio/certs
mv /tmp/private.key /home/minio-user/.minio/certs

echo "Installation complete voici les informations de connexion:" 
journalctl -xeu minio -n 7

