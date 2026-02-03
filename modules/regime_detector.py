"""
Sniper V5 - Market Regime Detector
===================================
Detects market regime based on three independent dimensions:
1. Volatility (Normalized ATR)
2. Momentum (EMA Slope)
3. Market Breadth (% of coins with positive returns)

Returns one of 4 regimes: QUIET, TRANSITIONAL, TRENDING, FAKE_NO_TRADE
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import pandas as pd

from config.settings import (
    # Volatility thresholds
    REGIME_ATR_PERIOD, REGIME_ATR_LOOKBACK_DAYS,
    VOLATILITY_LOW_THRESHOLD, VOLATILITY_MEDIUM_UPPER,
    VOLATILITY_HIGH_THRESHOLD, VOLATILITY_EXTREME_THRESHOLD,
    # Momentum thresholds
    MOMENTUM_EMA_PERIOD, MOMENTUM_LOOKBACK_BARS,
    MOMENTUM_WEAK_THRESHOLD, MOMENTUM_STRONG_THRESHOLD,
    # Breadth thresholds
    BREADTH_COIN_UNIVERSE, BREADTH_RETURN_THRESHOLD,
    BREADTH_WEAK_THRESHOLD, BREADTH_STRONG_THRESHOLD,
)


class MarketRegime(Enum):
    """Market regime classification."""
    QUIET = "QUIET"                    # Low vol, weak momentum
    TRANSITIONAL = "TRANSITIONAL"      # Medium vol, moderate momentum
    TRENDING = "TRENDING"              # High vol, strong momentum, strong breadth
    FAKE_NO_TRADE = "FAKE_NO_TRADE"   # High vol, weak momentum (stop-hunts)


class VolatilityState(Enum):
    """Volatility classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class MomentumState(Enum):
    """Momentum classification."""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class BreadthState(Enum):
    """Market breadth classification."""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


@dataclass
class RegimeAnalysis:
    """Full regime analysis result."""
    regime: MarketRegime
    volatility: VolatilityState
    momentum: MomentumState
    breadth: BreadthState
    normalized_atr: float
    ema_slope_pct: float
    breadth_pct: float
    
    def __str__(self) -> str:
        return (
            f"Regime: {self.regime.value} | "
            f"Vol: {self.volatility.value} ({self.normalized_atr:.2f}) | "
            f"Mom: {self.momentum.value} ({self.ema_slope_pct:.3f}%) | "
            f"Breadth: {self.breadth.value} ({self.breadth_pct:.1f}%)"
        )


class RegimeDetector:
    """
    Market Regime Detector
    
    Evaluates three independent dimensions continuously to classify market state.
    """
    
    def __init__(self, exchange):
        """
        Initialize with exchange connection.
        
        Args:
            exchange: CCXT exchange instance
        """
        self.exchange = exchange
        self._atr_cache: Dict[str, float] = {}
        self._cache_timestamp: Optional[float] = None
    
    # =========================================================================
    # Volatility Detection (ATR-Based)
    # =========================================================================
    
    def calculate_normalized_atr(self, symbol: str = "BTC/USDT") -> Tuple[float, VolatilityState]:
        """
        Calculate normalized ATR for volatility detection.
        
        Normalization: Current_ATR / Average_ATR(7-day lookback)
        
        Args:
            symbol: Trading pair to analyze (default BTC for market-wide view)
            
        Returns:
            Tuple of (normalized_atr, volatility_state)
        """
        try:
            # Fetch 15m candles for ATR calculation
            # Need enough candles for 7-day average: 7 days * 24h * 4 (15m candles/hour) = 672
            limit = REGIME_ATR_LOOKBACK_DAYS * 24 * 4 + REGIME_ATR_PERIOD + 10
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=limit)
            
            if len(ohlcv) < REGIME_ATR_PERIOD + 50:
                return 1.0, VolatilityState.MEDIUM  # Default on error
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate True Range
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            
            # Calculate ATR (14-period)
            atr = tr.rolling(window=REGIME_ATR_PERIOD).mean()
            
            # Current ATR (last value)
            current_atr = atr.iloc[-1]
            
            # 7-day average ATR
            lookback_candles = REGIME_ATR_LOOKBACK_DAYS * 24 * 4  # 15m candles per day
            avg_atr = atr.iloc[-lookback_candles:].mean()
            
            if avg_atr == 0 or pd.isna(avg_atr):
                return 1.0, VolatilityState.MEDIUM
            
            # Normalized ATR
            normalized = current_atr / avg_atr
            
            # Classify volatility state
            if normalized >= VOLATILITY_EXTREME_THRESHOLD:
                state = VolatilityState.EXTREME
            elif normalized > VOLATILITY_HIGH_THRESHOLD:
                state = VolatilityState.HIGH
            elif normalized >= VOLATILITY_LOW_THRESHOLD:
                state = VolatilityState.MEDIUM
            else:
                state = VolatilityState.LOW
            
            return float(normalized), state
            
        except Exception as e:
            print(f"[REGIME] Error calculating ATR volatility: {e}")
            return 1.0, VolatilityState.MEDIUM
    
    # =========================================================================
    # Momentum Detection (EMA Slope)
    # =========================================================================
    
    def calculate_momentum(self, symbol: str = "BTC/USDT") -> Tuple[float, MomentumState]:
        """
        Calculate momentum using EMA slope method.
        
        Slope = (EMA_now − EMA_10_bars_ago) / EMA_10_bars_ago
        
        Args:
            symbol: Trading pair
            
        Returns:
            Tuple of (slope_pct, momentum_state)
        """
        try:
            # Fetch 15m candles
            limit = MOMENTUM_EMA_PERIOD + MOMENTUM_LOOKBACK_BARS + 20
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=limit)
            
            if len(ohlcv) < MOMENTUM_EMA_PERIOD + MOMENTUM_LOOKBACK_BARS:
                return 0.0, MomentumState.WEAK
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate EMA
            ema = df['close'].ewm(span=MOMENTUM_EMA_PERIOD, adjust=False).mean()
            
            # EMA now vs EMA 10 bars ago
            ema_now = ema.iloc[-1]
            ema_lookback = ema.iloc[-MOMENTUM_LOOKBACK_BARS - 1]
            
            if ema_lookback == 0:
                return 0.0, MomentumState.WEAK
            
            # Slope as percentage
            slope_pct = ((ema_now - ema_lookback) / ema_lookback) * 100
            
            # Classify momentum state (absolute value for direction-agnostic)
            abs_slope = abs(slope_pct)
            
            if abs_slope >= MOMENTUM_STRONG_THRESHOLD:
                state = MomentumState.STRONG
            elif abs_slope >= MOMENTUM_WEAK_THRESHOLD:
                state = MomentumState.MODERATE
            else:
                state = MomentumState.WEAK
            
            return float(slope_pct), state
            
        except Exception as e:
            print(f"[REGIME] Error calculating momentum: {e}")
            return 0.0, MomentumState.WEAK
    
    # =========================================================================
    # Market Breadth Detection
    # =========================================================================
    
    def calculate_breadth(self) -> Tuple[float, BreadthState]:
        """
        Calculate market breadth.
        
        Breadth = % of top coins with 15m return > +0.3%
        
        Returns:
            Tuple of (breadth_pct, breadth_state)
        """
        try:
            # Fetch all tickers
            tickers = self.exchange.fetch_tickers()
            
            # Filter to USDT pairs and sort by volume
            usdt_tickers = {
                k: v for k, v in tickers.items()
                if k.endswith('/USDT') and not k.startswith('USDT')
                and v.get('quoteVolume', 0) and v.get('quoteVolume', 0) > 0
            }
            
            # Sort by 24h volume and take top N
            sorted_tickers = sorted(
                usdt_tickers.items(),
                key=lambda x: x[1].get('quoteVolume', 0),
                reverse=True
            )[:BREADTH_COIN_UNIVERSE]
            
            if len(sorted_tickers) == 0:
                return 30.0, BreadthState.MODERATE  # Default
            
            # Count coins with positive 15m return
            positive_count = 0
            
            for symbol, ticker in sorted_tickers:
                try:
                    # Fetch last 2 15m candles to calculate 15m return
                    ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=2)
                    if len(ohlcv) >= 2:
                        prev_close = ohlcv[-2][4]
                        curr_close = ohlcv[-1][4]
                        if prev_close > 0:
                            return_pct = (curr_close - prev_close) / prev_close
                            if return_pct > BREADTH_RETURN_THRESHOLD:
                                positive_count += 1
                except:
                    continue
            
            # Calculate breadth percentage
            breadth_pct = (positive_count / len(sorted_tickers)) * 100
            
            # Classify breadth state
            if breadth_pct > BREADTH_STRONG_THRESHOLD:
                state = BreadthState.STRONG
            elif breadth_pct >= BREADTH_WEAK_THRESHOLD:
                state = BreadthState.MODERATE
            else:
                state = BreadthState.WEAK
            
            return float(breadth_pct), state
            
        except Exception as e:
            print(f"[REGIME] Error calculating breadth: {e}")
            return 30.0, BreadthState.MODERATE
    
    # =========================================================================
    # Main Regime Detection
    # =========================================================================
    
    def detect_regime(self) -> RegimeAnalysis:
        """
        Detect current market regime.
        
        Decision Matrix:
        | Volatility | Momentum | Breadth | → Regime |
        |------------|----------|---------|----------|
        | Low        | Weak     | Any     | QUIET |
        | Medium     | Moderate | Moderate| TRANSITIONAL |
        | High       | Strong   | Strong  | TRENDING |
        | High       | Weak     | Weak    | FAKE_NO_TRADE |
        | Medium     | Weak     | Weak    | QUIET |
        | High       | Moderate | Weak    | TRANSITIONAL (Restricted) |
        
        Returns:
            RegimeAnalysis with full breakdown
        """
        # Calculate all three dimensions
        normalized_atr, vol_state = self.calculate_normalized_atr()
        slope_pct, mom_state = self.calculate_momentum()
        breadth_pct, breadth_state = self.calculate_breadth()
        
        # Determine regime based on decision matrix
        regime = self._classify_regime(vol_state, mom_state, breadth_state)
        
        result = RegimeAnalysis(
            regime=regime,
            volatility=vol_state,
            momentum=mom_state,
            breadth=breadth_state,
            normalized_atr=normalized_atr,
            ema_slope_pct=slope_pct,
            breadth_pct=breadth_pct
        )
        
        print(f"[REGIME] {result}")
        
        return result
    
    def _classify_regime(
        self,
        vol: VolatilityState,
        mom: MomentumState,
        breadth: BreadthState
    ) -> MarketRegime:
        """
        Apply classification logic to determine regime.
        
        Key rule: TRENDING requires ALL THREE confirmations (High vol + Strong mom + Strong breadth)
        """
        # FAKE/NO-TRADE: High volatility without momentum/breadth confirmation
        if vol in (VolatilityState.HIGH, VolatilityState.EXTREME):
            if mom == MomentumState.WEAK and breadth == BreadthState.WEAK:
                return MarketRegime.FAKE_NO_TRADE
            
            # TRENDING: Full confirmation
            if mom == MomentumState.STRONG and breadth == BreadthState.STRONG:
                return MarketRegime.TRENDING
            
            # High vol but partial confirmation → Transitional (restricted)
            return MarketRegime.TRANSITIONAL
        
        # QUIET: Low volatility OR weak momentum with weak breadth
        if vol == VolatilityState.LOW:
            return MarketRegime.QUIET
        
        if mom == MomentumState.WEAK and breadth == BreadthState.WEAK:
            return MarketRegime.QUIET
        
        # TRANSITIONAL: Medium volatility with moderate signals
        if vol == VolatilityState.MEDIUM:
            if mom in (MomentumState.MODERATE, MomentumState.STRONG):
                return MarketRegime.TRANSITIONAL
            return MarketRegime.QUIET
        
        # Default fallback
        return MarketRegime.TRANSITIONAL


# =============================================================================
# Singleton Instance
# =============================================================================

_detector_instance: Optional[RegimeDetector] = None


def get_regime_detector(exchange=None) -> RegimeDetector:
    """Get the global regime detector instance."""
    global _detector_instance
    if _detector_instance is None:
        if exchange is None:
            raise ValueError("Exchange must be provided on first call")
        _detector_instance = RegimeDetector(exchange)
    return _detector_instance


def detect_regime(exchange) -> RegimeAnalysis:
    """Convenience function to detect regime."""
    detector = get_regime_detector(exchange)
    return detector.detect_regime()
