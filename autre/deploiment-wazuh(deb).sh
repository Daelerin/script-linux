#!/bin/bash
read -p "Quel est le nom du groupe auquel vous voulez ajouter cet agent ? : " group
read -p "Quel est l'adresse de votre manager ? : " manager
curl -so wazuh-agent.deb https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.4.5-1_amd64.deb && WAZUH_MANAGER=$manager WAZUH_AGENT_GROUP=$group WAZUH_AGENT_NAME=$(hostname) dpkg -i ./wazuh-agent.deb
systemctl start wazuh-agent