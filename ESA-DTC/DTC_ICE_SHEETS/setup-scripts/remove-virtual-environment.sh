#!/bin/bash
# clean up and remove the DTC-ICE-SHEETS virtual environment and its associated Jupyter kernel

ENV_NAME="esa_dtc_ice_sheets_env"

rm -r /home/jovyan/$ENV_NAME
jupyter kernelspec uninstall $ENV_NAME -y

echo "Environment \"${ENV_NAME}\" succesfully removed"
