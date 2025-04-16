#!/bin/bash

# Vérification des droits root
if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être exécuté en tant que root." >&2
  exit 1
fi

# Saisie du chemin du volume
read -rp "Entrez le chemin du volume : " repo

# Création du répertoire si besoin
if [[ ! -d "$repo" ]]; then
  echo "Le répertoire $repo n'existe pas, création..."
  mkdir -p "$repo" || { echo "Erreur lors de la création du répertoire."; exit 1; }
fi

# Création du groupe et de l'utilisateur si besoin
if ! getent group minio-user >/dev/null; then
  groupadd -r minio-user
fi
if ! id minio-user >/dev/null 2>&1; then
  useradd -r -g minio-user -s /sbin/nologin minio-user
fi
chown minio-user:minio-user "$repo"

# Installation du paquet MinIO
MINIO_DEB="/tmp/minio.deb"
wget -qO "$MINIO_DEB" "https://dl.min.io/server/minio/release/linux-amd64/archive/minio_20250408154124.0.0_amd64.deb" || { echo "Échec du téléchargement de MinIO."; exit 1; }
dpkg -i "$MINIO_DEB" || { echo "Échec de l'installation de MinIO."; exit 1; }

# Modification des variables d'environnement
var_defaut="/etc/default/minio"
if [[ ! -f "$var_defaut" ]]; then
  echo "Le fichier $var_defaut n'existe pas !"
  exit 1
fi

read -rp "Entrez le nom d'utilisateur admin pour la console : " user

# Saisie masquée du mot de passe
while true; do
  read -rsp "Entrez le mot de passe admin : " password
  echo
  read -rsp "Confirmez le mot de passe : " password2
  echo
  [[ "$password" == "$password2" ]] && break
  echo "Les mots de passe ne correspondent pas. Réessayez."
done

# Remplacement sécurisé dans le fichier d'environnement
sed -i "s/^MINIO_ROOT_USER=.*/MINIO_ROOT_USER=\"$user\"/" "$var_defaut"
sed -i "s/^MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=\"$password\"/" "$var_defaut"
sed -i "s|^MINIO_VOLUMES=.*|MINIO_VOLUMES=\"$repo\"|" "$var_defaut"

# Création du certificat auto-signé
CERTGEN="/tmp/certgen-linux-amd64"
wget -qO "$CERTGEN" "https://github.com/minio/certgen/releases/latest/download/certgen-linux-amd64" || { echo "Échec du téléchargement de certgen."; exit 1; }
chmod +x "$CERTGEN"

read -rp "Quelle est l'IP de votre serveur ? : " address
"$CERTGEN" -host "127.0.0.1,localhost,$address"

# Préparation du dossier certs
CERT_DIR="/home/minio-user/.minio/certs"
mkdir -p "$CERT_DIR"
mv public.crt "$CERT_DIR"
mv private.key "$CERT_DIR"
chown -R minio-user:minio-user "/home/minio-user/.minio"

echo "Installation complète. Voici les dernières lignes du journal MinIO :"
journalctl -xeu minio -n 7

echo "Accédez à la console MinIO avec :"
echo "  Utilisateur : $user"
echo "  Mot de passe : (celui que vous avez choisi)"
