#!/bin/sh

# Vérification de l'existence du répertoire /opt/f-secure/fsbg
dir="/opt/f-secure/fsbg"
if [ -d "$dir" ] && [ "$(find "$dir" -maxdepth 1 -type f -o -type d -print -quit)" ]; then
    printf "Installation détectée, lancement de la désinstallation\n"
    # Suppression du paquet existant s'il est installé tout en gardant le contenu des répertoires pour la traçabilité
    dnf remove -y f-secure-linuxsecurity
else
    printf "Pas d'installation détectée\n"
fi

# Installation des dépendances si nécessaire
dnf makecache
if rpm -q libcurl fuse-libs python36 python39; then
    printf "Dépendances déjà installées\n"
else
    printf "Installation de la dépendance libcurl\n"
    dnf install -y libcurl fuse-libs python36 python39
fi

# Téléchargement du paquet depuis le site de F-Secure en le plaçant dans le répertoire /tmp
printf "Installation en cours\n"
wget -O /tmp/f-secure-linuxsecurity.rpm https://download.sp.f-secure.com/linuxsecurity64/f-secure-linuxsecurity.rpm

# Installation du paquet
rpm -i /tmp/f-secure-linuxsecurity.rpm

# Activation de la clé de licence
printf "Activation de la clé de licence\n"
# Assurez-vous de remplacer '<votreclé>' par votre clé de licence réelle
subkey=<votreclé>
/opt/f-secure/linuxsecurity/bin/activate --psb --subscription-key "$subkey"
