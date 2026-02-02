# Sniper V4 — Complete Operational Manual

**Version**: 4.0  
**Last Updated**: February 2, 2026  
**Strategy**: Multi-State Adaptive Mean-Reversion Trading System

---

## Table of Contents
1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Market Regimes & Strategies](#3-market-regimes--strategies)
4. [Entry Logic: The 6-Layer Filter](#4-entry-logic-the-6-layer-filter)
5. [Exit Logic: Dual-Stage Ratchet](#5-exit-logic-dual-stage-ratchet)
6. [Risk Management](#6-risk-management)
7. [Capital Management](#7-capital-management)
8. [Configuration Reference](#8-configuration-reference)
9. [Telegram Notifications](#9-telegram-notifications)
10. [Deployment](#10-deployment)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

### What is Sniper V4?

Sniper V4 is an automated cryptocurrency trading bot designed for **mean-reversion trading** on the MEXC exchange. It identifies oversold altcoins, waits for reversal confirmation, then enters positions with strict risk management.

### Core Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Small Losses** | Tight ATR-based stop losses (~2%) |
| **Unlimited Upside** | 10x ATR take profit target with trailing stop |
| **Safety First** | 6-layer entry filter + server-side stop orders |
| **Adaptive** | 4 different strategies based on market conditions |

### Key Features

- 🎯 **Multi-Slot Trading**: Up to 20 concurrent positions
- 🦎 **Chameleon Mode**: Adapts to Bull/Bear markets
- 🪝 **RSI Hook**: Buys reversals, not falling knives
- 🧟 **Zombie Filter**: Avoids illiquid coins
- 🚨 **Kill Switch**: Auto-pauses on BTC flash crashes
- 📦 **The Vault**: BTC treasury for profits

---

## 2. Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        MAIN.PY                              │
│                    (Entry Point)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │     DISPATCHER        │
          │  (Multi-Slot Manager) │
          └───────────┬───────────┘
                      │
     ┌────────────────┼────────────────┐
     │                │                │
┌────▼────┐    ┌──────▼──────┐   ┌─────▼─────┐
│WATCHTOWER│    │ SNIPER SLOT │   │  VAULT    │
│(Scanner) │    │ (x1 to x20) │   │ MANAGER   │
└────┬────┘    └──────┬──────┘   └───────────┘
     │                │
     │         ┌──────▼──────┐
     └─────────► ANALYZER    │
               │ (5-Layer)   │
               └──────┬──────┘
                      │
               ┌──────▼──────┐
               │  EXECUTOR   │
               │(Trade Mgmt) │
               └─────────────┘
```

### Module Descriptions

| Module | File | Purpose |
|--------|------|---------|
| **Scanner** | `modules/scanner.py` | Fetches market data, filters candidates, detects market regime |
| **Analyzer** | `modules/analyzer.py` | Runs 6-layer filter, calculates entry/exit levels |
| **Executor** | `modules/executor.py` | Manages position lifecycle, trailing stops |
| **Dispatcher** | `modules/dispatcher.py` | Orchestrates multiple slots (V3+ only) |
| **Capital Manager** | `modules/capital_manager.py` | Slot sizing, dead hours, kill switch, vault |
| **Indicators** | `modules/indicators.py` | RSI, Bollinger Bands, ATR calculations |

---

## 3. Market Regimes & Strategies

### How Market Regime is Detected

The bot classifies the market using Bitcoin data:

```
BULL Market = (BTC Price > 50-day SMA) AND (BTC Daily RSI > 50)
BEAR Market = Everything else
```

### The 4-State Strategy Map

| State | Conditions | Strategy Name | Description |
|-------|------------|---------------|-------------|
| **BEAR_WEEKDAY** | BTC < SMA50 + Mon-Fri | "Sniper" | Strict scalping |
| **BEAR_WEEKEND** | BTC < SMA50 + Sat-Sun | "Bunker" | Ultra-defensive |
| **BULL_WEEKDAY** | BTC > SMA50 + Mon-Fri | "Rally" | Dip buying |
| **BULL_WEEKEND** | BTC > SMA50 + Sat-Sun | "Volatility" | Wide stops |

### Strategy Parameters

| Parameter | Sniper | Bunker | Rally | Volatility |
|-----------|--------|--------|-------|------------|
| Min Volume | $2M | $5M | $1.5M | $1M |
| RSI Limit | 32 | 28 | 40 | 35 |
| Timeout | 45 min | 90 min | 120 min | 180 min |
| Min Stop Loss | 1.5% | 1.5% | 2.5% | 3.0% |
| Slots Factor | 100% | 50% | 100% | 100% |

---

## 4. Entry Logic: The 6-Layer Filter

Every trade must pass **ALL layers** before execution:

### Layer 0: Pre-Filters

| Filter | Rule | Purpose |
|--------|------|---------|
| **Cooldown** | Cannot re-buy same coin for 60 min after ANY sale | Prevents revenge trading |
| **Blacklist** | Coin banned for 24h after 2 losses in 24h | Avoids "cursed" coins |
| **Dead Hours** | No new trades 03:00-06:00 UTC | Avoids low liquidity periods |
| **Kill Switch** | Trading paused if BTC drops 3%+ in 1 hour | Flash crash protection |

### Layer 1: BTC Sentiment

```
PASS if: BTC 15-minute change > -0.5%
```

**Purpose**: Don't buy altcoins when BTC is bleeding.

### Layer 2: Order Book Analysis

```
PASS if: (Total Bid Volume / Total Ask Volume) >= 1.0
```

**Purpose**: Confirms buying pressure exists.

### Layer 3: Technical Confluence

**Indicators Used**:
- RSI (14-period)
- Bollinger Bands (20-period, 2 std dev)

**RSI Hook Logic** (when `RSI_HOOK_STRICT = True`):
```
PASS if: (Previous RSI < 32) AND (Current RSI >= Previous RSI)
```

This means the RSI must:
1. Have been below the threshold
2. Now be curling back UP (reversal confirmation)

> ⚠️ **Why you might not see trades**: With RSI Hook STRICT enabled, the bot won't buy during a straight-line dip. It waits for the "hook" pattern showing reversal.

### Layer 4: Volume Validation

```
PASS if: Current Volume >= 1.5x Average Volume (20-period)
```

**Purpose**: Confirms momentum/capitulation selling.

### Layer 5: Multi-Timeframe Confirmation

```
PASS if: 15-minute RSI <= 50
```

**Purpose**: Ensures oversold condition exists on higher timeframe.

### Layer 6: ATR Targets & Noise Filter

```
PASS if: Calculated Take Profit >= 2.0%
```

**Purpose**: Rejects low-volatility coins that don't offer enough upside.

---

## 5. Exit Logic: Dual-Stage Ratchet

The bot uses a sophisticated exit system that protects capital while allowing winners to run:

### A. Initial Hard Stop

| Setting | Value | Description |
|---------|-------|-------------|
| ATR Multiplier | 2.0x | Stop loss = Entry - (2.0 × ATR) |
| Minimum | 1.5% | Never tighter than 1.5% |
| Maximum | 2.4% | Hard catastrophe limit |

### B. Stage 1: Break-Even (Capital Protection)

| Trigger | Action |
|---------|--------|
| +0.8% profit | Move stop to +0.1% (Entry + Fees) |

**Result**: Once triggered, you cannot lose money on the trade.

### C. Stage 2: Wide Trailing Stop (Let Winners Run)

| Trigger | Action |
|---------|--------|
| +1.5% profit | Activate trailing stop with 2.0% gap |

**Example Progression**:
| When Price Reaches | Trailing Stop Moves To |
|--------------------|------------------------|
| +1.5% | -0.5% (1.5% - 2.0% gap) |
| +5.0% | +3.0% |
| +10.0% | +8.0% |
| +20.0% | +18.0% |

**Ratchet Rule**: The trailing stop only moves UP, never down.

### D. Take Profit Target

| Setting | Value | Notes |
|---------|-------|-------|
| ATR Multiplier | 10.0x | Essentially unlimited |

We rely on the trailing stop to exit, not a fixed take profit.

### E. Time-Based Exit

| Trigger | Action |
|---------|--------|
| Position open > 45 min (strategy-dependent) AND profit < 1.0% | Exit position |

**Purpose**: Don't hold stagnant trades.

---

## 6. Risk Management

### Circuit Breaker

| Trigger | Action | Duration |
|---------|--------|----------|
| 3 consecutive losses | Pause all trading | 12 hours |

### BTC Flash Crash Kill Switch

| Trigger | Action | Duration |
|---------|--------|----------|
| BTC drops > 3% in 1 hour | Emergency pause | 2 hours |

### Position Sizing

| Capital | Slots | Size per Slot |
|---------|-------|---------------|
| $12 | 2 | $6 each |
| $120 | 20 | $6 each |
| $1,200 | 20 | $60 each |
| $10,000 | 20 | $500 each (capped) |

- **Base Trade Size**: $6 minimum per slot
- **Whale Cap**: $500 maximum per slot
- **Max Concurrent Slots**: 20

---

## 7. Capital Management

### The Vault (BTC Treasury)

When USDT balance exceeds operational cap, the bot automatically buys BTC to store profits safely.

| Setting | Value | Description |
|---------|-------|-------------|
| Operational Cap | $10,000 | Target trading balance |
| Overflow | 1.0x | Buy BTC when above cap |
| Critical Level | 0.5x | Sell BTC when below 50% of cap |
| Rebalance Hour | 00:00 UTC | Daily vault check |

### Dead Hours (Shift System)

| Setting | Value | Description |
|---------|-------|-------------|
| Start | 03:00 UTC | Trading pause begins |
| End | 06:00 UTC | Trading resumes |
| Pre-Buffer | 60 min | Stop new entries 1 hour before |

**Purpose**: Avoid low-liquidity Asian morning session trap.

---

## 8. Configuration Reference

### Scanner Settings (`config/settings.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCAN_INTERVAL_SECONDS` | 60 | Time between scans |
| `MIN_24H_VOLUME_USDT` | 2,000,000 | Minimum liquidity |
| `MIN_PRICE_CHANGE_PCT` | -15.0 | Max dip to consider |
| `MAX_PRICE_CHANGE_PCT` | -1.5 | Min dip to consider |
| `WATCHLIST_SIZE` | 60 | Candidates per scan |

### Technical Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RSI_PERIOD` | 14 | RSI calculation period |
| `RSI_OVERSOLD` | 32 | Base RSI threshold |
| `RSI_HOOK_ENABLED` | True | Enable hook pattern |
| `RSI_HOOK_STRICT` | True | Require reversal confirmation |
| `BOLLINGER_PERIOD` | 20 | BB calculation period |
| `BOLLINGER_STD` | 2 | BB standard deviations |
| `ATR_PERIOD` | 14 | ATR calculation period |

### Risk Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TAKE_PROFIT_ATR_MULTIPLIER` | 10.0 | TP = Entry + (10 × ATR) |
| `STOP_LOSS_ATR_MULTIPLIER` | 2.0 | SL = Entry - (2 × ATR) |
| `MIN_STOP_LOSS_PCT` | 1.5 | Minimum stop loss distance |
| `HARD_STOP_LOSS_PCT` | 2.4 | Maximum catastrophe limit |
| `MIN_TARGET_PROFIT_PCT` | 2.0 | Noise filter threshold |

### Trailing Stop Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BREAK_EVEN_TRIGGER_PCT` | 0.8 | Move stop to BE at this profit |
| `BREAK_EVEN_TARGET_PCT` | 0.1 | Stop moved to Entry + this % |
| `TRAILING_STOP_ACTIVATION_PCT` | 1.5 | Start trailing at this profit |
| `TRAILING_STOP_DISTANCE_PCT` | 2.0 | Trail behind price by this % |
| `RATCHET_TRAILING_STOP` | True | Trail only moves UP |

### Protection Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `COOLDOWN_MINUTES` | 60 | Wait after selling before re-buying |
| `BLACKLIST_LOSSES` | 2 | Losses before 24h ban |
| `BLACKLIST_DURATION_HOURS` | 24 | Ban duration |
| `MAX_CONSECUTIVE_LOSSES` | 3 | Circuit breaker trigger |
| `CIRCUIT_BREAKER_HOURS` | 12 | Pause duration |
| `TIME_EXIT_MINUTES` | 45 | Stagnant trade timeout |

---

## 9. Telegram Notifications

### Notification Types

| Event | Sample Message |
|-------|----------------|
| **Startup** | 🚀 Sniper V4 STARTED — PAPER Mode — Balance: $12.00 — 2 Slots |
| **Buy Signal** | 🎯 BUY: SUI/USDT @ $1.23456 — TP: $1.36 — SL: $1.20 |
| **Position Closed** | 💰 SOLD: SUI/USDT — Entry: $1.23 → Exit: $1.30 — P&L: +5.68% ($0.34) — Balance: $12.34 — Trades: 10 — Win Rate: 70% |
| **Circuit Breaker** | 🚨 CIRCUIT BREAKER: 3 losses — Paused for 12 hours |
| **Kill Switch** | 🚨 KILL SWITCH ACTIVATED — BTC dropped -3.5% in 1 hour — Paused for 2 hours |

### Setup

1. Create a Telegram bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 10. Deployment

### Local Development

```bash
# Clone and setup
git clone https://github.com/sefasahiner16/sniper-v1.git
cd sniper-v1
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env with your API keys

# Run
python main.py --test      # Test connection
python main.py --scan      # Single scan (no trading)
python main.py             # Run bot (V3 multi-slot)
python main.py --legacy    # Run bot (V2 single-slot)
```

### Railway Deployment

1. Push to GitHub
2. Create Railway project: [railway.app](https://railway.app)
3. Link GitHub repo
4. Add environment variables
5. Deploy

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MEXC_API_KEY` | ✅ | Your MEXC API key |
| `MEXC_SECRET_KEY` | ✅ | Your MEXC secret |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram notifications |
| `TELEGRAM_CHAT_ID` | ❌ | Your Telegram chat ID |
| `BOT_VERSION` | ❌ | v2 or v3 (default: v3) |

---

## 11. Troubleshooting

### Bot Not Buying — Common Causes

| Issue | Cause | Solution |
|-------|-------|----------|
| No dips in market | `MAX_PRICE_CHANGE_PCT = -1.5` requires coins down 1.5%+ | Wait for dips OR set to 0 |
| RSI Hook waiting | RSI hasn't "hooked" up yet | Wait for reversal OR set `RSI_HOOK_STRICT = False` |
| Dead hours active | 03:00-06:00 UTC | Wait until 06:00 UTC |
| Kill switch triggered | BTC crashed recently | Wait 2 hours |
| Circuit breaker | 3 consecutive losses | Wait 12 hours |
| No volume | Coins don't have $2M+ volume | Normal in quiet markets |

### Checking Bot Status

```bash
# View market regime
python main.py --regime

# View last scan
python main.py --scan

# View performance
python main.py --stats
```

### Log Files

| File | Location | Contents |
|------|----------|----------|
| Trades | `data/trades.json` | All trade history |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    SNIPER V4 QUICK REF                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ENTRY CONDITIONS (ALL must pass):                          │
│  ✓ BTC not crashing (>-0.5% in 15min)                      │
│  ✓ Coin down 1.5% to 15% (24h)                             │
│  ✓ RSI < 32 AND hooking up                                  │
│  ✓ Volume > 1.5x average                                    │
│  ✓ 15m RSI < 50                                             │
│  ✓ Potential profit > 2%                                    │
│                                                             │
│  EXIT CONDITIONS (ANY triggers):                            │
│  • Stop Loss hit (-2% from entry)                           │
│  • Trailing Stop hit (after +1.5% profit)                   │
│  • Take Profit hit (+10x ATR)                               │
│  • Time exit (45min + < 1% profit)                          │
│                                                             │
│  PROTECTION:                                                │
│  🚨 Circuit Breaker: 3 losses → 12h pause                   │
│  🚨 Kill Switch: BTC -3% in 1h → 2h pause                   │
│  🌙 Dead Hours: 03:00-06:00 UTC (no new trades)             │
│  🧊 Cooldown: 60min after selling same coin                 │
│  ☠️ Blacklist: 2 losses on coin → 24h ban                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Document generated: February 2, 2026*
