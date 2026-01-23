# 🚀 Deploying Sniper V1 to Oracle Cloud (Free Forever)

Complete guide to running your bot 24/7 for free.

---

## Step 1: Create Oracle Cloud Account

1. Go to [cloud.oracle.com](https://cloud.oracle.com)
2. Click **"Start for free"**
3. Fill in your details (credit card needed for verification, won't be charged)
4. Select a **Home Region** close to you (e.g., Frankfurt, London)
5. Wait for account activation (usually instant)

---

## Step 2: Create a Free VM Instance

1. Login to Oracle Cloud Console
2. Go to **Compute → Instances → Create Instance**
3. Configure:
   - **Name**: `sniper-bot`
   - **Image**: Ubuntu 22.04
   - **Shape**: Click "Change Shape"
     - Select **"Specialty and previous generation"**
     - Choose **VM.Standard.E2.1.Micro** (Always Free)
     - Or **Ampere A1** (also free, better performance)
   - **Networking**: Keep defaults (creates VCN automatically)
   - **SSH Keys**: Click "Generate key pair" and **download both keys**

4. Click **Create** and wait ~2 minutes

---

## Step 3: Connect to Your Server

### On Windows (PowerShell):

```powershell
# Move your downloaded key to a safe location
mkdir ~\.ssh -Force
Move-Item ~\Downloads\ssh-key-*.key ~\.ssh\oracle-key.pem

# Connect (replace IP with your instance's public IP)
ssh -i ~\.ssh\oracle-key.pem ubuntu@YOUR_SERVER_IP
```

### On Mac/Linux:

```bash
chmod 400 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_SERVER_IP
```

> **Find your IP**: In Oracle Console → Instances → Click your instance → "Public IP Address"

---

## Step 4: Set Up the Server

Once connected via SSH, run:

```bash
# Download and run setup script
curl -O https://raw.githubusercontent.com/YOUR_REPO/main/deploy/setup.sh
bash setup.sh
```

Or manually:

```bash
# Update & install Python
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv

# Create project folder
mkdir -p ~/sniper-v1
cd ~/sniper-v1

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install ccxt pandas ta python-dotenv requests
```

---

## Step 5: Upload Your Bot Files

### Option A: Using SCP (from your Windows PC)

```powershell
# From PowerShell on your PC, upload all files
scp -i ~\.ssh\oracle-key.pem -r "C:\Users\Sefa Şahiner\SniperV1\*" ubuntu@YOUR_SERVER_IP:~/sniper-v1/
```

### Option B: Using FileZilla (GUI)

1. Download [FileZilla](https://filezilla-project.org/)
2. Edit → Settings → SFTP → Add key file (your .pem file)
3. Connect: `sftp://ubuntu@YOUR_SERVER_IP`
4. Drag files from left (your PC) to right (server)

---

## Step 6: Configure Environment

```bash
# On the server
cd ~/sniper-v1

# Edit .env file with your API keys
nano .env
```

Paste your credentials:

```
MEXC_API_KEY=your_actual_key
MEXC_SECRET_KEY=your_actual_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Save: `Ctrl+X`, then `Y`, then `Enter`

---

## Step 7: Test the Bot

```bash
cd ~/sniper-v1
source venv/bin/activate
python main.py --test
```

You should see:
```
✅ MEXC API key configured
✅ Connected to MEXC
✅ Market data accessible
✅ Telegram notifications working
```

---

## Step 8: Set Up Auto-Start (systemd)

This makes the bot:
- Start automatically when server boots
- Restart automatically if it crashes
- Run 24/7 in the background

```bash
# Create logs directory
mkdir -p ~/sniper-v1/logs

# Copy service file
sudo cp ~/sniper-v1/deploy/sniper.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable sniper
sudo systemctl start sniper
```

---

## Step 9: Monitor Your Bot

### Check Status
```bash
sudo systemctl status sniper
```

### View Live Logs
```bash
sudo journalctl -u sniper -f
```

### View Log Files
```bash
tail -f ~/sniper-v1/logs/bot.log
```

### Stop the Bot
```bash
sudo systemctl stop sniper
```

### Restart the Bot
```bash
sudo systemctl restart sniper
```

---

## 🔥 Firewall Setup (Important!)

Oracle Cloud blocks all ports by default. The bot only needs outbound connections (which are allowed), so you don't need to open any ports.

But if you want to access logs via web (optional):
1. Go to **Networking → Virtual Cloud Networks**
2. Click your VCN → Security Lists → Default
3. Add Ingress Rule: Source `0.0.0.0/0`, Port `22` (for SSH)

---

## 📱 You're Done!

Your bot is now running 24/7 on Oracle Cloud for **$0/month**.

You'll receive Telegram notifications when:
- 🟢 Bot enters a trade
- 🔴 Bot exits a trade (with P&L)
- 🚨 Circuit breaker activates
- 🚀 Bot starts up

### Check Performance Anytime

```bash
ssh -i ~\.ssh\oracle-key.pem ubuntu@YOUR_SERVER_IP
cd ~/sniper-v1 && source venv/bin/activate
python main.py --stats
```

---

## ⚠️ Troubleshooting

### "Permission denied" on SSH
```bash
chmod 400 your-key.pem
```

### Bot not starting
```bash
sudo journalctl -u sniper -n 50  # See last 50 lines of logs
```

### "Module not found" error
```bash
cd ~/sniper-v1
source venv/bin/activate
pip install -r requirements.txt
```

### Update bot code
```bash
# Upload new files, then restart
sudo systemctl restart sniper
```
