#!/bin/sh
apt update
echo "installation des dépendances"

version_id=$(grep VERSION_ID /etc/os-release | cut -d '=' -f 2- | tr -d '"')

apt install -y libx11-xcb1 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libnss3 libxss1 
wget -O /tmp/packages-microsoft-prod.deb https://packages.microsoft.com/config/debian/$version_id/packages-microsoft-prod.deb

dpkg -i /tmp/packages-microsoft-prod.deb
apt update
apt install -y powershell

echo "Récupération de l'installeur"
wget -O /tmp/installer.deb https://updates-api.radar-prd.fsapi.com/api/1.1/ProductUpdates/Components/ScanNodeAgent/Releases/4.0.0.0/Download
echo "Installation de l'agent, pensez a metre en place le fichier de licences"
apt install -y /tmp/installer.deb
echo "Installation terminée"

#echo "Nettoyage en cours"
#rm  /tmp/*.deb

#echo "Nettoyage terminéeé"