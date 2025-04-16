#!/bin/bash
set -euo pipefail

# Vérification des dépendances
for cmd in wget dpkg sed getent id chmod chown mv mkdir ip awk cut head; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "$cmd est requis mais non trouvé."; exit 1; }
done

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

# Sécurisation du fichier d'environnement
chmod 640 "$var_defaut"
chown root:minio-user "$var_defaut"

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
sed -i "s/^MINIO_ROOT_USER=.*/MINIO_ROOT_USER=\"$user\"/" "$var_defaut" || { echo "Erreur lors de la modification de MINIO_ROOT_USER."; exit 1; }
sed -i "s/^MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=\"$password\"/" "$var_defaut" || { echo "Erreur lors de la modification de MINIO_ROOT_PASSWORD."; exit 1; }
sed -i "s|^MINIO_VOLUMES=.*|MINIO_VOLUMES=\"$repo\"|" "$var_defaut" || { echo "Erreur lors de la modification de MINIO_VOLUMES."; exit 1; }

# Création du certificat auto-signé
CERTGEN="/tmp/certgen-linux-amd64"
wget -qO "$CERTGEN" "https://github.com/minio/certgen/releases/latest/download/certgen-linux-amd64" || { echo "Échec du téléchargement de certgen."; exit 1; }
chmod +x "$CERTGEN"

# Détection automatique ou saisie de l'adresse IP
read -rp "Voulez vous detectez automatiquement l'adresse IP (o/n) : " multi_ip

if [[ "$multi_ip" =~ ^[Nn]$ ]]; then
  # L'utilisateur souhaite choisir l'IP manuellement
  while true; do
    read -rp "Quelle est l'IP de votre serveur ? : " address
    if [[ "$address" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
      OIFS=$IFS; IFS='.' read -r o1 o2 o3 o4 <<< "$address"; IFS=$OIFS
      if ((o1 >= 0 && o1 <= 255 && o2 >= 0 && o2 <= 255 && o3 >= 0 && o3 <= 255 && o4 >= 0 && o4 <= 255)); then
        break
      fi
    fi
    echo "Adresse IP invalide, veuillez réessayer."
  done
else
  # Détection automatique avec validation utilisateur
  while true; do
    address=$(ip -o -4 addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1)
    echo "Adresse IP détectée automatiquement : $address"
    read -rp "Validez-vous cette IP ? (o/n) : " valid
    if [[ "$valid" =~ ^[Oo]$ ]]; then
      break
    else
      read -rp "Veuillez saisir l'adresse IP à utiliser : " address
      if [[ "$address" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        OIFS=$IFS; IFS='.' read -r o1 o2 o3 o4 <<< "$address"; IFS=$OIFS
        if ((o1 >= 0 && o1 <= 255 && o2 >= 0 && o2 <= 255 && o3 >= 0 && o3 <= 255 && o4 >= 0 && o4 <= 255)); then
          break
        fi
      fi
      echo "Adresse IP invalide, veuillez réessayer."
    fi
  done
fi

else
  # Détection automatique de la première IP locale
  address=$(ip -o -4 addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1)
  echo "Adresse IP détectée automatiquement : $address"
fi

"$CERTGEN" -host "127.0.0.1,localhost,$address"

# Préparation du dossier certs
CERT_DIR="/home/minio-user/.minio/certs"
mkdir -p "$CERT_DIR"
mv public.crt "$CERT_DIR" || { echo "Erreur lors du déplacement de public.crt."; exit 1; }
mv private.key "$CERT_DIR" || { echo "Erreur lors du déplacement de private.key."; exit 1; }
chown -R minio-user:minio-user "/home/minio-user/.minio"

# Nettoyage des fichiers temporaires
rm -f "$MINIO_DEB" "$CERTGEN"

echo "Installation complète. Voici les dernières lignes du journal MinIO :"
journalctl -xeu minio -n 7

echo "Accédez à la console MinIO avec :"
echo "  Utilisateur : $user"
echo "  Mot de passe : (celui que vous avez choisi)"
