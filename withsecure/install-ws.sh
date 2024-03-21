#!/bin/sh
apt update
apt install -y libcurl4 auditd libfuse2
# Téléchargement du paquet depuis le site de withsecure en le placant dans le répertoire /tmp
wget -O /tmp/f-secure-linuxsecurity.deb https://download.sp.f-secure.com/linuxsecurity64/f-secure-linuxsecurity.deb

# Installation du paquet
dpkg -i /tmp/f-secure-linuxsecurity.deb

# Activation de la clé 
# Si la distribution est trop récente cela peut généré une erreur il y a cependant un moyen de coutournement par exemple 
# mon serveur est en debian et with secure n'est pas encore compatible avec cette version il suffit d'ajouter cete option a la commande : --override-distro debian:11
# permetant ainsi de dire au script d'activation que vous avez un debian 11 et non un debian 12
subkey = <vorteclé>
/opt/f-secure/linuxsecurity/bin/activate --psb --subscription-key  $subkey