"""
Sniper V2 - Technical Indicators
=================================
Wrapper functions for technical analysis indicators using the 'ta' library.
"""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import SMAIndicator
from typing import Dict, Tuple

from config.settings import (
    RSI_PERIOD, RSI_OVERSOLD,
    BOLLINGER_PERIOD, BOLLINGER_STD,
    ATR_PERIOD, VOLUME_MA_PERIOD
)


def calculate_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    """
    Calculate Relative Strength Index.
    
    Args:
        df: DataFrame with 'close' column
        period: RSI lookback period
        
    Returns:
        Series of RSI values
    """
    rsi = RSIIndicator(close=df['close'], window=period)
    return rsi.rsi()


def calculate_bollinger_bands(df: pd.DataFrame, 
                               period: int = BOLLINGER_PERIOD,
                               std: float = BOLLINGER_STD) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    
    Args:
        df: DataFrame with 'close' column
        period: Moving average period
        std: Number of standard deviations
        
    Returns:
        Tuple of (lower, middle, upper) bands
    """
    bb = BollingerBands(close=df['close'], window=period, window_dev=int(std))
    return bb.bollinger_lband(), bb.bollinger_mavg(), bb.bollinger_hband()


def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR lookback period
        
    Returns:
        Series of ATR values
    """
    atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=period)
    return atr.average_true_range()


def calculate_volume_ma(df: pd.DataFrame, period: int = VOLUME_MA_PERIOD) -> pd.Series:
    """
    Calculate Volume Moving Average.
    
    Args:
        df: DataFrame with 'volume' column
        period: MA lookback period
        
    Returns:
        Series of volume MA values
    """
    sma = SMAIndicator(close=df['volume'], window=period)
    return sma.sma_indicator()


def calculate_highest_high(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Calculate rolling highest high over N periods.
    
    Used for Bull Mode breakout detection.
    
    Args:
        df: DataFrame with 'high' column
        period: Lookback period for highest high
        
    Returns:
        Series of highest high values
    """
    return df['high'].rolling(window=period).max()


def analyze_technicals(df: pd.DataFrame) -> Dict:
    """
    Calculate all technical indicators for analysis.
    
    Args:
        df: OHLCV DataFrame
        
    Returns:
        Dictionary with all indicator values for the latest candle
    """
    min_periods = max(RSI_PERIOD, BOLLINGER_PERIOD, ATR_PERIOD, VOLUME_MA_PERIOD) + 5
    if len(df) < min_periods:
        return {"error": f"Insufficient data (need {min_periods}, have {len(df)})"}
    
    try:
        # Calculate indicators
        rsi = calculate_rsi(df)
        bb_lower, bb_mid, bb_upper = calculate_bollinger_bands(df)
        atr = calculate_atr(df)
        vol_ma = calculate_volume_ma(df)
        
        # Get latest values (handle NaN)
        latest = {
            "close": float(df['close'].iloc[-1]),
            "volume": float(df['volume'].iloc[-1]),
            "rsi": float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None,
            "bb_lower": float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else None,
            "bb_mid": float(bb_mid.iloc[-1]) if pd.notna(bb_mid.iloc[-1]) else None,
            "bb_upper": float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else None,
            "atr": float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else None,
            "volume_ma": float(vol_ma.iloc[-1]) if pd.notna(vol_ma.iloc[-1]) else None,
        }
        
        # Add derived signals
        if latest["rsi"] is not None:
            latest["rsi_oversold"] = latest["rsi"] < RSI_OVERSOLD
        
        if latest["bb_lower"] is not None and latest["close"] is not None:
            latest["below_bb_lower"] = latest["close"] <= latest["bb_lower"]
        
        if latest["volume"] is not None and latest["volume_ma"] is not None and latest["volume_ma"] > 0:
            latest["volume_spike"] = latest["volume"] > (latest["volume_ma"] * 1.5)
        
        return latest
        
    except Exception as e:
        return {"error": f"Indicator calculation failed: {e}"}


def get_atr_targets(entry_price: float, atr: float, 
                    tp_multiplier: float = 2.0, 
                    sl_multiplier: float = 1.0) -> Tuple[float, float]:
    """
    Calculate ATR-based take profit and stop loss levels.
    
    Args:
        entry_price: Entry price
        atr: Current ATR value
        tp_multiplier: ATR multiplier for take profit
        sl_multiplier: ATR multiplier for stop loss
        
    Returns:
        Tuple of (take_profit_price, stop_loss_price)
    """
    take_profit = entry_price + (atr * tp_multiplier)
    stop_loss = entry_price - (atr * sl_multiplier)
    
    return take_profit, stop_loss
