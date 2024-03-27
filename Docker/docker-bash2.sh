#!/bin/bash
# Fonction pour attacher un conteneur et ouvrir une invite de commandes interactive
function attach_container() {
  docker exec -ti $1 bash
}

# Afficher la liste des conteneurs en cours d'exécution
echo "Liste des conteneurs disponibles :"
containers=$(docker ps --format "{{.Names}} {{.Image}}")
# Tentative d'indexation 
index=1
for container in $containers 
do
  name=$(echo $container | awk '{print $1}')
  image=$(echo $container | awk '{print $2}')
  echo "$index. Nom: $name, Image: $image"
  ((index++))
done

# Afficher la liste paginée si elle contient plus de 10 éléments
if [ $(echo "$containers" | wc -l) -gt 10 ]; then
  echo "$containers" | less
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

# Option pour sélectionner le conteneur souhaité en se basant sur la valeur de choix
index_container_select=$(($choix - 1))
selected_container=$(awk -v i=$index_container_select '{ print $1 }' <<< "$containers")

# Entrer dans le conteneur
attach_container $selected_container

# Vérifier si le conteneur est en cours d'exécution
if [ "$(docker inspect -f "{{.State.Status}}" $selected_container)" != "running" ]; then
  echo "Le conteneur \"$selected_container\" ($selected_image) n'est pas actuellement en cours d'exécution."
  exit 1
else
  attach_container $selected_container
fi