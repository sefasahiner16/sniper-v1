#!/bin/bash

# Update script for Sniper V1 on GCP
# Usage: ./deploy/update.sh

echo "📦 Unzipping sniper_deploy.zip..."
unzip -o sniper_deploy.zip -d /home/sahinersefa9/sniper-v1/

echo "🔄 Restarting sniper service..."
sudo systemctl restart sniper

echo "✅ Update complete! Checking status..."
sudo systemctl status sniper --no-pager
