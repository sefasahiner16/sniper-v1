# Sniper V3 Operational Manual

**Version**: 3.0 (Hybrid)
**Date**: 2026-01-28
**Strategy**: "The Step Ratchet" (Mean Reversion + Trend Following)

---

## 1. Core Philosophy
The Sniper V3 is designed for **Asymmetric Returns**:
*   **Small Losses**: Losses are cut immediately via tight stops.
*   **Unlimited Upside**: Winners are allowed to run using a precise ratchet mechanism.
*   **Safety First**: Liquidity filters and server-side orders prevent slippage and "rug falls."

---

## 2. Market Regimes (Chameleon Mode)
The bot adapts its strategy based on the broader market context (Bitcoin).

### Bull Market (Trend Following)
*   **Trigger**: BTC Price > BTC 50-Day SMA **AND** BTC RSI > 50.
*   **Logic**: "The Trend is your Friend, but only with Momentum."
*   **Entry**: Breakouts (RSI > 55, Price > 20-period High).
*   **Exits**: Wider stops, larger targets.

### Bear/Sideways Market (Mean Reversion)
*   **Trigger**: BTC Price < SMA50 **OR** BTC RSI < 50.
*   **Logic**: "Buy the Dip" or "Wait for clarity."
*   **Entry**: Oversold Dips (RSI < 32, Hook Pattern).
*   **Exits**: Tight scalps (Spinning out of danger quickly).

---

## 3. Entry Logic: The 5-Layer Filter
Every trade must pass **all 5 layers** to be executed.

1.  **Liquidity Filter ("Anti-Zombie")**
    *   **Rule**: 24h Volume must be > **$2,000,000**.
    *   **Purpose**: Filters out dead coins that can't be sold.
    *   **Logic**: Volume/Cap Ratio > 0.3.

2.  **Sentiment Filter**
    *   **Rule**: BTC must not be crashing > -0.5% in the last 15 mins.
    *   **Purpose**: "Don't catch knives when the floor is collapsing."

3.  **Technical Filter**
    *   **RSI Hook**: RSI must dip below **32** and then *curl up*.
    *   **Hook Logic**: Prevents buying a straight line down.

4.  **Volume Validation**
    *   **Rule**: Current volume spike > **1.5x** average volume.
    *   **Purpose**: Confirms buyers are stepping in.

5.  **Volatility Check**
    *   **Rule**: Potential upside must be > **2.0%**.
    *   **Purpose**: Ignores flat/boring coins.

---

## 4. Exit Logic: "The Dual-Stage Ratchet"
This updated logic balances capital safety with volatility tolerance (allowing winning trades to ride out wicks).

### A. Initial Hard Stop (The Safety Net)
*   **Setting**: -1.2% from Entry Price.
*   **Mechanism**: **Server-Side Stop Limit**. Placed instantly on entry.
*   **Goal**: Limits maximum loss to ~1.2%.

### B. Stage 1: The "Break-Even" Trigger (Safety First)
*   **Trigger**: Price reaches **+1.0% Profit**.
*   **Action**: Move Stop to **+0.1%** (Entry + Fees).
*   **Scenario**: If price hits +1.0% and crashes, we exit at +0.1% (Zero Loss).

### C. Stage 2: The "Wide Trail" (Growth Phase)
*   **Trigger**: Price reaches **+2.0% Profit**.
*   **Action**: Activate Trailing Stop with **1.5% Gap**.
    *   Price +2.0% -> Stop +0.5%.
    *   Price +5.0% -> Stop +3.5%.
    *   Price +10.0% -> Stop +8.5%.
*   **Goal**: Gives the coin "room to breathe." A normal 1% pullback will NOT stop the bot out, allowing it to catch +20% pumps.

### D. Take Profit (The Moonshot)
*   **Target**: 10x ATR (effectively unlimited).
*   **Logic**: We rely on the Trailing Stop to exit.

---

## 5. Protective Measures

### Anti-Slippage (Server-Side Orders)
*   **Mechanism**: The bot places real orders on the exchange.
*   **Benefit**: If the bot crashes or internet fails, the exchange will still execute the stop loss.

### Anti-Addiction (Cooldowns)
*   **Cooldown**: After selling a coin, the bot is locked out of that coin for **60 minutes**.
*   **Blacklist**: If a coin causes **2 losses** in 24 hours, it is banned for **24 hours**.

### Circuit Breaker
*   **Trigger**: **3 Consecutive Losses**.
*   **Action**: Bot shuts down for **12 hours**.

---

## 6. Configuration Reference (`config/settings.py`)

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **LIQUIDITY** | | |
| `MIN_24H_VOLUME_USDT` | `2,000,000` | Minimum volume to trade. |
| `ZOMBIE_VOLUME_RATIO` | `0.3` | Min active trading ratio. |
| **RISK** | | |
| `STOP_LOSS_ATR_MULTIPLIER` | `1.2` | Initial risk (~1.2%). |
| `HARD_STOP_LOSS_PCT` | `2.4` | Maximum catastrophe limit. |
| **TRAILING** | | |
| `TRAILING_STOP_ACTIVATION_PCT` | `0.5` | Profit needed to start trailing. |
| `TRAILING_STOP_DISTANCE_PCT` | `0.5` | Distance to follow price. |
| **PROTECTION** | | |
| `COOLDOWN_MINUTES` | `60` | Wait time after sale. |
| `BLACKLIST_LOSSES` | `2` | Losses before ban. |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Circuit breaker trigger. |
