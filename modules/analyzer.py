"""
Sniper V1 - The Analyzer (5-Layer Filter)
==========================================
The brain of the trading system. Implements the 5-layer safety algorithm.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

from config.settings import (
    BTC_SENTIMENT_THRESHOLD,
    ORDERBOOK_DEPTH, ORDERBOOK_BID_ASK_RATIO,
    RSI_OVERSOLD,
    VOLUME_SPIKE_MULTIPLIER,
    TAKE_PROFIT_ATR_MULTIPLIER, STOP_LOSS_ATR_MULTIPLIER,
    ANALYSIS_TIMEFRAME, OHLCV_LIMIT
)
from modules.scanner import get_scanner
from modules.indicators import analyze_technicals, get_atr_targets


@dataclass
class AnalysisResult:
    """Result of the 5-layer analysis."""
    symbol: str
    is_buy_signal: bool
    
    # Layer results
    layer1_btc_ok: bool = False
    layer2_orderbook_ok: bool = False
    layer3_technical_ok: bool = False
    layer4_volume_ok: bool = False
    layer5_targets_set: bool = False
    
    # Data
    btc_change: Optional[float] = None
    bid_ask_ratio: Optional[float] = None
    rsi: Optional[float] = None
    price: Optional[float] = None
    bb_lower: Optional[float] = None
    volume_ratio: Optional[float] = None
    atr: Optional[float] = None
    
    # Targets (set by Layer 5)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Rejection reason (if not a buy signal)
    rejection_reason: Optional[str] = None
    
    def __str__(self) -> str:
        status = "✅ BUY SIGNAL" if self.is_buy_signal else f"❌ REJECTED: {self.rejection_reason}"
        return f"""
[{self.symbol}] {status}
├── Layer 1 (BTC):      {'✓' if self.layer1_btc_ok else '✗'} BTC Change: {self.btc_change:.2f}%
├── Layer 2 (OrderBook): {'✓' if self.layer2_orderbook_ok else '✗'} Bid/Ask: {self.bid_ask_ratio:.2f}
├── Layer 3 (Technical): {'✓' if self.layer3_technical_ok else '✗'} RSI: {self.rsi:.1f}, Price: {self.price:.6f}, BB Lower: {self.bb_lower:.6f}
├── Layer 4 (Volume):    {'✓' if self.layer4_volume_ok else '✗'} Volume Ratio: {self.volume_ratio:.2f}x
└── Layer 5 (Targets):   {'✓' if self.layer5_targets_set else '✗'} TP: {self.take_profit:.6f}, SL: {self.stop_loss:.6f}
"""


class Analyzer:
    """The 5-layer filter analyzer."""
    
    def __init__(self):
        """Initialize the analyzer."""
        self.scanner = get_scanner()
    
    def check_layer1_btc_sentiment(self) -> tuple[bool, float]:
        """
        Layer 1: Check if BTC is not bleeding.
        
        Returns:
            Tuple of (passed, btc_change_pct)
        """
        btc_change = self.scanner.get_btc_change(lookback_minutes=15)
        
        if btc_change is None:
            print("[ANALYZER] Layer 1: Could not fetch BTC data")
            return False, 0.0
        
        passed = btc_change > BTC_SENTIMENT_THRESHOLD
        
        if passed:
            print(f"[ANALYZER] Layer 1 ✓: BTC change {btc_change:.2f}% > {BTC_SENTIMENT_THRESHOLD}%")
        else:
            print(f"[ANALYZER] Layer 1 ✗: BTC change {btc_change:.2f}% <= {BTC_SENTIMENT_THRESHOLD}% (market too risky)")
        
        return passed, btc_change
    
    def check_layer2_orderbook(self, symbol: str) -> tuple[bool, float]:
        """
        Layer 2: Check order book imbalance.
        
        Args:
            symbol: Trading pair to analyze
            
        Returns:
            Tuple of (passed, bid_ask_ratio)
        """
        orderbook = self.scanner.get_orderbook(symbol, limit=ORDERBOOK_DEPTH)
        
        if orderbook is None:
            print(f"[ANALYZER] Layer 2: Could not fetch order book for {symbol}")
            return False, 0.0
        
        # Calculate total bid and ask volumes
        bid_volume = sum(bid[1] for bid in orderbook['bids'][:ORDERBOOK_DEPTH])
        ask_volume = sum(ask[1] for ask in orderbook['asks'][:ORDERBOOK_DEPTH])
        
        if ask_volume == 0:
            return False, 0.0
        
        ratio = bid_volume / ask_volume
        passed = ratio >= ORDERBOOK_BID_ASK_RATIO
        
        if passed:
            print(f"[ANALYZER] Layer 2 ✓: Bid/Ask ratio {ratio:.2f} >= {ORDERBOOK_BID_ASK_RATIO}")
        else:
            print(f"[ANALYZER] Layer 2 ✗: Bid/Ask ratio {ratio:.2f} < {ORDERBOOK_BID_ASK_RATIO} (weak buying pressure)")
        
        return passed, ratio
    
    def check_layer3_technical(self, df: pd.DataFrame) -> tuple[bool, dict]:
        """
        Layer 3: Check RSI + Bollinger Bands confluence.
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            Tuple of (passed, technicals_dict)
        """
        technicals = analyze_technicals(df)
        
        if "error" in technicals:
            print(f"[ANALYZER] Layer 3: {technicals['error']}")
            return False, technicals
        
        rsi = technicals.get('rsi')
        close = technicals.get('close')
        bb_lower = technicals.get('bb_lower')
        
        if rsi is None or close is None or bb_lower is None:
            print("[ANALYZER] Layer 3: Missing indicator data")
            return False, technicals
        
        rsi_oversold = rsi < RSI_OVERSOLD
        below_bb = close <= bb_lower
        
        passed = rsi_oversold and below_bb
        
        if passed:
            print(f"[ANALYZER] Layer 3 ✓: RSI {rsi:.1f} < {RSI_OVERSOLD} AND Price {close:.6f} <= BB Lower {bb_lower:.6f}")
        else:
            reasons = []
            if not rsi_oversold:
                reasons.append(f"RSI {rsi:.1f} >= {RSI_OVERSOLD}")
            if not below_bb:
                reasons.append(f"Price {close:.6f} > BB Lower {bb_lower:.6f}")
            print(f"[ANALYZER] Layer 3 ✗: {', '.join(reasons)}")
        
        return passed, technicals
    
    def check_layer4_volume(self, technicals: dict) -> tuple[bool, float]:
        """
        Layer 4: Check volume spike.
        
        Args:
            technicals: Technical analysis dictionary
            
        Returns:
            Tuple of (passed, volume_ratio)
        """
        volume = technicals.get('volume')
        volume_ma = technicals.get('volume_ma')
        
        if volume is None or volume_ma is None or volume_ma == 0:
            print("[ANALYZER] Layer 4: Missing volume data")
            return False, 0.0
        
        ratio = volume / volume_ma
        passed = ratio >= VOLUME_SPIKE_MULTIPLIER
        
        if passed:
            print(f"[ANALYZER] Layer 4 ✓: Volume {ratio:.2f}x average >= {VOLUME_SPIKE_MULTIPLIER}x required")
        else:
            print(f"[ANALYZER] Layer 4 ✗: Volume {ratio:.2f}x average < {VOLUME_SPIKE_MULTIPLIER}x (weak momentum)")
        
        return passed, ratio
    
    def calculate_layer5_targets(self, entry_price: float, atr: float) -> tuple[float, float]:
        """
        Layer 5: Calculate ATR-based take profit and stop loss.
        
        Args:
            entry_price: Expected entry price
            atr: Current ATR value
            
        Returns:
            Tuple of (take_profit, stop_loss)
        """
        take_profit, stop_loss = get_atr_targets(
            entry_price, atr,
            tp_multiplier=TAKE_PROFIT_ATR_MULTIPLIER,
            sl_multiplier=STOP_LOSS_ATR_MULTIPLIER
        )
        
        tp_pct = ((take_profit - entry_price) / entry_price) * 100
        sl_pct = ((stop_loss - entry_price) / entry_price) * 100
        
        print(f"[ANALYZER] Layer 5 ✓: TP ${take_profit:.6f} (+{tp_pct:.2f}%), SL ${stop_loss:.6f} ({sl_pct:.2f}%)")
        
        return take_profit, stop_loss
    
    def analyze(self, symbol: str) -> AnalysisResult:
        """
        Run full 5-layer analysis on a symbol.
        
        This is the main entry point for analysis.
        
        Args:
            symbol: Trading pair to analyze (e.g., "SUI/USDT")
            
        Returns:
            AnalysisResult with all layer results and targets
        """
        print(f"\n{'='*50}")
        print(f"[ANALYZER] Starting 5-layer analysis for {symbol}")
        print('='*50)
        
        result = AnalysisResult(symbol=symbol, is_buy_signal=False)
        
        # Layer 1: BTC Sentiment
        layer1_ok, btc_change = self.check_layer1_btc_sentiment()
        result.layer1_btc_ok = layer1_ok
        result.btc_change = btc_change
        
        if not layer1_ok:
            result.rejection_reason = "Layer 1: BTC sentiment negative"
            return result
        
        # Layer 2: Order Book
        layer2_ok, bid_ask_ratio = self.check_layer2_orderbook(symbol)
        result.layer2_orderbook_ok = layer2_ok
        result.bid_ask_ratio = bid_ask_ratio
        
        if not layer2_ok:
            result.rejection_reason = "Layer 2: Weak order book"
            return result
        
        # Fetch OHLCV data for remaining layers
        df = self.scanner.get_ohlcv(symbol, timeframe=ANALYSIS_TIMEFRAME, limit=OHLCV_LIMIT)
        
        if df is None or len(df) < 50:
            result.rejection_reason = "Insufficient OHLCV data"
            return result
        
        # Layer 3: Technical Confluence
        layer3_ok, technicals = self.check_layer3_technical(df)
        result.layer3_technical_ok = layer3_ok
        result.rsi = technicals.get('rsi')
        result.price = technicals.get('close')
        result.bb_lower = technicals.get('bb_lower')
        result.atr = technicals.get('atr')
        
        if not layer3_ok:
            result.rejection_reason = "Layer 3: Technical conditions not met"
            return result
        
        # Layer 4: Volume Validation
        layer4_ok, volume_ratio = self.check_layer4_volume(technicals)
        result.layer4_volume_ok = layer4_ok
        result.volume_ratio = volume_ratio
        
        if not layer4_ok:
            result.rejection_reason = "Layer 4: Volume too low"
            return result
        
        # Layer 5: ATR Targets
        if result.price and result.atr:
            take_profit, stop_loss = self.calculate_layer5_targets(result.price, result.atr)
            result.take_profit = take_profit
            result.stop_loss = stop_loss
            result.layer5_targets_set = True
        else:
            result.rejection_reason = "Layer 5: Could not calculate targets"
            return result
        
        # All layers passed!
        result.is_buy_signal = True
        print(f"\n🎯 [ANALYZER] ALL LAYERS PASSED - BUY SIGNAL for {symbol}")
        
        return result


# Singleton instance
_analyzer_instance = None

def get_analyzer() -> Analyzer:
    """Get the global analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = Analyzer()
    return _analyzer_instance
