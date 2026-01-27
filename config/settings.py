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
BASE_TRADE_SIZE = 5.0  # Base $ per slot for auto-scaling
WHALE_CAP = 500.0  # Maximum $ per single trade (prevents slippage)
MIN_SLOT_SIZE = 1.0  # Minimum $ per trade (exchange minimum)
MAX_CONCURRENT_SLOTS = 3  # V3: 3 simultaneous positions

# =============================================================================
# V2: The Vault (BTC Treasury)
# =============================================================================
VAULT_ENABLED = True  # Enable automatic BTC treasury management
VAULT_OVERFLOW_MULTIPLIER = 2.0  # Buy BTC when balance > operational_cap * this
VAULT_CRITICAL_LEVEL = 0.3  # Sell BTC when balance < operational_cap * this
VAULT_REBALANCE_HOUR_UTC = 2  # Daily vault rebalance hour (02:00 UTC)
OPERATIONAL_CAP = 100.0  # Target operational USDT balance

# =============================================================================
# V2: Dead Hours (Shift System)
# =============================================================================
DEAD_HOURS_ENABLED = True  # Enable trading pause during low volume hours
DEAD_HOURS_START_UTC = 3  # Trading pause start (03:00 UTC = 06:00 Turkey)
DEAD_HOURS_END_UTC = 6  # Trading pause end (06:00 UTC = 09:00 Turkey) - OPTIMIZED: Shortened duration
DEAD_HOURS_PRE_BUFFER_MINUTES = 60  # Stop buying this many minutes before dead hours

# =============================================================================
# Scanner Settings
# =============================================================================
SCAN_INTERVAL_SECONDS = 60  # OPTIMIZED: 1 minute between scans (High Velocity)
MIN_24H_VOLUME_USDT = 100000  # Minimum 24h volume in USDT
MIN_PRICE_CHANGE_PCT = -15.0  # Minimum negative change (looking for dips)
MAX_PRICE_CHANGE_PCT = -2.0   # OPTIMIZED: Catch smaller dips (was -3.0)
WATCHLIST_SIZE = 50  # OPTIMIZED: Widen the net (was 20)

# =============================================================================
# V2: Zombie Filter (Liquidity Check)
# =============================================================================
# =============================================================================
# V2: Zombie Filter (Liquidity Check)
# =============================================================================
ZOMBIE_FILTER_ENABLED = True
ZOMBIE_VOLUME_RATIO = 0.1  # Min 24h volume / market cap ratio

# =============================================================================
# Layer 1: BTC Sentiment + V2 Chameleon Mode
# =============================================================================
BTC_SENTIMENT_THRESHOLD = -0.5  # Abort if BTC drops more than this %
BTC_SMA_PERIOD = 50  # BTC SMA for market regime detection

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
RSI_OVERSOLD = 30  # Base RSI threshold (Prevent knife catching)
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# V2: RSI Hook - buy on RSI crossing BACK above threshold, not while falling
RSI_HOOK_ENABLED = True
RSI_HOOK_STRICT = True  # SAFETY: Strict Hook ON (No falling knives)
RSI_HOOK_THRESHOLD = 30  # RSI must cross back above this

# =============================================================================
# Layer 4: Volume Validation
# =============================================================================
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 1.5  # Current volume must be this x average

# =============================================================================
# Layer 5: ATR-Based Targets
# =============================================================================
ATR_PERIOD = 14
TAKE_PROFIT_ATR_MULTIPLIER = 1.5  # BALANCED: 1.5x Reward
STOP_LOSS_ATR_MULTIPLIER = 1.0    # SAFETY: 1.0x Risk (1:1.5 Ratio)

# V3: Minimum Volatility Requirement (Noise Filter)
# Reject trades if the calculated Take Profit is less than this %
MIN_TARGET_PROFIT_PCT = 1.5

# =============================================================================
# Position Management + V2 Ratchet Trailing Stop
# =============================================================================
TRAILING_STOP_ACTIVATION_PCT = 1.5  # Let it run to target before trailing
TRAILING_STOP_DISTANCE_PCT = 0.5    # Trail 0.5% behind price

# V2: Ratchet mode - trailing stop only moves UP, never down
RATCHET_TRAILING_STOP = True

# V2: Time-based exit (stagnant trade timeout)
TIME_EXIT_MINUTES = 45  # Exit if no profit after this many minutes
TIME_EXIT_MIN_PROFIT_PCT = 1.0  # Minimum profit % to stay in trade past timeout

HARD_STOP_LOSS_PCT = 5.0  # Maximum loss per trade

# =============================================================================
# Risk Management
# =============================================================================
MAX_CONSECUTIVE_LOSSES = 3  # Trigger circuit breaker after this many
CIRCUIT_BREAKER_HOURS = 12  # Pause duration after circuit breaker
MAX_POSITION_PCT = 100  # Use 100% of balance per trade (single position model)

# =============================================================================
# Timeframes
# =============================================================================
ANALYSIS_TIMEFRAME = "5m"  # Candle timeframe for analysis
OHLCV_LIMIT = 100  # Number of candles to fetch

# V3: Multi-timeframe confirmation
MULTI_TIMEFRAME_ENABLED = True
CONFIRM_TIMEFRAME = "15m"  # Secondary timeframe for confirmation
MULTI_TF_RSI_THRESHOLD = 40  # RSI must be below this on confirm timeframe

# =============================================================================
# V3: Volume Capitulation Detection
# =============================================================================
CAPITULATION_ENABLED = True
CAPITULATION_VOLUME_MULT = 5.0  # Volume must be 5x+ average for capitulation
CAPITULATION_BONUS_SCORE = 0.5  # Extra score for capitulation + RSI Hook

# =============================================================================
# Logging
# =============================================================================
LOG_FILE = "data/trades.json"
LOG_LEVEL = "INFO"
