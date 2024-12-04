#!/bin/bash

# Définir le chemin du fichier de sauvegarde
BACKUP_FILE="/etc/nftables.conf"

# Fonction pour vérifier la présence de règles nftables
check_existing_rules() {
    if nft list ruleset | grep -q "table"; then
        return 0  # Des règles existent
    else
        return 1  # Aucune règle n'existe
    fi
}

# Fonction pour demander à l'utilisateur s'il veut supprimer les règles existantes
ask_flush_ruleset() {
    read -p "Des règles nftables existantes ont été détectées. Voulez-vous les supprimer ? (o/n) " choice
    case "$choice" in 
        o|O ) return 0 ;;
        n|N ) return 1 ;;
        * ) echo "Réponse non valide. Veuillez répondre par 'o' ou 'n'."; ask_flush_ruleset ;;
    esac
}

# Vérification des règles existantes
if check_existing_rules; then
    if ask_flush_ruleset; then
        echo "Suppression des règles existantes..."
        nft flush ruleset
    else
        echo "Conservation des règles existantes. Ajout des nouvelles règles..."
    fi
else
    echo "Aucune règle existante détectée. Configuration d'un nouveau jeu de règles..."
fi

# Configuration des nouvelles règles
echo "Configuration des règles pour FTPS et SFTP..."

# Créer une nouvelle table et une chaîne pour le trafic entrant
nft add table inet filter 2>/dev/null
nft add chain inet filter input { type filter hook input priority 0\; policy drop\; } 2>/dev/null

# Ajouter les règles
nft add rule inet filter input iifname "lo" accept
nft add rule inet filter input ct state established,related accept
nft add rule inet filter input ct state invalid drop

# Règles FTPS
nft add rule inet filter input tcp dport 990 comment "FTPS control channel" accept
nft add rule inet filter input tcp dport 30000-31000 comment "FTPS passive mode" accept

# Règles SSH/SFTP
nft add rule inet filter input tcp dport 22 comment "SSH/SFTP" accept

# Bloquer explicitement FTP non sécurisé
nft add rule inet filter input tcp dport 21 comment "Block FTP" drop

# Ajout d'une règle de journalisation avant le drop final
nft add rule inet filter input counter log prefix \"Dropped Input: \" level debug

echo "Configuration terminée. Voici les règles actuelles :"
nft list ruleset

# Sauvegarde des règles
echo "Sauvegarde des règles dans $BACKUP_FILE..."
nft list ruleset > $BACKUP_FILE
if [ $? -eq 0 ]; then
    echo "Les règles ont été sauvegardées avec succès."
else
    echo "Erreur lors de la sauvegarde des règles."
fi

# Instructions finales
echo "Pour activer le service nftables au démarrage :"
echo "sudo systemctl enable nftables"
echo "sudo systemctl start nftables"