#!/bin/sh
# Désintallation du paquet
echo "Désinstallation du paquet en cours"
dpkg -r f-secure-linuxsecurity

# Purge des répertoires
echo "Purges des répertoires en cours"
rm -rf /etc/opt/f-secure/baseguard
rm -rf /etc/opt/f-secure/fsbg
rm -rf /etc/opt/f-secure/linuxsecurity
rm -rf /opt/f-secure/baseguard
rm -rf /opt/f-secure/fsbg
rm -rf /opt/f-secure/linuxsecurity
rm -rf /var/opt/f-secure/baseguard
rm -rf /var/opt/f-secure/fsbg
rm -rf /var/opt/f-secure/linuxsecurity
echo "Désinstallation terminé"