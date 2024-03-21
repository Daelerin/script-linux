#!/bin/bash
group="srv-linux"
manager='siem.customer.fr'
curl -so wazuh-agent.deb https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.4.5-1_amd64.deb && WAZUH_MANAGER=$manager WAZUH_AGENT_GROUP=$group WAZUH_AGENT_NAME=$(hostname) dpkg -i ./wazuh-agent.deb
printf "l'agent est bien déployé avec le nom %s\n" "$(hostname)"
systemctl start wazuh-agent