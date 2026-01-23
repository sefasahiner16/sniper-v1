# 🎯 Sniper V1 - Data-Driven Trading Bot

A precision-focused cryptocurrency trading bot for MEXC using a 5-layer filter mechanism.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd SniperV1
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit the `.env` file with your credentials:

```env
# MEXC API (get from https://www.mexc.com/user/openapi)
MEXC_API_KEY=your_api_key_here
MEXC_SECRET_KEY=your_secret_key_here

# Telegram (optional, for notifications)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Test Connection

```bash
python main.py --test
```

### 4. Run the Bot

```bash
# Paper trading mode (default)
python main.py

# View stats
python main.py --stats

# Single scan (no trading)
python main.py --scan
```

## 📊 The 5-Layer Filter

The bot only trades when ALL conditions are met:

| Layer | Check | Threshold |
|-------|-------|-----------|
| 1️⃣ | BTC Sentiment | BTC 15m change > -0.5% |
| 2️⃣ | Order Book | Bid/Ask ratio > 1.5 |
| 3️⃣ | Technical | RSI < 30 AND Price ≤ Lower BB |
| 4️⃣ | Volume | Current > 1.5x average |
| 5️⃣ | Targets | ATR-based TP (+2x) and SL (-1x) |

## 🛡️ Risk Management

- **Trailing Stop**: Activates at +1% profit, trails at 0.5%
- **Time Exit**: Closes stagnant positions after 45 minutes
- **Circuit Breaker**: Pauses for 12 hours after 3 consecutive losses
- **Hard Stop Loss**: Maximum -5% per trade

## 📁 Project Structure

```
SniperV1/
├── config/
│   └── settings.py      # All configuration parameters
├── modules/
│   ├── scanner.py       # Market scanning & data fetching
│   ├── analyzer.py      # 5-layer filter logic
│   ├── executor.py      # Trade execution & monitoring
│   └── indicators.py    # Technical indicator calculations
├── utils/
│   ├── logger.py        # Trade logging to JSON
│   ├── notifier.py      # Telegram notifications
│   └── helpers.py       # Utility functions
├── data/
│   └── trades.json      # Paper trading history
├── .env                 # API credentials (not committed)
├── main.py              # Entry point
└── requirements.txt     # Dependencies
```

## 📱 Telegram Notifications

You'll receive alerts for:
- 🟢 **Buy signals** with entry price and targets
- 🔴 **Sell signals** with P&L summary
- 🚨 **Circuit breaker** activation
- 🚀 **Bot startup** confirmation

## ⚙️ Configuration

All settings are in `config/settings.py`:

```python
PAPER_TRADING = True        # Set False for live trading
INITIAL_BALANCE = 12.0      # Starting paper balance
SCAN_INTERVAL_SECONDS = 300 # 5 minutes between scans
```

## 📈 Paper Trading Mode

The bot starts in paper trading mode by default:
- Simulates trades without risking real money
- Logs all decisions to `data/trades.json`
- Tracks win rate and cumulative P&L
- Run for 2 weeks to validate strategy

## ☁️ Cloud Deployment (24/7)

Don't want to keep your computer on? Deploy to **Oracle Cloud for free**:

```bash
# See full guide
deploy/DEPLOY.md
```

Quick overview:
1. Create free Oracle Cloud account
2. Spin up a free Ubuntu VM
3. Upload your bot files
4. Install as a systemd service
5. Bot runs forever, auto-restarts on crash

📖 **Full guide**: [deploy/DEPLOY.md](deploy/DEPLOY.md)

## ⚠️ Disclaimer

This software is for educational purposes only. Cryptocurrency trading carries significant risk. Never trade with money you cannot afford to lose.
