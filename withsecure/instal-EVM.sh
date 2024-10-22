#!/bin/sh
apt update 
echo "installation des dépendances"

apt install -y libx11-xcb1 libxrandr2 libasound2 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 libnss3 libxss1
wget -o /tmp/ https://github.com/PowerShell/PowerShell/releases/download/v7.4.5/powershell_7.4.5-1.deb_amd64.deb
wget -o /tmp/ http://ftp.de.debian.org/debian/pool/main/p/python2.7/libpython2.7-stdlib_2.7.16-2+deb10u1_amd64.deb
wget -o /tmp/ http://ftp.de.debian.org/debian/pool/main/p/python2.7/python2.7-minimal_2.7.16-2+deb10u1_amd64.deb
wget -o /tmp/ http://ftp.de.debian.org/debian/pool/main/p/python2.7/python2.7_2.7.18-8+deb11u1_amd64.deb
dpkg -i /tmp/powershell_7.4.5-1.deb_amd64.deb
dpkg -i /tmp/libpython2.7-stdlib_2.7.16-2+deb10u1_amd64.deb
dpkg -i /tmp/python2.7-minimal_2.7.16-2+deb10u1_amd64.deb
dpkg -i /tmp/python2.7_2.7.18-8+deb11u1_amd64.deb