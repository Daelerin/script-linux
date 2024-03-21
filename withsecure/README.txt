Attention a bien renseigné la variable "subkey" avec la clé de license désiré

Par convenance pensé à placé les script utilisé dans le répertoire /tmp et a changé les droits :
chown root:root script.sh
chmod u+x script.sh 

Une fois les droits OK et la clé renseigné il suffit de lancé le script en root
./script.sh

Le script uninstall-ws.sh désinstalle le paquet et purge les répertoire ce qui entraine la suppresion de toutes les données