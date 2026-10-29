#!/bin/bash

set -e
ENV_NAME="esa_dtc_ice_sheets_env"
SCRIPT_DIR=$(dirname "$0")

echo "installing requirements..."
source /home/jovyan/$ENV_NAME/bin/activate
pip install --upgrade pip
python -m pip install -r $SCRIPT_DIR/requirements.txt
python -m ipykernel install --user --name=$ENV_NAME
echo "requirements installed"