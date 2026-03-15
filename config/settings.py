"""
Sniper V3 - Configuration Settings
===================================
All trading parameters and API configuration loaded from environment variables.

V3 Features:
- Multi-slot concurrent trading (3 slots)
- Multi-timeframe confirmation (5m + 15m)
- Volume capitulation detection
- RSI Hook, Zombie Filter, Chameleon Mode
- Dead hours, Ratchet trailing stop, Vault
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Bybit API Configuration
# =============================================================================
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET_KEY = os.getenv("BYBIT_SECRET_KEY", "")

# =============================================================================
# Telegram Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# =============================================================================
# Trading Mode
# =============================================================================
PAPER_TRADING = True  # FLIP TO False WHEN BYBIT IS FUNDED
INITIAL_BALANCE = 12.0  # Starting balance for paper trading (USD)

# =============================================================================
# V2: Dynamic Capital Management
# =============================================================================
BASE_TRADE_SIZE = 6.0  # Base $ per slot for auto-scaling ($6 min)
WHALE_CAP = 500.0  # Maximum $ per single trade (prevents slippage)
MIN_SLOT_SIZE = 6.0  # Minimum $ per trade (exchange minimum ~5)
MAX_CONCURRENT_SLOTS = 20  # V4: 20 simultaneous positions (User request)

# =============================================================================
# V2: The Vault (BTC Treasury)
# =============================================================================
VAULT_ENABLED = True  # Enable automatic BTC treasury management
VAULT_OVERFLOW_MULTIPLIER = 1.0  # Buy BTC when balance > operational_cap
VAULT_CRITICAL_LEVEL = 0.5  # Sell BTC when balance < operational_cap * this
VAULT_REBALANCE_HOUR_UTC = 0  # Daily vault rebalance hour (00:00 UTC)
OPERATIONAL_CAP = 10000.0  # Target operational USDT balance (20 slots * $500)

# =============================================================================
# V2: Dead Hours (Shift System)
# =============================================================================
DEAD_HOURS_ENABLED = True  # Enable trading pause during low volume hours
DEAD_HOURS_START_UTC = 3  # Trading pause start (03:00 UTC = 06:00 Turkey)
DEAD_HOURS_END_UTC = 6  # Trading pause end (06:00 UTC = 09:00 Turkey) - OPTIMIZED: Shortened duration
DEAD_HOURS_PRE_BUFFER_MINUTES = 60  # Stop buying this many minutes before dead hours

# =============================================================================
# =============================================================================
# Scanner Settings
# =============================================================================
SCAN_INTERVAL_SECONDS = 900  # 15 minutes between scans (matches analysis timeframe, reduces noise)
MIN_24H_VOLUME_USDT = 2000000  # HIGH LIQUIDITY: Min $2M volume (Anti-Zombie)
MIN_PRICE_CHANGE_PCT = -15.0  # Minimum negative change (looking for dips)
MAX_PRICE_CHANGE_PCT = -1.5   # OPTIMIZED: Catch smaller dips (was -2.0)
WATCHLIST_SIZE = 60  # OPTIMIZED: Widen the net (was 50)

# =============================================================================
# V2: Zombie Filter (Liquidity Check)
# =============================================================================
ZOMBIE_FILTER_ENABLED = True
ZOMBIE_VOLUME_RATIO = 0.3  # Min 24h volume / market cap ratio (Active Trading)

# =============================================================================
# Layer 1: BTC Sentiment + V2 Chameleon Mode
# =============================================================================
BTC_SENTIMENT_THRESHOLD = -0.5  # Abort if BTC drops more than this % (15-min check)
BTC_SMA_PERIOD = 50  # BTC SMA for market regime detection
BTC_RSI_PERIOD = 14  # RSI period for BTC confirmation
BTC_RSI_THRESHOLD = 50  # BTC RSI must be > this for Bull Mode

# V4: BTC Flash Crash Kill Switch (1-Hour Pulse Check)
BTC_CRASH_THRESHOLD = -3.0  # If BTC drops more than 3% in 1 hour, KILL SWITCH
BTC_CRASH_PAUSE_HOURS = 2   # Pause trading for this many hours after kill switch

# V2: Chameleon Mode - dynamic thresholds based on market regime
CHAMELEON_MODE_ENABLED = True
RSI_BULL_THRESHOLD = 45  # Looser RSI in bull market (BTC > SMA50)
RSI_BEAR_THRESHOLD = 35  # Stricter RSI in bear market (BTC < SMA50)

# =============================================================================
# Layer 2: Order Book Analysis
# =============================================================================
ORDERBOOK_DEPTH = 20  # Number of levels to analyze
ORDERBOOK_BID_ASK_RATIO = 1.0  # Minimum bid/ask volume ratio

# =============================================================================
# Layer 3: Technical Indicators + V2 RSI Hook
# =============================================================================
# Layer 3: Technical Indicators + V2 RSI Hook
# =============================================================================
RSI_PERIOD = 14
RSI_OVERSOLD = 32  # Base RSI threshold (Adjusted: 30 -> 32 for more trades)
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# V2: RSI Hook - buy on RSI crossing BACK above threshold, not while falling
RSI_HOOK_ENABLED = True
RSI_HOOK_STRICT = True  # ENABLED: Wait for curl up (Prevents falling knives)
RSI_HOOK_THRESHOLD = 30  # EARLIER ENTRY: Adjusted to 30 (was 32)

# V5: BBW Filter (Horizontal Market Avoidance)
# Reject trades if Bollinger Band Width < 0.05 (5%) - Market is too tight/choppy
BBW_FILTER_ENABLED = True
MIN_BB_WIDTH = 0.05

# =============================================================================
# Layer 4: Volume Validation
# =============================================================================
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 1.5  # Current volume must be this x average

# =============================================================================
# Layer 5: ATR-Based Targets
# =============================================================================
ATR_PERIOD = 14
TAKE_PROFIT_ATR_MULTIPLIER = 10.0  # UNLIMITED: 10x Reward
STOP_LOSS_ATR_MULTIPLIER = 2.0    # TARGET: ~2.0% risk (User Request: "Space to stretch")
MIN_STOP_LOSS_PCT = 1.5           # SAFETY: Minimum SL distance (Prevent too tight stops)

# V3: Minimum Volatility Requirement (Noise Filter)
# Reject trades if the calculated Take Profit is less than this %
MIN_TARGET_PROFIT_PCT = 2.0

# =============================================================================
# Position Management + V2 Dual-Stage Ratchet
# =============================================================================
# Stage 1: Break-Even
BREAK_EVEN_TRIGGER_PCT = 0.8  # Move stop to BE when profit hits 0.8% (Hybrid: Safety + Fees)
BREAK_EVEN_TARGET_PCT = 0.1   # The BE target (Entry + 0.1% to cover fees)

# Stage 2: Trailing Stop
TRAILING_STOP_ACTIVATION_PCT = 1.5  # Start trailing at 1.5% profit
TRAILING_STOP_DISTANCE_PCT = 1.2    # Tight trail: locks profit (matched to backtest)

# V2: Ratchet mode - trailing stop only moves UP, never down
RATCHET_TRAILING_STOP = True

# V2: Time-based exit (stagnant trade timeout)
TIME_EXIT_MINUTES = 60  # Exit if no profit after this many minutes
TIME_EXIT_MIN_PROFIT_PCT = 0.3  # Stay in trade if any meaningful profit

HARD_STOP_LOSS_PCT = 2.4  # SAFETY: Max loss 2.4%

# =============================================================================
# Risk Management
# =============================================================================
MAX_CONSECUTIVE_LOSSES = 3  # Trigger circuit breaker after this many
CIRCUIT_BREAKER_HOURS = 12  # Pause duration after circuit breaker
MAX_POSITION_PCT = 100  # Use 100% of balance per trade (single position model)

# V3: Advanced Cooldowns (Anti-Addiction)
COOLDOWN_MINUTES = 60         # Wait 60m before re-buying same coin after ANY sale
BLACKLIST_LOSSES = 2          # Blacklist coin after this many losses in 24h
BLACKLIST_DURATION_HOURS = 24 # Duration of blacklist for "cursed" coins

# =============================================================================
# Timeframes
# =============================================================================
ANALYSIS_TIMEFRAME = "15m"  # Candle timeframe for analysis (backtested on 15m)
OHLCV_LIMIT = 100  # Number of candles to fetch

# V3: Multi-timeframe confirmation
MULTI_TIMEFRAME_ENABLED = True
CONFIRM_TIMEFRAME = "1h"  # Secondary timeframe for confirmation (one level above analysis)
MULTI_TF_RSI_THRESHOLD = 50  # RSI must be below this on confirm timeframe (Adjusted: 40 -> 50)

# =============================================================================
# V3: Volume Capitulation Detection
# =============================================================================
CAPITULATION_ENABLED = True
CAPITULATION_VOLUME_MULT = 5.0  # Volume must be 5x+ average for capitulation
CAPITULATION_BONUS_SCORE = 0.5  # Extra score for capitulation + RSI Hook

# =============================================================================
# V4: Bull Mode (Trend-Following Strategy)
# =============================================================================
# When market is BULL (BTC > SMA50), switch from mean-reversion to trend-following
BULL_MODE_ENABLED = False  # DISABLED: Using STRATEGY_MAP logic instead (Rally Mode)

# Bull Mode Entry Conditions
BULL_RSI_BREAKOUT = 55       # RSI must cross ABOVE this (momentum building)
BULL_BREAKOUT_PERIOD = 20    # Price must be above N-period high

# Bull Mode Targets (let winners run in trending markets)
BULL_TAKE_PROFIT_ATR = 4.0   # Larger TP (trend continuation - 4x ATR)
BULL_STOP_LOSS_ATR = 2.0     # Tighter SL (trends are your friend - 2x ATR)

# =============================================================================
# Logging
# =============================================================================
LOG_FILE = "data/trades.json"
LOG_LEVEL = "INFO"

# =============================================================================
# V4: The 4-State Strategy Configuration
# =============================================================================
STRATEGY_MAP = {
    # 1. Bear Market / Weekday ("Sniper") - Scalping
    "BEAR_WEEKDAY": {
        "min_volume": 2000000,
        "timeout_minutes": 45,
        "rsi_limit": 32,
        "min_stop_loss_pct": 1.5,
        "slots_factor": 1.0,  # Standard slots
    },
    
    # 2. Bear Market / Weekend ("Bunker") - Defensive
    "BEAR_WEEKEND": {
        "min_volume": 5000000,
        "timeout_minutes": 90,
        "rsi_limit": 28,  # Picky entry
        "min_stop_loss_pct": 1.5,
        "slots_factor": 0.5,  # 50% reduced slots
    },
    
    # 3. Bull Market / Weekday ("Rally") - Trend Following
    "BULL_WEEKDAY": {
        "min_volume": 1500000,
        "timeout_minutes": 120,
        "rsi_limit": 50,  # RELAXED: Buy earlier (Dip Buy) - Was 40
        "min_stop_loss_pct": 2.5,  # Widen Stop
        "slots_factor": 1.0,
    },
    
    # 4. Bull Market / Weekend ("Volatility") - Chaos
    "BULL_WEEKEND": {
        "min_volume": 1000000,
        "timeout_minutes": 180,
        "rsi_limit": 35,
        "min_stop_loss_pct": 3.0,  # Very Wide Stop
        "slots_factor": 1.0,
    }
}

# =============================================================================
# V4.1: BTC Volatility Filter (Risk Reduction)
# =============================================================================
BTC_VOLATILITY_FILTER_ENABLED = True
BTC_VOLATILITY_THRESHOLD = 0.03  # If ATR/Price > 3%, reduce slots
BTC_VOLATILITY_SLOT_REDUCTION = 0.5  # Reduce to 50% of max slots

# =============================================================================
# V4.1: Conditional RSI Hook Relaxation (BULL_WEEKDAY only)
# =============================================================================
RSI_HOOK_RELAXATION_ENABLED = True
RSI_HOOK_RELAXATION_VOLUME_MULT = 2.5  # Volume must be >= 2.5x average

# =============================================================================
# V4.1: ATR-Based Trailing Stop
# =============================================================================
ATR_TRAILING_ENABLED = True
ATR_TRAILING_MULTIPLIER = 1.5  # Trail by 1.5 × ATR%
MIN_TRAILING_STOP_PCT = 1.2  # Hard minimum floor (NEVER go below this)

# =============================================================================
# V4.1: Conditional Time-Exit Extension
# =============================================================================
TIME_EXIT_EXTENSION_ENABLED = True
TIME_EXIT_EXTENSION_MINUTES = 30  # Extend by 30 min if conditions met

# =============================================================================
# V4.1: Slot Correlation Protection (Sector Caps)
# =============================================================================
SECTOR_CAPS_ENABLED = True
SECTOR_CAPS = {
    "MEME": 4,    # Max 4 meme coins
    "L1": 5,      # Max 5 Layer-1 coins
    "L2": 5,      # Max 5 Layer-2 coins
    "DEFAULT": 3  # Max 3 for uncategorized
}

# Sector classification (add coins as needed)
SECTOR_CLASSIFICATION = {
    # Meme Coins
    "DOGE": "MEME", "SHIB": "MEME", "PEPE": "MEME", "FLOKI": "MEME",
    "BONK": "MEME", "WIF": "MEME", "MEME": "MEME", "ELON": "MEME",
    "BABYDOGE": "MEME", "NEIRO": "MEME", "TURBO": "MEME", "COQ": "MEME",
    # Layer-1
    "BTC": "L1", "ETH": "L1", "SOL": "L1", "AVAX": "L1", "ADA": "L1",
    "DOT": "L1", "ATOM": "L1", "NEAR": "L1", "APT": "L1", "SUI": "L1",
    "SEI": "L1", "TIA": "L1", "INJ": "L1", "FTM": "L1", "ALGO": "L1",
    # Layer-2
    "MATIC": "L2", "ARB": "L2", "OP": "L2", "IMX": "L2", "STRK": "L2",
    "MANTA": "L2", "METIS": "L2", "ZK": "L2", "BLAST": "L2",
}

# =============================================================================
# V4.1: Daily Drawdown Guard
# =============================================================================
DAILY_DRAWDOWN_GUARD_ENABLED = True
DAILY_DRAWDOWN_LIMIT_PCT = -3.0  # Pause new entries if daily PnL <= -3%

# =============================================================================
# V5: AUTOMATIC MARKET REGIME SYSTEM
# =============================================================================

# Volatility Detection (Normalized ATR on 15m)
REGIME_ATR_PERIOD = 14
REGIME_ATR_LOOKBACK_DAYS = 7  # For 7-day average normalization

VOLATILITY_LOW_THRESHOLD = 0.8       # Normalized_ATR < 0.8 = LOW
VOLATILITY_MEDIUM_UPPER = 1.3        # 0.8 <= Normalized_ATR <= 1.3 = MEDIUM
VOLATILITY_HIGH_THRESHOLD = 1.3      # Normalized_ATR > 1.3 = HIGH
VOLATILITY_EXTREME_THRESHOLD = 2.0   # Normalized_ATR > 2.0 = EXTREME

# Momentum Detection (EMA Slope)
MOMENTUM_EMA_PERIOD = 20
MOMENTUM_LOOKBACK_BARS = 10
MOMENTUM_WEAK_THRESHOLD = 0.15       # |slope| < 0.15% = WEAK
MOMENTUM_STRONG_THRESHOLD = 0.35     # |slope| > 0.35% = STRONG

# Market Breadth Detection
BREADTH_COIN_UNIVERSE = 50           # Top N coins by volume
BREADTH_RETURN_THRESHOLD = 0.003     # >0.3% 15m return = positive
BREADTH_WEAK_THRESHOLD = 20          # < 20% positive = WEAK
BREADTH_STRONG_THRESHOLD = 40        # > 40% positive = STRONG

# Per-Regime Entry Filter Configuration
REGIME_CONFIG = {
    "QUIET": {
        "rsi_oversold": 28,          # Pickier: deeper oversold only
        "rsi_hook_strict": True,
        "volume_spike_mult": 1.8,
        "max_slots_factor": 0.20,    # Reduced exposure in quiet markets
        "min_expected_profit": 2.5,
        "allow_trades": True,
    },
    "TRANSITIONAL": {
        "rsi_oversold": 34,
        "rsi_hook_strict": True,
        "volume_spike_mult": 1.5,
        "max_slots_factor": 0.65,    # 60-70% of max slots
        "min_expected_profit": 2.0,
        "allow_trades": True,
    },
    "TRENDING": {
        "rsi_oversold": 50, # RELAXED: Catch shallower dips
        "rsi_hook_strict": False,    # Relaxed - let momentum enter
        "volume_spike_mult": 1.0,
        "max_slots_factor": 1.0,     # 100% of max slots
        "min_expected_profit": 1.5,
        "allow_trades": True,
    },
    "FAKE_NO_TRADE": {
        "rsi_oversold": 25,
        "rsi_hook_strict": True,
        "volume_spike_mult": 2.5,
        "max_slots_factor": 0.0,     # No new trades
        "min_expected_profit": 5.0,
        "allow_trades": False,       # BLOCK new entries
    },
}

# Per-Regime Exit/Risk Parameters
REGIME_EXIT_CONFIG = {
    "QUIET": {
        "stop_loss_pct": 1.5,
        "trailing_distance": 1.5,
        "time_exit_minutes": 45,
    },
    "TRANSITIONAL": {
        "stop_loss_pct": 2.0,
        "trailing_distance": 2.0,
        "time_exit_minutes": 60,
    },
    "TRENDING": {
        "stop_loss_pct": 2.5,
        "trailing_distance": 3.0,
        "time_exit_minutes": 120,
    },
    "FAKE_NO_TRADE": {
        "stop_loss_pct": 1.2,        # Tighten aggressively
        "trailing_distance": 1.0,
        "time_exit_minutes": 15,     # Very short
    },
}

# =============================================================================
# V5: HANDLER - CAPITAL AUTHORITY LAYER
# =============================================================================

# Risk Budget Limits
DAILY_LOSS_LIMIT_PCT = -3.0          # Block new trades if daily PnL <= this
WEEKLY_LOSS_LIMIT_PCT = -8.0         # Block new trades if weekly PnL <= this
ROLLING_DRAWDOWN_LIMIT_PCT = -15.0   # Block if peak-to-trough drawdown > this

# Profit Locking (Protect Gains)
PROFIT_LOCK_TRIGGER_PCT = 5.0        # Lock profits after 5% daily gain
PROFIT_LOCK_RATIO = 0.5              # Lock 50% of daily gains

# Winner Protection (Asymmetric Exit Rules)
WINNER_THRESHOLD_PCT = 3.0           # Raised above trailing activation to prevent dead zone
WINNER_TIME_EXIT_DISABLED = True     # Disable time exit for winners
WINNER_TRAILING_ACTIVATION_PCT = 2.5 # Wide trailing for winners
WINNER_TRAILING_DISTANCE_PCT = 1.5   # Tighter: lock profit, don't give it all back
