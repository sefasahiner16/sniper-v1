"""
Sniper V3 - The Analyzer (Enhanced 5-Layer Filter)
===================================================
The brain of the trading system. Implements the enhanced 5-layer safety algorithm.

V3 Features:
- RSI Hook: Buy on RSI crossing BACK above threshold
- Zombie Filter: Liquidity check integration
- Chameleon Mode: Dynamic RSI thresholds based on market regime
- Multi-Timeframe: Confirm on 5m AND 15m charts
- Volume Capitulation: Detect 5x+ volume panic selling
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
import pandas as pd

from config.settings import (
    BTC_SENTIMENT_THRESHOLD,
    ORDERBOOK_DEPTH, ORDERBOOK_BID_ASK_RATIO,
    RSI_OVERSOLD, RSI_HOOK_ENABLED, RSI_HOOK_THRESHOLD,
    RSI_BULL_THRESHOLD, RSI_BEAR_THRESHOLD, CHAMELEON_MODE_ENABLED,
    ZOMBIE_FILTER_ENABLED,
    VOLUME_SPIKE_MULTIPLIER,
    TAKE_PROFIT_ATR_MULTIPLIER, STOP_LOSS_ATR_MULTIPLIER,
    ANALYSIS_TIMEFRAME, OHLCV_LIMIT,
    MULTI_TIMEFRAME_ENABLED, CONFIRM_TIMEFRAME, MULTI_TF_RSI_THRESHOLD,
    CAPITULATION_ENABLED, CAPITULATION_VOLUME_MULT
)
from modules.scanner import get_scanner
from modules.indicators import analyze_technicals, get_atr_targets, calculate_rsi


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
    
    # V2: Additional layer results
    zombie_filter_ok: bool = False  # Liquidity check
    rsi_hook_ok: bool = False  # RSI crossing confirmation
    
    # Data
    btc_change: Optional[float] = None
    bid_ask_ratio: Optional[float] = None
    rsi: Optional[float] = None
    rsi_prev: Optional[float] = None  # V2: Previous RSI for hook detection
    price: Optional[float] = None
    bb_lower: Optional[float] = None
    volume_ratio: Optional[float] = None
    atr: Optional[float] = None
    
    # V2: Market regime
    market_regime: str = "UNKNOWN"  # BULL, BEAR, or UNKNOWN
    effective_rsi_threshold: float = RSI_OVERSOLD  # Dynamic threshold
    
    # V2: Zombie filter data
    liquidity_ratio: Optional[float] = None
    
    # V3: Multi-timeframe confirmation
    multi_tf_ok: bool = False
    confirm_rsi: Optional[float] = None
    
    # V3: Volume capitulation
    capitulation_ok: bool = False
    capitulation_volume_ratio: Optional[float] = None
    
    # Targets (set by Layer 5)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Rejection reason (if not a buy signal)
    rejection_reason: Optional[str] = None
    
    def __str__(self) -> str:
        status = "✅ BUY SIGNAL" if self.is_buy_signal else f"❌ REJECTED: {self.rejection_reason}"
        rsi_hook_str = " (Hook ✓)" if self.rsi_hook_ok else ""
        regime_str = f" [{self.market_regime}]" if self.market_regime != "UNKNOWN" else ""
        return f"""
[{self.symbol}] {status}{regime_str}
├── Layer 1 (BTC):       {'✓' if self.layer1_btc_ok else '✗'} BTC Change: {self.btc_change:.2f}%
├── Layer 2 (OrderBook): {'✓' if self.layer2_orderbook_ok else '✗'} Bid/Ask: {self.bid_ask_ratio:.2f}
├── Layer 3 (Technical): {'✓' if self.layer3_technical_ok else '✗'} RSI: {self.rsi:.1f}{rsi_hook_str}, Threshold: {self.effective_rsi_threshold}
├── Layer 4 (Volume):    {'✓' if self.layer4_volume_ok else '✗'} Volume Ratio: {self.volume_ratio:.2f}x
├── Zombie Filter:       {'✓' if self.zombie_filter_ok else '✗'} Liquidity: {self.liquidity_ratio:.3f if self.liquidity_ratio else 'N/A'}
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
    
    def check_layer3_technical(
        self, 
        df: pd.DataFrame, 
        market_regime: str = "UNKNOWN"
    ) -> Tuple[bool, dict, bool, float]:
        """
        Layer 3: Check RSI + Bollinger Bands confluence.
        
        V2 Enhancements:
        - RSI Hook: Buy when RSI crosses BACK above threshold (not while falling)
        - Chameleon Mode: Dynamic RSI threshold based on market regime
        
        Args:
            df: OHLCV DataFrame
            market_regime: Current market regime (BULL, BEAR, UNKNOWN)
            
        Returns:
            Tuple of (passed, technicals_dict, rsi_hook_triggered, effective_threshold)
        """
        technicals = analyze_technicals(df)
        
        if "error" in technicals:
            print(f"[ANALYZER] Layer 3: {technicals['error']}")
            return False, technicals, False, RSI_OVERSOLD
        
        rsi = technicals.get('rsi')
        close = technicals.get('close')
        bb_lower = technicals.get('bb_lower')
        
        if rsi is None or close is None or bb_lower is None:
            print("[ANALYZER] Layer 3: Missing indicator data")
            return False, technicals, False, RSI_OVERSOLD
        
        # V2: Chameleon Mode - adjust RSI threshold based on market regime
        if CHAMELEON_MODE_ENABLED:
            if market_regime == "BULL":
                rsi_threshold = RSI_BULL_THRESHOLD
            elif market_regime == "BEAR":
                rsi_threshold = RSI_BEAR_THRESHOLD
            else:
                rsi_threshold = RSI_OVERSOLD
        else:
            rsi_threshold = RSI_OVERSOLD
        
        # V2: RSI Hook - check if RSI is crossing BACK above threshold
        rsi_hook_triggered = False
        rsi_prev = None
        
        if RSI_HOOK_ENABLED:
            # Calculate previous RSI from the dataframe
            from modules.indicators import calculate_rsi
            rsi_series = calculate_rsi(df)
            
            if len(rsi_series) >= 2:
                rsi_prev = float(rsi_series.iloc[-2]) if pd.notna(rsi_series.iloc[-2]) else None
                
                if rsi_prev is not None:
                    # RSI Hook: was below threshold, now at or above
                    rsi_hook_triggered = (rsi_prev < RSI_HOOK_THRESHOLD) and (rsi >= RSI_HOOK_THRESHOLD)
                    
                    if rsi_hook_triggered:
                        print(f"[ANALYZER] 🪝 RSI Hook triggered: {rsi_prev:.1f} → {rsi:.1f}")
        
        # Store previous RSI in technicals for result
        technicals['rsi_prev'] = rsi_prev
        
        # Check conditions
        below_bb = close <= bb_lower
        
        # V2: Accept if RSI Hook triggered OR traditional oversold
        if RSI_HOOK_ENABLED:
            # RSI Hook mode: either crossing back up from oversold OR currently oversold with hook
            rsi_condition = rsi_hook_triggered or (rsi < rsi_threshold and rsi_hook_triggered is False)
        else:
            # Traditional mode: just check if oversold
            rsi_condition = rsi < rsi_threshold
        
        passed = rsi_condition and below_bb
        
        if passed:
            hook_str = " (RSI Hook ✓)" if rsi_hook_triggered else ""
            print(f"[ANALYZER] Layer 3 ✓: RSI {rsi:.1f}{hook_str}, Threshold: {rsi_threshold}, BB Lower: {bb_lower:.6f}")
        else:
            reasons = []
            if not rsi_condition:
                if RSI_HOOK_ENABLED:
                    reasons.append(f"RSI {rsi:.1f} not hooking (prev: {rsi_prev:.1f if rsi_prev else 'N/A'})")
                else:
                    reasons.append(f"RSI {rsi:.1f} >= {rsi_threshold}")
            if not below_bb:
                reasons.append(f"Price {close:.6f} > BB Lower {bb_lower:.6f}")
            print(f"[ANALYZER] Layer 3 ✗: {', '.join(reasons)}")
        
        return passed, technicals, rsi_hook_triggered, rsi_threshold
    
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
    
    def check_multi_timeframe(self, symbol: str) -> Tuple[bool, Optional[float]]:
        """
        V3: Multi-timeframe confirmation.
        
        Check if RSI is also oversold on the confirmation timeframe (15m).
        
        Args:
            symbol: Trading pair
            
        Returns:
            Tuple of (passed, confirm_rsi)
        """
        if not MULTI_TIMEFRAME_ENABLED:
            return True, None
        
        try:
            # Fetch 15m OHLCV data
            ohlcv = self.scanner.get_ohlcv(symbol, timeframe=CONFIRM_TIMEFRAME, limit=50)
            if ohlcv is None or len(ohlcv) < 20:
                print(f"[ANALYZER] Multi-TF: Insufficient 15m data")
                return True, None  # Pass if no data (don't block trade)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate RSI on confirmation timeframe
            from modules.indicators import calculate_rsi
            confirm_rsi_series = calculate_rsi(df)
            confirm_rsi = float(confirm_rsi_series.iloc[-1]) if pd.notna(confirm_rsi_series.iloc[-1]) else None
            
            if confirm_rsi is None:
                return True, None
            
            passed = confirm_rsi <= MULTI_TF_RSI_THRESHOLD
            
            if passed:
                print(f"[ANALYZER] 📊 Multi-TF ✓: 15m RSI {confirm_rsi:.1f} <= {MULTI_TF_RSI_THRESHOLD}")
            else:
                print(f"[ANALYZER] 📊 Multi-TF ✗: 15m RSI {confirm_rsi:.1f} > {MULTI_TF_RSI_THRESHOLD}")
            
            return passed, confirm_rsi
            
        except Exception as e:
            print(f"[ANALYZER] Multi-TF error: {e}")
            return True, None  # Pass on error
    
    def check_capitulation(self, technicals: dict) -> Tuple[bool, float]:
        """
        V3: Volume capitulation detection.
        
        Detect if volume is 5x+ average, indicating panic selling exhaustion.
        
        Args:
            technicals: Technical analysis dictionary
            
        Returns:
            Tuple of (is_capitulation, volume_ratio)
        """
        if not CAPITULATION_ENABLED:
            return False, 0.0
        
        volume = technicals.get('volume')
        volume_ma = technicals.get('volume_ma')
        
        if volume is None or volume_ma is None or volume_ma == 0:
            return False, 0.0
        
        ratio = volume / volume_ma
        is_capitulation = ratio >= CAPITULATION_VOLUME_MULT
        
        if is_capitulation:
            print(f"[ANALYZER] 🔥 CAPITULATION ✓: Volume {ratio:.1f}x (>= {CAPITULATION_VOLUME_MULT}x)")
        
        return is_capitulation, ratio
    
    def analyze(self, symbol: str, ticker_data: dict = None) -> AnalysisResult:
        """
        Run full 5-layer analysis on a symbol.
        
        V3 Enhancements:
        - Market regime detection (Chameleon Mode)
        - Zombie Filter (liquidity check)
        - RSI Hook integration
        - Multi-timeframe confirmation (5m + 15m)
        - Volume capitulation detection
        
        Args:
            symbol: Trading pair to analyze (e.g., "SUI/USDT")
            ticker_data: Optional ticker data to avoid refetching
            
        Returns:
            AnalysisResult with all layer results and targets
        """
        print(f"\n{'='*50}")
        print(f"[ANALYZER] Starting V3 analysis for {symbol}")
        print('='*50)
        
        result = AnalysisResult(symbol=symbol, is_buy_signal=False)
        
        # V2: Get market regime for Chameleon Mode
        if CHAMELEON_MODE_ENABLED:
            regime, btc_price, btc_sma = self.scanner.get_market_regime()
            result.market_regime = regime
            if regime != "UNKNOWN":
                print(f"[ANALYZER] 🦎 Chameleon Mode: {regime} market (BTC: ${btc_price:,.0f}, SMA50: ${btc_sma:,.0f})")
        
        # V2: Zombie Filter (Liquidity Check)
        if ZOMBIE_FILTER_ENABLED:
            zombie_ok, liquidity_ratio = self.scanner.check_zombie_filter(symbol, ticker_data)
            result.zombie_filter_ok = zombie_ok
            result.liquidity_ratio = liquidity_ratio
            
            if not zombie_ok:
                result.rejection_reason = f"Zombie Filter: Low liquidity ({liquidity_ratio:.3f})"
                print(f"[ANALYZER] 🧟 Zombie Filter ✗: Liquidity ratio {liquidity_ratio:.3f} < {ZOMBIE_FILTER_ENABLED}")
                return result
            print(f"[ANALYZER] 🧟 Zombie Filter ✓: Liquidity ratio {liquidity_ratio:.3f}")
        else:
            result.zombie_filter_ok = True
        
        # Layer 1: BTC Sentiment
        layer1_ok, btc_change = self.check_layer1_btc_sentiment()
        result.layer1_btc_ok = layer1_ok
        result.btc_change = btc_change
        
        if not layer1_ok:
            result.rejection_reason = f"Layer 1: BTC dropping {btc_change:.2f}%"
            return result
        
        # Layer 2: Order Book
        layer2_ok, bid_ask_ratio = self.check_layer2_orderbook(symbol)
        result.layer2_orderbook_ok = layer2_ok
        result.bid_ask_ratio = bid_ask_ratio
        
        if not layer2_ok:
            result.rejection_reason = f"Layer 2: Weak order book ({bid_ask_ratio:.2f})"
            return result
        
        # Fetch OHLCV for Layer 3, 4, 5
        ohlcv = self.scanner.get_ohlcv(symbol, ANALYSIS_TIMEFRAME, OHLCV_LIMIT)
        if ohlcv is None or len(ohlcv) < 30:
            result.rejection_reason = "Insufficient OHLCV data"
            return result
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        technicals = analyze_technicals(df)
        
        # Store price and ATR
        result.price = df['close'].iloc[-1]
        result.atr = technicals.get('atr')
        
        # Layer 3: Technical Confluence (V2: with RSI Hook and Chameleon Mode)
        layer3_ok, technicals_updated, rsi_hook_triggered, effective_threshold = self.check_layer3_technical(
            df, 
            market_regime=result.market_regime
        )
        result.layer3_technical_ok = layer3_ok
        result.rsi = technicals_updated.get('rsi')
        result.rsi_prev = technicals_updated.get('rsi_prev')
        result.bb_lower = technicals_updated.get('bb_lower')
        result.rsi_hook_ok = rsi_hook_triggered
        result.effective_rsi_threshold = effective_threshold
        
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
        
        # V3: Check volume capitulation
        is_capitulation, cap_ratio = self.check_capitulation(technicals)
        result.capitulation_ok = is_capitulation
        result.capitulation_volume_ratio = cap_ratio
        
        # V3: Multi-timeframe confirmation
        multi_tf_ok, confirm_rsi = self.check_multi_timeframe(symbol)
        result.multi_tf_ok = multi_tf_ok
        result.confirm_rsi = confirm_rsi
        
        if not multi_tf_ok:
            result.rejection_reason = f"Multi-TF: 15m RSI too high ({confirm_rsi:.1f})"
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
        
        # Build status string
        extras = []
        if rsi_hook_triggered:
            extras.append("RSI Hook")
        if is_capitulation:
            extras.append("CAPITULATION")
        if multi_tf_ok and confirm_rsi:
            extras.append("Multi-TF")
        
        extras_str = " + ".join(extras) if extras else ""
        regime_str = f" [{result.market_regime}]" if result.market_regime != "UNKNOWN" else ""
        print(f"\n🎯 [ANALYZER] ALL LAYERS PASSED - BUY SIGNAL{regime_str} {extras_str} for {symbol}")
        
        return result


# Singleton instance
_analyzer_instance = None

def get_analyzer() -> Analyzer:
    """Get the global analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = Analyzer()
    return _analyzer_instance
