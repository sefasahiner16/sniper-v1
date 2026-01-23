"""
Sniper V1 - Configuration Settings
===================================
All trading parameters and API configuration loaded from environment variables.
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
# Scanner Settings
# =============================================================================
SCAN_INTERVAL_SECONDS = 300  # 5 minutes between scans
MIN_24H_VOLUME_USDT = 100000  # Minimum 24h volume in USDT
MIN_PRICE_CHANGE_PCT = -15.0  # Minimum negative change (looking for dips)
MAX_PRICE_CHANGE_PCT = -3.0   # Maximum negative change (not too crashed)
WATCHLIST_SIZE = 20  # Number of candidates to analyze

# =============================================================================
# Layer 1: BTC Sentiment
# =============================================================================
BTC_SENTIMENT_THRESHOLD = -0.5  # Abort if BTC drops more than this %

# =============================================================================
# Layer 2: Order Book Analysis
# =============================================================================
ORDERBOOK_DEPTH = 20  # Number of levels to analyze
ORDERBOOK_BID_ASK_RATIO = 1.5  # Minimum bid/ask volume ratio

# =============================================================================
# Layer 3: Technical Indicators
# =============================================================================
RSI_PERIOD = 14
RSI_OVERSOLD = 30  # RSI must be below this
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# =============================================================================
# Layer 4: Volume Validation
# =============================================================================
VOLUME_MA_PERIOD = 20
VOLUME_SPIKE_MULTIPLIER = 1.5  # Current volume must be this x average

# =============================================================================
# Layer 5: ATR-Based Targets
# =============================================================================
ATR_PERIOD = 14
TAKE_PROFIT_ATR_MULTIPLIER = 2.0  # TP = Entry + (ATR * this)
STOP_LOSS_ATR_MULTIPLIER = 1.0    # SL = Entry - (ATR * this)

# =============================================================================
# Position Management
# =============================================================================
TRAILING_STOP_ACTIVATION_PCT = 1.0  # Activate trailing stop after 1% profit
TRAILING_STOP_DISTANCE_PCT = 0.5    # Trail 0.5% behind price
TIME_EXIT_MINUTES = 45  # Exit if stagnant for this long
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

# =============================================================================
# Logging
# =============================================================================
LOG_FILE = "data/trades.json"
LOG_LEVEL = "INFO"
