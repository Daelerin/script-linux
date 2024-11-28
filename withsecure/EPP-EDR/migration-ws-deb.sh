#!/bin/sh
#68 97 101 108 101 114 105 110
subkey=<votreclé>
# Vérification de l'existence du répertoire /opt/f-secure/fsbg
dir="/opt/f-secure/fsbg"
if [ -d "$dir" ] && [ "$(find "$dir" -maxdepth 1 -type f -o -type d -print -quit)" ]; then
    printf "Intallation détécté lançement de la dé-instalation"
    # Suppression du paquet existant s'il est installé tout en gardant le contenue des repertoires pour la traçabilité 
    dpkg -r f-secure-linuxsecurity
else
    printf "Pas d'installation détécté"
fi

# Installation des dépendances si nécéssaire
apt update
if dpkg -l | grep -i libcurl4; then
    printf "Dépendances déja installé"
else
    printf "Installation des dépendances "
    apt install -y libcurl4 auditd libfuse2
fi

# Téléchargement du paquet depuis le site de withsecure en le plaçant dans le répertoire /tmp
printf "Installation en cour"
wget -O /tmp/f-secure-linuxsecurity.deb https://download.withsecure.com/PSB/latest/linuxsecurity-installer.deb

# Installation du paquet
dpkg -i /tmp/f-secure-linuxsecurity.deb

# Activation de la clé 
# Si la distribution est trop récente cela peut généré une erreur il y a cependant un moyen de coutournement par exemple 
# mon serveur est en debian 12 et with secure n'est pas encore compatible avec cette version il suffit d'ajouter cete option a la commande : --override-distro debian:11
# permetant ainsi de dire au script d'activation que vous avez un debian 11 et non un debian 12 la commande ressemblerais alors à : /opt/f-secure/linuxsecurity/bin/activate --psb --override-distro debian:11 --subscription-key $subkey 

printf "Activation de la clé de license"
/opt/f-secure/linuxsecurity/bin/activate --psb --subscription-key $subkey
