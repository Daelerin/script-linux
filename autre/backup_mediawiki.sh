 #!/bin/sh
  # script de sauvegarde automatique (FL)
  # Définition des variables
  #
  path_wiki=""
  path_backup="your/path/to/store/backup"
  user="-uyouruser"
  mdp="yourpassword"
  bdd="yourdb"
  optdump="--default-character-set=latin1"
  #
  # Utilisation de la variable $wgReadOnly afin de bloquer les écriture pendant la sauvegarde
  #
  cp -p $path_wiki/LocalSettings.php $path_wiki/LocalSettings.php.bak
  echo '$wgReadOnly = "Sauvegarde de la base de donnee, les acces seront retablis des que possible"' >> $path_wiki/LocalSettings.php
  #
  # dump de la base de donnée
  #
  mysqldump $user $mdp $optdump $bdd | gzip > $path_backup/wiki$(date '+%Y%m%d').sql.gz
  #
  # Backup des fichiers
  #
  tar -zcvf  $path_backup/wiki$(date '+%Y%m%d').tar.gz $path_wiki/images/
  #
  # Rétablissement du médiawiki en écriture
  #
  mv $path_wiki/LocalSettings.php.bak $path_wiki/LocalSettings.php
  $(./nb-arch.sh) && (./rsync-wiki.sh)
