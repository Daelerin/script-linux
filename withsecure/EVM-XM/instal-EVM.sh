#!/bin/sh
apt update
echo "installation des dépendances"

version_id=$(grep VERSION_ID /etc/os-release | cut -d '=' -f 2- | tr -d '"')

apt install -y libx11-xcb1 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libnss3 libxss1 libssl1.1 libreadline7
wget -O /tmp/packages-microsft-prod.deb https://packages.microsoft.com/config/debian/$version_id/packages-microsoft-prod.deb
wget -O /tmp/libffi6.deb http://ftp.de.debian.org/debian/pool/main/libf/libffi/libffi6_3.2.1-9_amd64.deb
wget -O /tmp/libpython2.7-stdlib_2.7.16-2+deb10u1_amd64.deb http://ftp.de.debian.org/debian/pool/main/p/python2.7/libpython2.7-stdlib_2.7.16-2+deb10u1_amd64.deb
wget -O /tmp/python2.7-minimal_2.7.16-2+deb10u1_amd64.deb http://ftp.de.debian.org/debian/pool/main/p/python2.7/python2.7-minimal_2.7.16-2+deb10u1_amd64.deb
wget -O /tmp/python2.7_2.7.18-8+deb11u1_amd64.deb http://ftp.de.debian.org/debian/pool/main/p/python2.7/python2.7_2.7.18-8+deb11u1_amd64.deb

dpkg -i /tmp/packages-microsoft-prod.deb
apt update
apt install -y powershell
apt install /tmp/libffi6.deb
apt install /tmp/libpython2.7-stdlib_2.7.16-2+deb10u1_amd64.deb
apt install /tmp/python2.7-minimal_2.7.16-2+deb10u1_amd64.deb
apt install /tmp/python2.7_2.7.18-8+deb11u1_amd64.deb

echo "Récupération de l'installeur"
wget -O /tmp/installer.deb https://updates-api.radar-prd.fsapi.com/api/1.1/ProductUpdates/Components/ScanNodeAgent/Releases/4.0.0.0/Download
echo "Installation de l'agent, pensez a metre en place le fichier de licences"
apt install /tmp/installer.deb
echo "Installation terminée"
#echo "Entrez le chemin pour le fichier de lincences ainsi que sont nom"
#read chemin
#if [ -f "$chemin" ]; then
#    bash /opt/f-secure/radar-scannodeagent/ScanNodeAgent apply-license "$chemin"
#else 
#    echo "Fichier de licences introuvable"
#fi

echo "Nettoyage en cours"
rm  /tmp/*.deb

echo "Nettoyage terminéeé"