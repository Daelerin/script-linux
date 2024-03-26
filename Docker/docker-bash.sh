#!/bin/bash

# Fonction pour attacher un conteneur et ouvrir l'invite de commandes interactive
function attach_container() {
  docker exec -ti $1 bash
}

# Afficher la liste des conteneurs en cours d'exécution
echo "Liste des conteneurs disponibles :"
containers=$(docker ps --format "{{.Names}} {{.Image}}")

# Paginer la liste si elle contient plus de 10 éléments
if [ $(echo "$containers" | wc -l) -gt 10 ]; then
  echo "$containers" | page
else
  echo "$containers"
fi

# Demander à l'utilisateur de choisir un conteneur
read -p "Veuillez choisir un conteneur (1-$(echo "$containers" | wc -l)) : " choix

# Vérifier si l'entrée de l'utilisateur est valide
if [ $choix -lt 1 ] || [ $choix -gt $(echo "$containers" | wc -l) ]; then
  echo "Option invalide. Veuillez sélectionner une option valide."
  exit 1
fi

# Obtenir le nom du conteneur et l'image sélectionnée
selected_container_index=$((choix - 1))
selected_container=$(echo "$containers" | awk -v i=$selected_container_index '{print $1}' | sed -n ${i}p)
selected_image=$(echo "$containers" | awk -v i=$selected_container_index '{print $2}' | sed -n ${i}p)

# Vérifier si le conteneur est en cours d'exécution
if [ "$(docker inspect -f "{{.State.Status}}" $selected_container)" != "running" ]; then
  echo "Le conteneur \"$selected_container\" ($selected_image) n'est pas actuellement en cours d'exécution."
  exit 1
else
  attach_container $selected_container
fi