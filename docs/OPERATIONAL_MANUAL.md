# Sniper V5 — Complete Technical Manual

**Version**: 5.0  
**Last Updated**: February 3, 2026  
**Strategy**: Layered Trading System with Automatic Market Regime Detection

---

## Table of Contents
1. [Overview](#1-overview)
2. [Architecture: The Layered Trading Philosophy](#2-architecture)
3. [Automatic Market Regime System](#3-market-regime-system)
4. [Entry Logic: The 6-Layer Filter](#4-entry-logic)
5. [Exit Logic: Winner Protection](#5-exit-logic)
6. [The Handler: Capital Authority](#6-the-handler)
7. [Risk Management](#7-risk-management)
8. [Configuration Reference](#8-configuration-reference)
9. [Telegram Notifications](#9-telegram-notifications)
10. [Deployment](#10-deployment)

---

## 1. Overview

### Core Philosophy

**Risk is allowed to be created, but loss is not allowed to compound.**

| Principle | Implementation |
|-----------|----------------|
| **Asymmetric Returns** | Winners run (3.5% trail), Losers cut fast (1.5%) |
| **Capital Authority** | Handler layer has final veto on all trades |
| **Regime Adaptive** | 4 market states with different parameters |
| **Layered Responsibility** | Watchtower creates, Scanner qualifies, Handler approves |

### What's New in V5

| Feature | Description |
|---------|-------------|
| 🎯 **4-Regime System** | QUIET, TRANSITIONAL, TRENDING, FAKE_NO_TRADE |
| 🔒 **Handler Layer** | Capital authority with final approval |
| 🏆 **Winner Protection** | Asymmetric exits for winning trades |
| 💰 **Profit Locking** | Lock 50% of gains after +5% daily |
| 📊 **Risk Budgets** | Daily -3%, Weekly -8%, Drawdown -15% limits |

---

## 2. Architecture

### The Layered Trading Philosophy

```
┌─────────────────────────────────────────────────────────────┐
│              LAYER 1: WATCHTOWER (Opportunity)              │
│  • Finds ALL candidates without safety filtering             │
│  • Risk creation is intentional at this stage                │
│  • Missing opportunities is worse than bad candidates        │
└─────────────────────────┬───────────────────────────────────┘
                          │ Candidates
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                LAYER 2: SCANNER (Qualification)             │
│  • Converts opportunity into bounded, measurable risk       │
│  • Answers: "If wrong, how wrong can it be?"                 │
│  • Cannot force execution                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ Trade Intents
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 3: HANDLER (Authority)                │
│  • Final veto power on ALL executions                       │
│  • Risk budgets, profit locking, winner protection          │
│  • Handler decisions override all other layers              │
└─────────────────────────┬───────────────────────────────────┘
                          │ APPROVE / DENY
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      EXECUTOR                               │
│  • Manages position lifecycle                               │
│  • Applies asymmetric exit rules                            │
└─────────────────────────────────────────────────────────────┘
```

**Authority Flow**: Watchtower → Scanner → Handler (one-directional, never reverse)

---

## 3. Market Regime System

### How Regime is Detected

Three independent dimensions are evaluated on the **15-minute timeframe**:

#### A. Volatility (Normalized ATR)

```
Normalized_ATR = Current_ATR(14) / Average_ATR(7-day)
```

| State | Condition | Meaning |
|-------|-----------|---------|
| LOW | < 0.8 | Quiet market, small moves |
| MEDIUM | 0.8 - 1.3 | Normal volatility |
| HIGH | > 1.3 | Elevated volatility |
| EXTREME | > 2.0 | Dangerous volatility |

#### B. Momentum (EMA Slope)

```
Slope = (EMA_now - EMA_10_bars_ago) / EMA_10_bars_ago × 100
```

| State | Condition | Meaning |
|-------|-----------|---------|
| WEAK | |slope| < 0.15% | No directional bias |
| MODERATE | 0.15% - 0.35% | Mild trend |
| STRONG | > 0.35% | Clear momentum |

#### C. Market Breadth

```
Breadth = % of top 50 coins with 15m return > +0.3%
```

| State | Condition | Meaning |
|-------|-----------|---------|
| WEAK | < 20% positive | Bear market |
| MODERATE | 20% - 40% positive | Mixed market |
| STRONG | > 40% positive | Bull market |

### The 4 Regimes

| Regime | Conditions | Intent | Slots |
|--------|------------|--------|-------|
| 🌙 **QUIET** | Low vol + Weak momentum | Capital preservation | 35% |
| 🔄 **TRANSITIONAL** | Medium vol + Moderate signals | Selective participation | 65% |
| 🚀 **TRENDING** | High vol + Strong mom + Strong breadth | Profit concentration | 100% |
| ⚠️ **FAKE_NO_TRADE** | High vol + Weak momentum | Avoid stop-hunts | 0% |

### Per-Regime Parameters

| Parameter | QUIET | TRANSITIONAL | TRENDING | FAKE |
|-----------|-------|--------------|----------|------|
| **RSI Threshold** | ≤30 | ≤34 | ≤40 | ≤25 |
| **RSI Hook Strict** | Yes | Yes | No | Yes |
| **Volume Spike** | 1.8x | 1.5x | 1.2x | 2.5x |
| **Stop Loss** | 1.5% | 2.0% | 2.5% | 1.2% |
| **Trailing Distance** | 1.5% | 2.0% | 3.0% | 1.0% |
| **Time Exit** | 30 min | 45 min | 90 min | 15 min |
| **Allow Trades** | ✅ | ✅ | ✅ | ❌ |

---

## 4. Entry Logic

### The 6-Layer Filter

Every trade must pass **ALL layers**:

#### Layer 0: Pre-Filters

| Filter | Rule | Purpose |
|--------|------|---------|
| **Handler Approval** | Check risk budgets | Capital protection |
| **Regime Check** | Not FAKE_NO_TRADE | Avoid stop-hunts |
| **Cooldown** | 60 min after selling | Prevent revenge trading |
| **Blacklist** | 24h ban after 2 losses | Avoid cursed coins |
| **Kill Switch** | Not active | BTC crash protection |

#### Layer 1: BTC Sentiment

```
PASS if: BTC 15-min change > -0.5%
```

#### Layer 2: Order Book

```
PASS if: Bid Volume / Ask Volume >= 1.0
```

#### Layer 3: Technical Confluence

**RSI Hook Logic** (regime-specific):
```
if regime.rsi_hook_strict:
    PASS if: (Previous RSI < threshold) AND (Current RSI >= Previous RSI)
else:
    PASS if: RSI < threshold  # TRENDING allows easier entry
```

| Regime | RSI Threshold | Hook Required? |
|--------|---------------|----------------|
| QUIET | 30 | Yes |
| TRANSITIONAL | 34 | Yes |
| TRENDING | 40 | No |

#### Layer 4: Volume Validation (Regime-Specific)

```
PASS if: Current Volume >= regime.volume_spike_mult × Average Volume
```

| Regime | Required Multiplier |
|--------|---------------------|
| QUIET | 1.8x |
| TRANSITIONAL | 1.5x |
| TRENDING | 1.2x |

#### Layer 5: Multi-Timeframe

```
PASS if: 15-minute RSI <= 50
```

#### Layer 6: ATR Targets

```
PASS if: Calculated Take Profit >= 2.0%
```

---

## 5. Exit Logic: Winner Protection

### The Key Asymmetry

**Losers are cut fast. Winners are given room to run.**

| Rule | Losers (< +1.5%) | Winners (≥ +1.5%) |
|------|------------------|-------------------|
| **Time Exit** | ✅ Enforced | ❌ Disabled |
| **Trailing Activation** | 1.5% profit | 2.5% profit |
| **Trailing Distance** | 2.0% | 3.5% |
| **Stop Tightening** | Fast | Slow |

### Exit Conditions (ANY triggers exit)

#### A. Stop Loss Hit
```
Exit if: Current Price <= Stop Loss Price
```

#### B. Take Profit Hit
```
Exit if: Current Price >= Take Profit Price
```

#### C. Trailing Stop
```
if profit >= trailing_activation:
    Activate trailing stop
    trailing_stop = highest_price × (1 - trailing_distance)
    
Exit if: Current Price <= Trailing Stop
```

**Ratchet Rule**: Trailing stop only moves UP, never down.

#### D. Time Exit (Winners Exempt)
```
if NOT is_winner AND position_age > time_exit_minutes AND profit < 1.0%:
    Exit position
```

### Example Progression

**Winner Trade (+5% profit):**
| Event | Stop Level |
|-------|------------|
| Entry @ $1.00 | $0.975 (-2.5%) |
| +0.8% profit | $1.001 (Break-even) |
| +1.5% profit | Winner status 🏆 |
| +2.5% profit | Trail activates @ $0.9925 |
| +5.0% profit | Trail @ $1.0125 |
| Trail hit | Exit @ ~$1.01 (+1%) |

---

## 6. The Handler: Capital Authority

### Risk Budget Enforcement

| Limit | Threshold | Action |
|-------|-----------|--------|
| **Daily Loss** | -3% | Block new trades until midnight UTC |
| **Weekly Loss** | -8% | Block new trades |
| **Rolling Drawdown** | -15% | Block new trades |

When a limit is hit:
- ❌ New positions blocked
- ✅ Existing positions continue normally
- ✅ All stops remain active
- ✅ Watchtower/Scanner continue (for when trading resumes)

### Profit Locking

```
if daily_pnl >= 5%:
    locked_capital = daily_pnl × 50%
    // This capital cannot be re-risked today
```

**Purpose**: Protect gains from being given back.

### Emergency Overrides

| Trigger | Action |
|---------|--------|
| BTC drops > 3% in 1 hour | Activate emergency mode |
| Handler emergency mode | Deny all new trades |
| Manual activation | Admin can trigger |

---

## 7. Risk Management

### Position Sizing

| Capital | Slots | Size per Slot |
|---------|-------|---------------|
| $12 | 2 | $6 each |
| $120 | 20 | $6 each |
| $1,200 | 20 | $60 each |
| $10,000 | 20 | $500 (capped) |

- **Base Trade Size**: $6 minimum
- **Whale Cap**: $500 maximum
- **Max Slots**: 20 (regime-adjusted)

### Slot Adjustment by Regime

| Regime | Slot Factor | With 20 Max Slots |
|--------|-------------|-------------------|
| QUIET | 35% | 7 slots |
| TRANSITIONAL | 65% | 13 slots |
| TRENDING | 100% | 20 slots |
| FAKE_NO_TRADE | 0% | 0 slots |

### Sector Caps (Correlation Protection)

| Sector | Max Slots |
|--------|-----------|
| MEME | 4 |
| L1 (Layer-1) | 5 |
| L2 (Layer-2) | 5 |
| DEFAULT | 3 |

---

## 8. Configuration Reference

### Regime Detection Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| `REGIME_ATR_PERIOD` | 14 | ATR calculation period |
| `REGIME_ATR_LOOKBACK_DAYS` | 7 | Normalization window |
| `VOLATILITY_LOW_THRESHOLD` | 0.8 | Below = LOW |
| `VOLATILITY_HIGH_THRESHOLD` | 1.3 | Above = HIGH |
| `VOLATILITY_EXTREME_THRESHOLD` | 2.0 | Above = EXTREME |
| `MOMENTUM_EMA_PERIOD` | 20 | EMA for slope calc |
| `MOMENTUM_LOOKBACK_BARS` | 10 | Slope calculation window |
| `MOMENTUM_WEAK_THRESHOLD` | 0.15% | Below = WEAK |
| `MOMENTUM_STRONG_THRESHOLD` | 0.35% | Above = STRONG |
| `BREADTH_COIN_UNIVERSE` | 50 | Top N coins |
| `BREADTH_RETURN_THRESHOLD` | 0.3% | Positive if above |
| `BREADTH_WEAK_THRESHOLD` | 20% | Below = WEAK |
| `BREADTH_STRONG_THRESHOLD` | 40% | Above = STRONG |

### Handler Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| `DAILY_LOSS_LIMIT_PCT` | -3.0% | Block new trades |
| `WEEKLY_LOSS_LIMIT_PCT` | -8.0% | Block new trades |
| `ROLLING_DRAWDOWN_LIMIT_PCT` | -15.0% | Block new trades |
| `PROFIT_LOCK_TRIGGER_PCT` | 5.0% | Lock profits after |
| `PROFIT_LOCK_RATIO` | 0.5 | Lock 50% of gains |

### Winner Protection Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| `WINNER_THRESHOLD_PCT` | 1.5% | Position is "winner" if above |
| `WINNER_TIME_EXIT_DISABLED` | True | No time exit for winners |
| `WINNER_TRAILING_ACTIVATION_PCT` | 2.5% | Late activation for winners |
| `WINNER_TRAILING_DISTANCE_PCT` | 3.5% | Wide trail for winners |

### Base Settings (Regime may override)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RSI_PERIOD` | 14 | RSI calculation |
| `RSI_OVERSOLD` | 32 | Base threshold |
| `VOLUME_SPIKE_MULTIPLIER` | 1.5 | Base volume requirement |
| `STOP_LOSS_ATR_MULTIPLIER` | 2.0 | SL = Entry - (2×ATR) |
| `TAKE_PROFIT_ATR_MULTIPLIER` | 10.0 | TP = Entry + (10×ATR) |
| `BREAK_EVEN_TRIGGER_PCT` | 0.8% | Move stop to BE |
| `TRAILING_STOP_ACTIVATION_PCT` | 1.5% | Default activation |
| `TRAILING_STOP_DISTANCE_PCT` | 2.0% | Default trail |

---

## 9. Telegram Notifications

### Buy Notification (V5)

```
🟢 [V5] BUY SIGNAL EXECUTED

📊 Symbol: SUI/USDT
💰 Entry Price: $1.234560
📈 Regime: 🔄 TRANSITIONAL

🎯 Take Profit: $1.360000 (+10.16%)
🛑 Stop Loss: $1.210000 (-1.99%)

⏰ Paper Trading Mode
```

### Sell Notification

```
🟢 [V5] POSITION CLOSED - WIN

📊 Symbol: SUI/USDT
📥 Entry: $1.234560
📤 Exit: $1.300000

💵 P&L: +5.30% (+$0.32)
💰 Balance: $12.64
📝 Reason: 📈 Trailing Stop Triggered

📈 Performance:
🏆 Win Rate: 65% (13/20)
📉 Total Trades: 20

⏰ Paper Trading Mode
```

---

## 10. Deployment

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MEXC_API_KEY` | ✅ | MEXC API key |
| `MEXC_SECRET_KEY` | ✅ | MEXC secret |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram notifications |
| `TELEGRAM_CHAT_ID` | ❌ | Your chat ID |
| `BOT_VERSION` | ❌ | Default: V5 |

### Commands

```bash
python main.py             # Run V5 multi-slot
python main.py --test      # Test API connection
python main.py --scan      # Single scan (no trading)
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    SNIPER V5 QUICK REF                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  REGIMES:                                                   │
│  🌙 QUIET      = Low vol, weak mom → 35% slots, RSI≤30     │
│  🔄 TRANSITIONAL = Medium → 65% slots, RSI≤34              │
│  🚀 TRENDING   = High vol, strong all → 100% slots, RSI≤40 │
│  ⚠️ FAKE       = High vol, weak mom → 0% slots (NO TRADE)  │
│                                                             │
│  HANDLER LIMITS:                                            │
│  • Daily loss > -3% → Block new trades                      │
│  • Weekly loss > -8% → Block new trades                     │
│  • Drawdown > -15% → Block new trades                       │
│  • Daily profit > +5% → Lock 50%                            │
│                                                             │
│  WINNER PROTECTION (if profit ≥ 1.5%):                      │
│  🏆 No time exit                                            │
│  🏆 Trail activates at 2.5% (not 1.5%)                      │
│  🏆 Trail distance 3.5% (not 2.0%)                          │
│                                                             │
│  EXIT CONDITIONS (ANY triggers):                            │
│  • Stop Loss hit                                            │
│  • Take Profit hit                                          │
│  • Trailing Stop hit                                        │
│  • Time exit (45min, < 1% profit, NOT WINNER)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Document generated: February 3, 2026*
