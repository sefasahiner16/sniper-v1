#!/bin/bash
# =============================================================================
# Sniper V1 - Oracle Cloud Server Setup Script
# =============================================================================
# Run this on a fresh Ubuntu 22.04 VM to set up everything automatically.
# Usage: bash setup.sh
# =============================================================================

set -e  # Exit on any error

echo "================================================"
echo "🚀 Sniper V1 - Server Setup"
echo "================================================"

# Update system
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip
echo "[2/6] Installing Python 3.10+..."
sudo apt install -y python3 python3-pip python3-venv git

# Create project directory
echo "[3/6] Setting up project directory..."
mkdir -p ~/sniper-v1
cd ~/sniper-v1

# Create virtual environment
echo "[4/6] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "[5/6] Installing Python dependencies..."
pip install --upgrade pip
pip install ccxt pandas ta python-dotenv requests

# Create necessary directories
mkdir -p config modules utils data

echo "[6/6] Setup complete!"
echo ""
echo "================================================"
echo "📋 NEXT STEPS:"
echo "================================================"
echo ""
echo "1. Upload your project files to ~/sniper-v1/"
echo "   You can use SCP or FileZilla"
echo ""
echo "2. Create your .env file:"
echo "   nano ~/sniper-v1/.env"
echo ""
echo "3. Install the systemd service:"
echo "   sudo cp ~/sniper-v1/deploy/sniper.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable sniper"
echo "   sudo systemctl start sniper"
echo ""
echo "4. Check bot status:"
echo "   sudo systemctl status sniper"
echo "   sudo journalctl -u sniper -f"
echo ""
echo "================================================"
