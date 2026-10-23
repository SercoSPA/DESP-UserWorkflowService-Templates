#!/bin/bash

set -e
ENV_NAME="esa_dtc_ice_sheets_env"
SCRIPT_DIR=$(dirname "$0")

# check if environment already exists and remove it
if [ -d "/home/jovyan/$ENV_NAME" ]; then
    echo "Environment $ENV_NAME already exists. Remove it with setup-scripts/remove-virtual-environment.sh before creating it"
    exit 1
fi

echo "creating environment..."
python -m venv /home/jovyan/$ENV_NAME --system-site-packages # build on top of system site packages

bash $SCRIPT_DIR/install-requirements.sh

echo "environment created, enter: \"source /home/jovyan/${ENV_NAME}/bin/activate\" to activate it"
    