#!/bin/bash

if [ "$(date +%A)" == "Lundi" ] && [ $(date +%d) -eq 1 ]; then
    ansible-playbook -i /etc/ansible/hosts /etc/ansible/playbook/reh-upgrade.yml
fi