#!/bin/bash
# Azure App Service (Linux Python) startup command.
# Configure in Azure Portal → App Service → Configuration → General settings → Startup Command:
#   bash startup.sh
gunicorn --bind=0.0.0.0 --chdir server --timeout 600 --workers 2 main:app
