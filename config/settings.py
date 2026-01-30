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
# MEXC API Configuration
# =============================================================================
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "")

# =============================================================================
# Telegram Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# =============================================================================
# Trading Mode
# =============================================================================
PAPER_TRADING = True  # Set to False when ready for live trading
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
SCAN_INTERVAL_SECONDS = 60  # OPTIMIZED: 1 minute between scans (High Velocity)
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
BTC_SENTIMENT_THRESHOLD = -0.5  # Abort if BTC drops more than this %
BTC_SMA_PERIOD = 50  # BTC SMA for market regime detection
BTC_RSI_PERIOD = 14  # RSI period for BTC confirmation
BTC_RSI_THRESHOLD = 50  # BTC RSI must be > this for Bull Mode

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

# Stage 2: Wide Trailing Stop
TRAILING_STOP_ACTIVATION_PCT = 1.5  # Start trailing at 1.5% profit (Hybrid: Lock in earlier)
TRAILING_STOP_DISTANCE_PCT = 2.0    # WIDE: Trail by 2.0% (Allows volatility)

# V2: Ratchet mode - trailing stop only moves UP, never down
RATCHET_TRAILING_STOP = True

# V2: Time-based exit (stagnant trade timeout)
TIME_EXIT_MINUTES = 45  # Exit if no profit after this many minutes
TIME_EXIT_MIN_PROFIT_PCT = 1.0  # Minimum profit % to stay in trade past timeout

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
ANALYSIS_TIMEFRAME = "5m"  # Candle timeframe for analysis
OHLCV_LIMIT = 100  # Number of candles to fetch

# V3: Multi-timeframe confirmation
MULTI_TIMEFRAME_ENABLED = True
CONFIRM_TIMEFRAME = "15m"  # Secondary timeframe for confirmation
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
        "rsi_limit": 40,  # Buy earlier (Dip Buy)
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
