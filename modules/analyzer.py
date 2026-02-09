"""
Sniper V5 - The Analyzer (Enhanced 5-Layer Filter)
=====================================================
The brain of the trading system. Implements the enhanced 5-layer safety algorithm.

V5 Features:
- Automatic Market Regime integration
- Regime-specific RSI/Volume thresholds
- Handler-aware analysis

Legacy Features:
- RSI Hook, Zombie Filter, Multi-Timeframe, Volume Capitulation
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
import pandas as pd

from config.settings import (
    BTC_SENTIMENT_THRESHOLD,
    ORDERBOOK_DEPTH, ORDERBOOK_BID_ASK_RATIO,
    RSI_OVERSOLD, RSI_HOOK_ENABLED, RSI_HOOK_THRESHOLD, RSI_HOOK_STRICT,
    RSI_BULL_THRESHOLD, RSI_BEAR_THRESHOLD, CHAMELEON_MODE_ENABLED,
    ZOMBIE_FILTER_ENABLED,
    VOLUME_SPIKE_MULTIPLIER,
    TAKE_PROFIT_ATR_MULTIPLIER, STOP_LOSS_ATR_MULTIPLIER,
    ANALYSIS_TIMEFRAME, OHLCV_LIMIT,
    MIN_TARGET_PROFIT_PCT,
    MULTI_TIMEFRAME_ENABLED, CONFIRM_TIMEFRAME, MULTI_TF_RSI_THRESHOLD,
    CAPITULATION_ENABLED, CAPITULATION_VOLUME_MULT,
    # V4: Bull Mode settings
    BULL_MODE_ENABLED, BULL_RSI_BREAKOUT, BULL_BREAKOUT_PERIOD,
    BULL_TAKE_PROFIT_ATR, BULL_STOP_LOSS_ATR,
    COOLDOWN_MINUTES, BLACKLIST_LOSSES, BLACKLIST_DURATION_HOURS,
    MIN_STOP_LOSS_PCT,
    # V4.1: Conditional RSI Hook Relaxation
    RSI_HOOK_RELAXATION_ENABLED, RSI_HOOK_RELAXATION_VOLUME_MULT
)
from utils.helpers import is_weekend
from modules.scanner import get_scanner
from modules.indicators import analyze_technicals, get_atr_targets, calculate_rsi, calculate_highest_high
from utils.logger import load_trades
from datetime import datetime, timedelta


@dataclass
class AnalysisResult:
    """Result of the 5-layer analysis."""
    symbol: str
    is_buy_signal: bool
    
    # Layer results
    layer1_btc_ok: bool = False
    # ... (keeping existing fields implicitly via ... but for replace_file_content I need to be precise or use mulitple chunks if they are far apart)
    # Actually, I should just add the imports and the method.
    
    # Let me try to do it in 2 chunks to be safe.
    
    # Method implementation will be added to Analyzer class.
    # Logic in analyze() will be added at the start.

    # Wait, I cannot use "..." in ReplacementContent if I want to match exactly. 
    # I will use separate chunks.

# Chunk 1: Imports
# Chunk 2: Add check_trade_frequency_limits method to Analyzer 
# Chunk 3: Call it in analyze()



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
    
    # V4: Bull Mode (Trend-Following)
    bull_mode_active: bool = False  # True if using trend-following
    rsi_breakout_ok: bool = False   # RSI crossed above threshold
    price_breakout_ok: bool = False # Price above N-period high
    highest_high: Optional[float] = None
    
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
        
        V4: Also checks 1-hour BTC change for flash crash detection.
        
        Returns:
            Tuple of (passed, btc_change_pct)
        """
        from modules.capital_manager import get_capital_manager
        from config.settings import BTC_CRASH_THRESHOLD
        
        capital_manager = get_capital_manager()
        
        # V4: Check Kill Switch first
        is_killed, minutes_left = capital_manager.get_kill_switch_status()
        if is_killed:
            print(f"[ANALYZER] Layer 1 ✗: KILL SWITCH ACTIVE ({minutes_left} mins remaining)")
            return False, 0.0
        
        # V4: Check 1-hour BTC change for flash crash detection
        btc_1h_change = self.scanner.get_btc_change(lookback_minutes=60)
        if btc_1h_change is not None and btc_1h_change <= BTC_CRASH_THRESHOLD:
            print(f"[ANALYZER] 🚨 BTC CRASH DETECTED: {btc_1h_change:.2f}% in 1 hour!")
            capital_manager.trigger_kill_switch()
            from utils.notifier import send_message
            send_message(f"🚨 *KILL SWITCH ACTIVATED*\n\nBTC dropped {btc_1h_change:.2f}% in 1 hour.\nAll trading paused for 2 hours.")
            return False, btc_1h_change
        
        # Original 15-min check
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
    
    def check_trade_frequency_limits(self, symbol: str) -> bool:
        """
        V3: Check Cooldown and Blacklist rules.
        
        Rules:
        1. Cooldown: Cannot buy same coin within COOLDOWN_MINUTES of ANY sale.
        2. Blacklist: Cannot buy if 2+ losses in last 24h.
        """
        trades = load_trades()
        now = datetime.now()
        
        # Filter trades for this symbol
        symbol_trades = [t for t in trades if t['symbol'] == symbol and t['status'] == 'CLOSED']
        if not symbol_trades:
            # print(f"[ANALYZER] No previous trades for {symbol}. Cooldown check passed.")
            return True
            
        # Helper to parse time safely
        def parse_time(t_str):
            if not t_str: return None
            try:
                return datetime.fromisoformat(t_str)
            except ValueError:
                return None

        # Filter for valid exit times
        valid_trades = []
        for t in symbol_trades:
            exit_time = parse_time(t.get('exit_time'))
            if exit_time:
                t['_exit_dt'] = exit_time # Store for sorting
                valid_trades.append(t)
        
        if not valid_trades:
            return True
            
        # Sort by exit time (newest first)
        valid_trades.sort(key=lambda x: x['_exit_dt'], reverse=True)
        last_trade = valid_trades[0]
        
        # 1. Check Cooldown
        last_exit_time = last_trade['_exit_dt']
        minutes_since_exit = (now - last_exit_time).total_seconds() / 60
        
        if minutes_since_exit < COOLDOWN_MINUTES:
            print(f"[ANALYZER] 🧊 COOLDOWN: {symbol} Sold {minutes_since_exit:.1f}m ago (Limit: {COOLDOWN_MINUTES}m). REJECTED.")
            return False
        
        # 2. Check Blacklist (Cursed Coin)
        cutoff_time = now - timedelta(hours=BLACKLIST_DURATION_HOURS)
        recent_losses = 0
        
        for trade in valid_trades:
            exit_time = trade['_exit_dt']
            if exit_time < cutoff_time:
                break # Trades are sorted, so we can stop
                
            if trade['pnl_pct'] < 0:
                recent_losses += 1
        
        if recent_losses >= BLACKLIST_LOSSES:
            print(f"[ANALYZER] ☠️ BLACKLIST: {symbol} has {recent_losses} losses in last {BLACKLIST_DURATION_HOURS}h. CURSED.")
            return False
            
        return True
    
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
        market_regime: str = "UNKNOWN",
        rsi_limit_override: Optional[float] = None
    ) -> Tuple[bool, dict, bool, float]:
        """
        Layer 3: Check RSI + Bollinger Bands confluence.
        
        V2 Enhancements:
        - RSI Hook: Buy when RSI crosses BACK above threshold (not while falling)
        - Chameleon Mode: Dynamic RSI threshold based on market regime
        
        V4 Enhancement:
        - rsi_limit_override: Force a specific RSI threshold (from STRATEGY_MAP)
        
        Args:
            df: OHLCV DataFrame
            market_regime: Current market regime (BULL, BEAR, UNKNOWN)
            rsi_limit_override: Optional override for RSI threshold
            
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
        
        # Calculate Effective Threshold
        if rsi_limit_override is not None:
             # V4: Use the Strategy's RSI Limit directly
            rsi_threshold = rsi_limit_override
            # print(f"[ANALYZER] 🔧 Using Strategy RSI Limit: {rsi_threshold}")
        elif CHAMELEON_MODE_ENABLED:
            if market_regime == "BULL":
                rsi_threshold = RSI_BULL_THRESHOLD
            elif market_regime == "BEAR":
                rsi_threshold = RSI_BEAR_THRESHOLD
            else:
                rsi_threshold = RSI_OVERSOLD
        else:
            rsi_threshold = RSI_OVERSOLD

        # V4: Weekend Mode Override - Deprecated in favor of STRATEGY_MAP, but kept locally if check fails
        # The calling function should handle strategy selection.
        # We removed the direct WEEKEND_MODE check here.
        
        # V2: RSI Hook - check if RSI is crossing BACK above threshold
        rsi_hook_triggered = False
        rsi_prev = None
        
        if RSI_HOOK_ENABLED:
            # Re-calculate RSI series to get previous value
            # Optimization: could pass full series to analyze_technicals?
            from modules.indicators import calculate_rsi
            rsi_series = calculate_rsi(df)
            
            if len(rsi_series) >= 2:
                rsi_prev = float(rsi_series.iloc[-2]) if pd.notna(rsi_series.iloc[-2]) else None
                
                if rsi_prev is not None:
                     # V4.3 Fix: Adaptive Hook Logic
                     # If Threshold is high (e.g. 50 for Bull), Buy the Dip (Uptick within dip).
                     # If Threshold is low (e.g. 30 for Bear), Wait for Confirmation (Crossover out of oversold).
                     if rsi_threshold >= 45:
                         # Bull Mode: Catch the turn up even if still below 50
                         rsi_hook_triggered = (rsi_prev < rsi_threshold) and (rsi > rsi_prev)
                     else:
                         # Bear Mode: Wait for breakdown recovery
                         rsi_hook_triggered = (rsi_prev < rsi_threshold) and (rsi >= rsi_threshold)
                     
                     if rsi_hook_triggered:
                         print(f"[ANALYZER] 🪝 RSI Hook triggered: {rsi_prev:.1f} → {rsi:.1f} (Threshold {rsi_threshold})")

        technicals['rsi_prev'] = rsi_prev
        
        bb_tolerance_multiplier = 1.005
        below_bb = close <= (bb_lower * bb_tolerance_multiplier)
        
        # Logic Matrix
        if RSI_HOOK_STRICT:
            passed = rsi_hook_triggered
        else:
            # Loose Mode:
            # Pass if Hook Triggered OR (RSI < Threshold AND Below BB)
            if rsi_hook_triggered:
                passed = True
            else:
                passed = (rsi < rsi_threshold) and below_bb
        
        if passed:
            hook_str = " (RSI Hook ✓)" if rsi_hook_triggered else ""
            print(f"[ANALYZER] Layer 3 ✓: RSI {rsi:.1f}{hook_str}, Threshold: {rsi_threshold}, BB Lower: {bb_lower:.6f}")
        else:
            reasons = []
            if RSI_HOOK_STRICT:
                reasons.append("STRICT MODE: RSI Hook required")
            else:
                if not (rsi < rsi_threshold):
                     reasons.append(f"RSI {rsi:.1f} >= {rsi_threshold}")
                if not below_bb and not rsi_hook_triggered:
                     reasons.append(f"Price {close:.6f} > BB Lower {bb_lower:.6f}")
            print(f"[ANALYZER] Layer 3 ✗: {', '.join(reasons)}")
        
        return passed, technicals, rsi_hook_triggered, rsi_threshold
    
    def check_rsi_hook_relaxation_allowed(
        self,
        strategy_name: str,
        btc_change: float,
        volume_ratio: float
    ) -> bool:
        """
        V4.1: Check if RSI Hook can be relaxed for this specific trade.
        
        Relaxation is only allowed when ALL conditions are met:
        1. RSI_HOOK_RELAXATION_ENABLED is True
        2. Strategy is BULL_WEEKDAY
        3. BTC 15-minute change > 0
        4. Volume >= 2.5x average
        
        SAFETY: RSI Hook remains STRICT by default.
        This only bypasses the hook for THIS SINGLE TRADE.
        
        Args:
            strategy_name: Active strategy name
            btc_change: BTC 15-minute price change
            volume_ratio: Current volume / average volume
            
        Returns:
            True if relaxation is allowed
        """
        if not RSI_HOOK_RELAXATION_ENABLED:
            return False
        
        # Condition 1: Must be BULL_WEEKDAY strategy
        if strategy_name != "BULL_WEEKDAY":
            return False
        
        # Condition 2: BTC must be going up
        if btc_change <= 0:
            return False
        
        # Condition 3: Volume must be >= 2.5x average
        if volume_ratio < RSI_HOOK_RELAXATION_VOLUME_MULT:
            return False
        
        print(f"[ANALYZER] 🔓 V4.1 RSI Hook RELAXATION allowed: BULL_WEEKDAY + BTC +{btc_change:.2f}% + Volume {volume_ratio:.1f}x")
        return True

    def check_layer3_bull_technical(
        self, 
        df: pd.DataFrame
    ) -> Tuple[bool, dict, bool, bool]:
        """
        V4 Bull Mode Layer 3: RSI momentum breakout + price breakout.
        
        Entry Conditions:
        1. RSI crosses ABOVE BULL_RSI_BREAKOUT (from below) - momentum building
        2. Price is above N-period highest high - breakout confirmation
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            Tuple of (passed, technicals_dict, rsi_breakout_ok, price_breakout_ok)
        """
        technicals = analyze_technicals(df)
        
        if "error" in technicals:
            print(f"[ANALYZER] Bull Layer 3: {technicals['error']}")
            return False, technicals, False, False
        
        rsi = technicals.get('rsi')
        close = technicals.get('close')
        
        if rsi is None or close is None:
            print("[ANALYZER] Bull Layer 3: Missing indicator data")
            return False, technicals, False, False
        
        # Calculate RSI breakout (crossing above threshold)
        rsi_series = calculate_rsi(df)
        rsi_prev = None
        rsi_breakout_ok = False
        
        if len(rsi_series) >= 2:
            rsi_prev = float(rsi_series.iloc[-2]) if pd.notna(rsi_series.iloc[-2]) else None
            
            if rsi_prev is not None:
                # RSI Breakout: was below threshold, now above
                rsi_breakout_ok = (rsi_prev < BULL_RSI_BREAKOUT) and (rsi >= BULL_RSI_BREAKOUT)
                
                if rsi_breakout_ok:
                    print(f"[ANALYZER] 🚀 Bull RSI Breakout: {rsi_prev:.1f} → {rsi:.1f} (crossed {BULL_RSI_BREAKOUT})")
        
        technicals['rsi_prev'] = rsi_prev
        
        # Calculate price breakout (above N-period high)
        highest_high_series = calculate_highest_high(df, period=BULL_BREAKOUT_PERIOD)
        
        # Use the PREVIOUS bar's highest high (not current, to avoid look-ahead)
        if len(highest_high_series) >= 2 and pd.notna(highest_high_series.iloc[-2]):
            highest_high = float(highest_high_series.iloc[-2])
            price_breakout_ok = close > highest_high
            technicals['highest_high'] = highest_high
            
            if price_breakout_ok:
                print(f"[ANALYZER] 🚀 Price Breakout: {close:.6f} > {highest_high:.6f} ({BULL_BREAKOUT_PERIOD}-period high)")
        else:
            highest_high = None
            price_breakout_ok = False
            technicals['highest_high'] = None
        
        # Both conditions must pass for Bull Mode
        passed = rsi_breakout_ok and price_breakout_ok
        
        if passed:
            print(f"[ANALYZER] Bull Layer 3 ✓: RSI Breakout + Price Breakout confirmed")
        else:
            reasons = []
            if not rsi_breakout_ok:
                rsi_prev_str = f"{rsi_prev:.1f}" if rsi_prev else "N/A"
                reasons.append(f"RSI {rsi:.1f} not breaking out (prev: {rsi_prev_str}, threshold: {BULL_RSI_BREAKOUT})")
            if not price_breakout_ok:
                hh_str = f"{highest_high:.6f}" if highest_high else "N/A"
                reasons.append(f"Price {close:.6f} not above {BULL_BREAKOUT_PERIOD}-period high ({hh_str})")
            print(f"[ANALYZER] Bull Layer 3 ✗: {', '.join(reasons)}")
        
        return passed, technicals, rsi_breakout_ok, price_breakout_ok
    
    def check_layer4_volume(self, technicals: dict, volume_spike_override: float = None) -> tuple[bool, float]:
        """
        Layer 4: Check volume spike.
        
        V5: Now accepts regime-specific volume spike multiplier.
        
        Args:
            technicals: Technical analysis dictionary
            volume_spike_override: Optional regime-specific multiplier
            
        Returns:
            Tuple of (passed, volume_ratio)
        """
        volume = technicals.get('volume')
        volume_ma = technicals.get('volume_ma')
        
        if volume is None or volume_ma is None or volume_ma == 0:
            print("[ANALYZER] Layer 4: Missing volume data")
            return False, 0.0
        
        ratio = volume / volume_ma
        required = volume_spike_override if volume_spike_override else VOLUME_SPIKE_MULTIPLIER
        passed = ratio >= required
        
        if passed:
            print(f"[ANALYZER] Layer 4 ✓: Volume {ratio:.2f}x average >= {required}x required")
        else:
            print(f"[ANALYZER] Layer 4 ✗: Volume {ratio:.2f}x average < {required}x (weak momentum)")
        
        return passed, ratio
    
    # V4: Dynamic SL based on strategy (passed as min_stop_loss_pct_override)
    def calculate_layer5_targets(self, entry_price: float, atr: float, min_stop_loss_pct_override: Optional[float] = None) -> Tuple[float, float]:
        """
        Layer 5: Calculate ATR-based take profit and stop loss.
        
        Args:
            entry_price: Expected entry price
            atr: Current ATR value
            min_stop_loss_pct_override: Optional override for minimum stop loss percentage
            
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
        
        # V4: Use override or default constant
        min_sl_pct = min_stop_loss_pct_override if min_stop_loss_pct_override is not None else MIN_STOP_LOSS_PCT
        
        # V3: Minimum Stop Loss Floor (Safety)
        # If ATR Stop is tighter than limit, widen it.
        # If ATR Stop is wider (e.g. 2.5%), keep it.
        if abs(sl_pct) < min_sl_pct:
            # print(f"[ANALYZER] 🛡️ Stop Loss Adjustment: Calculated {abs(sl_pct):.2f}% < {min_sl_pct}%. Widening to {min_sl_pct}%.")
            sl_pct = -min_sl_pct
            stop_loss = entry_price * (1 + (sl_pct / 100))
        
        # V3: Minimum Profit Filter (Noise Reduction)
        if tp_pct < MIN_TARGET_PROFIT_PCT:
            print(f"[ANALYZER] Layer 5 ✗: Profit Potential {tp_pct:.2f}% < {MIN_TARGET_PROFIT_PCT}% (Too Risky/Noise)")
            return 0.0, 0.0
        
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
        print(f"[ANALYZER] Starting V5 analysis for {symbol}")
        print('='*50)
        
        # V5: Dynamic Strategy Configuration from Regime System
        strategy = self.scanner.get_active_strategy()
        regime_name = strategy.get('name', 'TRANSITIONAL')
        
        # V5: Extract Strategy Settings from regime config
        rsi_limit = strategy.get('rsi_limit', 32)
        min_stop_loss_pct = strategy.get('min_stop_loss_pct', 1.5)
        volume_spike_mult = strategy.get('volume_spike_mult', 1.5)
        rsi_hook_strict = strategy.get('rsi_hook_strict', True)
        
        print(f"[ANALYZER] 🧠 Regime: {regime_name} | RSI≤{rsi_limit} | VolSpike≥{volume_spike_mult}x | SL: {min_stop_loss_pct}%")
        
        result = AnalysisResult(symbol=symbol, is_buy_signal=False)
        
        # V3: Check Cooldowns & Blacklists
        if not self.check_trade_frequency_limits(symbol):
            result.rejection_reason = "Cooldown / Blacklist active"
            return result
        
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
        
        
        if result.atr:
            result.atr_stop_loss_pct = (result.atr * STOP_LOSS_ATR_MULTIPLIER / result.price) * 100
        
        # =========================================================
        # V4: Unified Strategy Logic (Sniper, Bunker, Rally, Volatility)
        # =========================================================
        # We use the standard 5-Layer approach but with DYNAMIC thresholds
        # passed from the active strategy.
        
        # Layer 3: Technical Confluence (RSI + BB + Hook)
        
        if regime_name == "TRENDING":
            # V4: Bull Mode (Hybrid: Breakout OR Dip Buy)
            
            # 1. Check Breakout (Momentum)
            bk_ok, bk_tech, rsi_bk, prc_bk = self.check_layer3_bull_technical(df)
            
            if bk_ok:
                layer3_ok = True
                result.bull_mode_active = True
                result.rsi_breakout_ok = rsi_bk
                result.price_breakout_ok = prc_bk
                result.rsi = bk_tech.get('rsi')
                result.highest_high = bk_tech.get('highest_high')
                technicals_updated = bk_tech
                
                print(f"[ANALYZER] 🐂 Bull Breakout Triggered! RSI {result.rsi:.2f}")

            else:
                # 2. Fallback to Dip Buy (Standard Technicals)
                # Uses strategy.rsi_limit (e.g. 50)
                # This catches pullbacks in the trend
                effective_rsi_threshold = rsi_limit
                
                layer3_ok, technicals_updated, rsi_hook_triggered, used_threshold = self.check_layer3_technical(
                    df, 
                    market_regime=result.market_regime,
                    rsi_limit_override=rsi_limit
                )
                
                result.rsi = technicals_updated.get('rsi')
                result.rsi_prev = technicals_updated.get('rsi_prev')
                result.bb_lower = technicals_updated.get('bb_lower')
                result.rsi_hook_ok = rsi_hook_triggered
                result.effective_rsi_threshold = used_threshold
                
                if not layer3_ok:
                     result.rejection_reason = "Layer 3: Bull Breakout & Dip Buy conditions failed"
                     return result
                else:
                     result.bull_mode_active = True
                     print(f"[ANALYZER] 🐂 Bull Dip Buy Triggered! RSI {result.rsi:.2f} < {used_threshold}")

        else:
            # Standard Mean Reversion Logic (Same as before)
            # V4 Override: Use strategy.rsi_limit instead of constants
            effective_rsi_threshold = rsi_limit
            
            # Pass dynamic threshold to check_layer3
            layer3_ok, technicals_updated, rsi_hook_triggered, used_threshold = self.check_layer3_technical(
                df, 
                market_regime=result.market_regime,
                rsi_limit_override=rsi_limit
            )
            
            result.layer3_technical_ok = layer3_ok
            result.rsi = technicals_updated.get('rsi')
            result.rsi_prev = technicals_updated.get('rsi_prev')
            result.bb_lower = technicals_updated.get('bb_lower')
            result.rsi_hook_ok = rsi_hook_triggered
            result.effective_rsi_threshold = used_threshold
            
            if not layer3_ok:
                # V4.2: Fix misleading rejection message
                if RSI_HOOK_STRICT and not rsi_hook_triggered:
                    result.rejection_reason = f"Layer 3: RSI Hook not triggered (RSI {result.rsi:.1f}, need reversal)"
                else:
                    result.rejection_reason = f"Layer 3: Technicals (RSI {result.rsi:.1f} >= {used_threshold})"
                return result
        
        result.layer3_technical_ok = True
        
        # Layer 4: Volume Validation
        layer4_ok, volume_ratio = self.check_layer4_volume(technicals, volume_spike_override=volume_spike_mult)
        result.layer4_volume_ok = layer4_ok
        result.volume_ratio = volume_ratio
        
        if not layer4_ok:
            result.rejection_reason = f"Layer 4: Volume too low ({volume_ratio:.2f} < {volume_spike_mult})"
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
            take_profit, stop_loss = self.calculate_layer5_targets(
                result.price, result.atr,
                min_stop_loss_pct_override=min_stop_loss_pct
            )
            
            # V3: Check if targets are valid (non-zero)
            if take_profit == 0 or stop_loss == 0:
                result.rejection_reason = "Layer 5: Profit potential too low (Noise Filter)"
                return result
                
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
