import subprocess
import logging
from typing import List
import os

# Configuration des logs
log_file_path = "/var/log/agent_upgrade.log"

# Vérifie si le répertoire /var/log existe et est accessible
if not os.path.exists("/var/log"):
    raise FileNotFoundError("Le répertoire /var/log n'existe pas.")
if not os.access("/var/log", os.W_OK):
    raise PermissionError("Impossible d'écrire dans le répertoire /var/log. Vérifiez les permissions.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

# Définition des chemins et commandes
path_tool = "/var/ossec/bin/agent_upgrade"
cmd_check_agent_update = f"{path_tool} -l"
cmd_run_agent_update = f"{path_tool} -a"

# Liste pour stocker les IDs des agents
agent_id: List[str] = []

def check_version_and_extract_ids() -> bool:
    """Vérifie les versions et extrait les IDs des agents obsolètes"""
    try:
        global agent_id
        agent_id.clear()  # Réinitialise la liste à chaque exécution
        
        check_agent = subprocess.run(
            cmd_check_agent_update,
            shell=True,
            capture_output=True,
            text=True
        )

        if check_agent.returncode != 0:
            logging.error(f"Erreur de commande : {check_agent.stderr}")
            return False

        output = check_agent.stdout
        logging.debug("Sortie brute de la commande :\n%s", output)

        if "All agents are updated." in output:
            logging.info("Tous les agents sont déjà à jour")
            return False

        # Extraction des IDs
        for line in output.splitlines():
            if line.strip() and line.split()[0].isdigit():
                agent_id.append(line.split()[0])
        
        logging.info("%d agents à mettre à jour trouvés", len(agent_id))
        return bool(agent_id)

    except Exception as e:
        logging.exception("Erreur lors de la vérision des versions")
        return False

def agent_upgrade() -> None:
    """Exécute la mise à jour des agents identifiés"""
    if not agent_id:
        logging.warning("Aucun ID d'agent à mettre à jour")
        return

    logging.info("Début des mises à jour pour %d agents", len(agent_id))
    
    for agent in agent_id:
        try:
            cmd = f"{cmd_run_agent_update} {agent}"
            logging.debug("Exécution de : %s", cmd)
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logging.info("Mise à jour réussie pour l'agent %s", agent)
            else:
                logging.error(
                    "Échec de la mise à jour pour %s : %s",
                    agent,
                    result.stderr.strip() or "Pas de message d'erreur"
                )

        except Exception as e:
            logging.exception("Erreur critique pendant la mise à jour de %s", agent)

if __name__ == "__main__":
    try:
        if check_version_and_extract_ids():
            logging.info("IDs à mettre à jour : %s", agent_id)
            agent_upgrade()
        else:
            logging.info("Aucune action nécessaire")
            
    except KeyboardInterrupt:
        logging.warning("Processus interrompu par l'utilisateur")
