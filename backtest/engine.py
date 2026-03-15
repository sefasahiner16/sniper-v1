import pandas as pd
import numpy as np
import os
import glob
import sys
import argparse
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.analyzer import Analyzer, AnalysisResult
from config.settings import (
    STOP_LOSS_ATR_MULTIPLIER, TAKE_PROFIT_ATR_MULTIPLIER,
    RSI_PERIOD, BTC_SMA_PERIOD, BTC_RSI_PERIOD
)

class BacktestScanner:
    """
    Mock Scanner that serves historical data based on current simulation time.
    """
    def __init__(self, full_df, current_idx):
        self.full_df = full_df
        self.current_idx = current_idx
        # OPTIMIZATION: Lookup for pre-calculated regimes
        # Map: pd.Timestamp (date only) -> (regime_str, current_price, sma_val)
        self.regime_lookup = {} 
        self._precalculate_regimes()
        
        # Default strategy for now
        self.active_strategy = {
            'name': 'BACKTEST',
            'min_volume': 0,
            'rsi_limit': 32,
            'stop_loss_pct': 1.5,
            'volume_spike_mult': 1.5
        }

    def _precalculate_regimes(self):
        try:
            print("   [Scanner] Pre-calculating Market Regimes...", end='', flush=True)
            # 1. Resample full DF to Daily
            # Copy to avoid messing up main DF
            daily_calc_df = self.full_df.copy()
            # Ensure datetime index
            if 'datetime' in daily_calc_df.columns:
                daily_calc_df.set_index('datetime', inplace=True)
            
            daily_df = daily_calc_df.resample('D').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            })
            
            # 2. Calculate SMA and RSI on Daily Data
            from config.settings import BTC_SMA_PERIOD, BTC_RSI_PERIOD
            
            daily_df['sma'] = daily_df['close'].rolling(window=BTC_SMA_PERIOD).mean()
            
            delta = daily_df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=BTC_RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=BTC_RSI_PERIOD).mean()
            rs = gain / loss
            daily_df['rsi'] = 100 - (100 / (1 + rs))
            
            # 3. Populate Lookup
            daily_df.ffill(inplace=True)
            
            for dt, row in daily_df.iterrows():
                # Timestamp to midnight
                date_key = pd.Timestamp(dt).normalize().tz_localize('UTC') if pd.Timestamp(dt).tzinfo is None else pd.Timestamp(dt).normalize()
                
                price = float(row['close'])
                sma = float(row['sma']) if pd.notna(row['sma']) else 0
                rsi_val = float(row['rsi']) if pd.notna(row['rsi']) else 0
                
                regime = "BEAR"
                if price > sma and rsi_val > 50:
                    regime = "BULL"
                    
                self.regime_lookup[date_key] = (regime, price, sma)
            print(" Done.")
            print(f"   [Scanner] Cached {len(self.regime_lookup)} daily regimes.")
        except Exception as e:
            print(f"   [Scanner] Regime pre-calc failed: {e}")

    def get_ohlcv(self, symbol, timeframe='15m', limit=100):
        # Return slice ending at current_idx (inclusive of the 'current' closed candle?
        # Usually backtest loops iterate over 'completed' candles.
        # So current_idx is the last completed candle.
        start = max(0, self.current_idx - limit + 1)
        return self.full_df.iloc[start : self.current_idx + 1]

    def get_btc_change(self, lookback_minutes=15):
        # Calculate change from history
        # Assuming 15m timeframe
        lookback_candles = lookback_minutes // 15
        if self.current_idx < lookback_candles:
            return 0.0
            
        current_close = self.full_df.iloc[self.current_idx]['close']
        old_close = self.full_df.iloc[self.current_idx - lookback_candles]['close']
        
        return ((current_close - old_close) / old_close) * 100

    def get_market_regime(self):
        # OPTIMIZATION: Check lookup first
        current_dt = self.full_df.iloc[self.current_idx]['datetime']
        # Normalize to date (midnight UTC)
        current_date = current_dt.normalize()
        
        if current_date in self.regime_lookup:
             return self.regime_lookup[current_date]

        # Fallback to slow method (should not happen if vectorized correctly)
        # 1. Start from current_idx, look back 50 days approx (50 * 96 candles)
        lookback = 4800 # 50 days * 96 candles
        if self.current_idx < lookback:
            return "UNKNOWN", 0, 0
            
        slice_df = self.full_df.iloc[self.current_idx - lookback : self.current_idx + 1]
        
        # Resample to Daily for SMA/RSI
        daily_df = slice_df.resample('D', on='datetime').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        })
        
        if len(daily_df) < BTC_SMA_PERIOD:
            return "UNKNOWN", 0, 0
            
        current_price = slice_df.iloc[-1]['close']
        
        # Calc SMA
        sma = daily_df['close'].rolling(window=BTC_SMA_PERIOD).mean().iloc[-1]
        
        # Calc RSI (14 day)
        delta = daily_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=BTC_RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=BTC_RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        
        regime = "BEAR"
        if current_price > sma and rsi_val > 50:
             regime = "BULL"
             
        return regime, current_price, sma

    def get_active_strategy(self):
        # In a real scenario, this would depend on get_market_regime logic
        # For backtest, let's use the real Scanner if possible, OR
        # just implement the basic mapping here.
        
        # Let's try to allow the Analyzer to call 'get_market_regime' on US
        # avoiding circular dependency issues? No, Analyzer calls scanner.get_active_strategy()
        
        regime, _, _ = self.get_market_regime()
        
        # Minimal mapping from scanner.py
        if regime == "BULL": # TRENDING
             # RELAXED: RSI < 50 for Bull Market Dips (was 40)
             # V4.2 Tune: Relax Volume to 1.0 (Average) for Dip Buys
             return {'name': 'TRENDING', 'rsi_limit': 50, 'stop_loss_pct': 2.5, 'volume_spike_mult': 1.0}
        else: # TRANSITIONAL / QUIET (simplifying)
             return {'name': 'TRANSITIONAL', 'rsi_limit': 34, 'stop_loss_pct': 2.0, 'volume_spike_mult': 1.5}
        
    def check_zombie_filter(self, symbol, ticker_data=None):
        return True, 10.0 # Always pass for major pairs

    def get_orderbook(self, symbol, limit=20):
        # Mock depth
        return {'bids': [[1, 1000]], 'asks': [[1, 1000]]} # Neutral

    def get_btc_volatility(self):
        return 0.01 # Mock

    def get_coin_sector(self, symbol):
        return "DEFAULT"


class BacktestEngine:
    def __init__(self, symbol='BTC/USDT', start_date='2022-02-01', end_date=None, output_dir=None):
        self.symbol = symbol
        self.symbol_clean = symbol.replace('/', '_')
        self.start_date = pd.to_datetime(start_date).tz_localize('UTC')
        self.end_date = pd.to_datetime(end_date).tz_localize('UTC') if end_date else pd.Timestamp.now(tz='UTC')
        self.data_dir = os.path.join('data', 'historical', self.symbol_clean)
        self.output_dir = output_dir
        self.df = None
        
    def load_data(self):
        print(f"[INFO] Loading data for {self.symbol}...")
        files = sorted(glob.glob(os.path.join(self.data_dir, "*.csv")))
        dfs = []
        for f in files:
            try:
                # Extract date from filename YYYY_MM.csv to filter efficiently?
                # Or just load all and filter
                df = pd.read_csv(f)
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                dfs.append(df)
            except Exception as e:
                print(f"Error loading {f}: {e}")
                
        if not dfs:
            print("❌ No data found!")
            return False
            
        full_df = pd.concat(dfs)
        full_df.sort_values('datetime', inplace=True)
        full_df.reset_index(drop=True, inplace=True)
        
        print(f"DEBUG: Full DF size: {len(full_df)}")
        if not full_df.empty:
            print(f"DEBUG: First row date: {full_df['datetime'].iloc[0]}")
            print(f"DEBUG: Last row date: {full_df['datetime'].iloc[-1]}")
            print(f"DEBUG: Filter Start: {self.start_date}")
            print(f"DEBUG: Filter End: {self.end_date}")
        
        # Filter Date Range
        mask = (full_df['datetime'] >= self.start_date) & (full_df['datetime'] <= self.end_date)
        self.df = full_df[mask].reset_index(drop=True)
        
        print(f"Loaded {len(self.df)} candles ({self.df['datetime'].min()} to {self.df['datetime'].max()})")
        return True

    def run(self):
        if self.df is None or len(self.df) < 200:
            print("Insufficient data to run backtest")
            return

        print("Starting Backtest Simulation...")
        
        trades = []
        analyzer = Analyzer()
        
        
        # Instantiate dependencies ONCE
        warmup = 200
        mock_scanner = BacktestScanner(self.df, warmup)
        analyzer = Analyzer()
        
        # --- VECTORIZATION OPTIMIZATION ---
        print("Pre-calculating technical indicators...")
        from modules.indicators import analyze_technicals
        
        # Calculate indicators for the ENTIRE dataframe at once
        # We wrap it in a try-except to handle potential errors in bulk calc
        try:
            from modules.indicators import analyze_technicals, calculate_rsi, calculate_bollinger_bands, calculate_atr, calculate_volume_ma, calculate_adx, calculate_bbw
            
            # Create a lookup dictionary for O(1) access
            # We map timestamp -> analysis result dict (subset needed for analyzer)
            indicator_lookup = {}
            
            closes = self.df['close'].values
            volumes = self.df['volume'].values
            
            # --- PRE-CALC VALUES FOR LOOKUP LOOP ---
            rsis = calculate_rsi(self.df).values
            bb_lowers, _, _ = calculate_bollinger_bands(self.df)
            bb_lowers = bb_lowers.values
            atrs = calculate_atr(self.df).values
            vol_mas = calculate_volume_ma(self.df).values
            adxs = calculate_adx(self.df).values
            bbws = calculate_bbw(self.df).values
            
            for i in range(len(self.df)):
                indicator_lookup[i] = {
                    "close": float(closes[i]),
                    "volume": float(volumes[i]),
                    "rsi": float(rsis[i]) if pd.notna(rsis[i]) else None,
                    "bb_lower": float(bb_lowers[i]) if pd.notna(bb_lowers[i]) else None,
                    "atr": float(atrs[i]) if pd.notna(atrs[i]) else None,
                    "volume_ma": float(vol_mas[i]) if pd.notna(vol_mas[i]) else None,
                    "adx": float(adxs[i]) if pd.notna(adxs[i]) else None,
                    "bbw": float(bbws[i]) if pd.notna(bbws[i]) else None, # NEW
                    "rsi_oversold": float(rsis[i]) < 32 if pd.notna(rsis[i]) else False,
                    "below_bb_lower": float(closes[i]) <= float(bb_lowers[i]) if pd.notna(bb_lowers[i]) else False,
                    "volume_spike": float(volumes[i]) > (float(vol_mas[i]) * 1.5) if pd.notna(vol_mas[i]) else False
                }
                
            print("Indicators pre-calculated successfully.")
            
            def optimized_analyze_technicals(df_slice):
                # Just return the looked-up value for the last timestamp
                last_ts = df_slice.index[-1]
                return indicator_lookup.get(last_ts, {})
                
        except Exception as e:
            print(f"Vectorization failed: {e}. Falling back to slow loop.")
            optimized_analyze_technicals = analyze_technicals
        # Apply patches globally for the loop
        with patch('modules.analyzer.get_scanner', return_value=mock_scanner), \
             patch('modules.capital_manager.get_capital_manager') as mock_cm, \
             patch.object(analyzer, 'check_trade_frequency_limits', return_value=True), \
             patch('builtins.print'), \
             patch('modules.analyzer.analyze_technicals', side_effect=optimized_analyze_technicals):
             
            # Configure CM mock
            mock_cm_instance = mock_cm.return_value
            mock_cm_instance.get_kill_switch_status.return_value = (False, 0)
            
            # Inject scanner into analyzer provided by get_analyzer if needed, 
            # OR just set it since we instantiated analyzer directly
            analyzer.scanner = mock_scanner
            
            # Simulation Loop
            for i in range(warmup, len(self.df)):
                self.current_idx = i
                current_time = self.df.iloc[i]['datetime']
                current_row = self.df.iloc[i]
                
                # UPDATE MOCK SCANNER TIME
                mock_scanner.current_idx = i
                
                # UPDATE MOCK SCANNER TIME
                mock_scanner.current_idx = i
                
                # --- GLOBAL SAFETY CHECKS (KILL SWITCH & CIRCUIT BREAKER) ---
                from config.settings import BTC_CRASH_THRESHOLD, MAX_CONSECUTIVE_LOSSES
                
                # 1. Kill Switch (BTC Crash)
                # Check 1h change
                btc_change_1h = mock_scanner.get_btc_change(60)
                if btc_change_1h < BTC_CRASH_THRESHOLD:
                    # e.g. -3.5% < -3.0%
                     # print(f"SKIPPING: Kill Switch Active at {current_time} (1h Change: {btc_change_1h:.2f}%)")
                     continue

                # 2. Circuit Breaker (Consecutive Losses)
                if len(trades) >= MAX_CONSECUTIVE_LOSSES:
                    # Check last N trades
                    last_n_trades = trades[-MAX_CONSECUTIVE_LOSSES:]
                    # Check if ALL were losses (pnl < 0)
                    consecutive_losses = sum(1 for t in last_n_trades if t['pnl'] < 0)
                    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                        # Check cooldown (e.g. skip for 4 hours? or just next trade?)
                        # For simplicity in backtest: assume we skip 1 candle until condition clears?
                        # But condition clears only with a WIN? No, usually it's a time cooldown.
                        # Implementation in capital_manager is time-based.
                        # Backtest approximation: If last trade exit time was < 4 hours ago.
                        last_trade_exit = last_n_trades[-1]['exit_time']
                        # Calculate hours difference
                        time_diff = (current_time - last_trade_exit).total_seconds() / 3600
                        if time_diff < 4.0: # 4 hour cooldown
                            # print(f"SKIPPING: Circuit Breaker Active at {current_time}")
                            continue
                
                # Print progress every month (using sys.stdout explicitly since print is patched!)
                if i % 1000 == 0:
                    sys.stdout.write(f"\\r   Simulating {current_time.strftime('%Y-%m-%d')}...")
                    sys.stdout.flush()

                # Analyze
                # stdout is suppressed via builtins.print patch
                result = analyzer.analyze(self.symbol)
            


                
                if result.is_buy_signal:
                    # EXPERIMENT: BBW Filter
                    # Filter out horizontal markets (squeeze)
                    from config.settings import MIN_BB_WIDTH, BBW_FILTER_ENABLED
                    
                    is_valid = True
                    if is_valid and BBW_FILTER_ENABLED:
                        # V4.2 Exception: Allow Bull Mode Breakouts even if BBW is low (Squeeze Breakout)
                        if getattr(result, 'bull_mode_active', False):
                             pass # Allow squeeze breakout
                        else:
                             current_bbw = indicator_lookup.get(i, {}).get('bbw')
                             if current_bbw is not None and current_bbw < MIN_BB_WIDTH:
                                 # print(f"Skipping trade at {current_time}: BBW {current_bbw:.4f} < {MIN_BB_WIDTH}")
                                 is_valid = False
                                


                    if is_valid:
                        # Entry Logic
                        entry_price = current_row['close']
                        atr = indicator_lookup.get(i, {}).get('atr', entry_price * 0.02)
                        tp = result.take_profit
                        sl = result.stop_loss
                    
                        # Trade duration simulation
                        # Look forward in DF
                        outcome = "OPEN"
                        pnl = 0.0
                        exit_price = 0.0
                        max_profit = 0.0
                        exit_time = current_time # Default if timeout immediately?
                        
                        # Loop forward candles - THIS IS ALSO SLOW if done purely in python loop
                        # Optimization: Vectorize exit check?
                        # For now, trade frequency is low, so this inner loop is rare.
                        # We leave it as is.
                        
                        for j in range(i + 1, min(i + 500, len(self.df))): # 500 candles max hold
                            future_row = self.df.iloc[j]
                            high = future_row['high']
                            low = future_row['low']
                            close = future_row['close']
                            exit_time = future_row['datetime']
                            
                            # Calc floating profit
                            profit_pct = (high - entry_price) / entry_price
                            max_profit = max(max_profit, profit_pct)
                            
                            # Check SL
                            if low <= sl:
                                outcome = "SL"
                                exit_price = sl
                                pnl = (sl - entry_price) / entry_price
                                break
                                
                            # Check TP
                            if high >= tp:
                                outcome = "TP"
                                exit_price = tp
                                pnl = (tp - entry_price) / entry_price
                                break
                                
                            # Check Trailing Stop (Optimized Single Trail)
                            # Balanced for Volatility: Trigger 2.0%, Callback 1.2%
                            if max_profit > 0.02: # 2% profit to arm
                                trail_price = high * (1 - 0.012) # Trail by 1.2% from peak
                                if low <= trail_price:
                                    outcome = "TRAIL"
                                    exit_price = trail_price
                                    pnl = (exit_price - entry_price) / entry_price
                                    break

                        if outcome == "OPEN":
                            # Force close at end
                            last_idx = min(i + 500, len(self.df)-1)
                            exit_price = self.df.iloc[last_idx]['close']
                            exit_time = self.df.iloc[last_idx]['datetime']
                            pnl = (exit_price - entry_price) / entry_price
                            outcome = "TIMEOUT"
                        
                        trade_res = {
                            'entry_time': current_time,
                            'exit_time': exit_time,
                            'price': entry_price,
                            'exit': exit_price,
                            'outcome': outcome,
                            'pnl': pnl,
                            'month': current_time.strftime('%Y-%m'),
                            'max_pnl': max_profit
                        }
                        trades.append(trade_res)
                        # Use sys.stdout.write for trade log too
                        sys.stdout.write(f"\\n   [TRADE] {current_time} | {outcome} | PnL: {pnl*100:+.2f}%\\n")
                    
        sys.stdout.write("\\n") # Newline after loop

        self.generate_report(trades)

    def generate_report(self, trades):
        if not trades:
            print("No trades generated.")
            return
            
        df_trades = pd.DataFrame(trades)
        
        print("\n" + "="*50)
        print(f"BACKTEST REPORT: {self.symbol}")
        print("="*50)
        
        # Monthly Breakdown
        monthly = df_trades.groupby('month').agg(
            trades=('pnl', 'count'),
            wins=('pnl', lambda x: (x > 0).sum()),
            avg_pnl=('pnl', 'mean'),
            total_pnl=('pnl', 'sum'),
            win_rate=('pnl', lambda x: ((x > 0).sum() / len(x)) * 100)
        )
        
        print("\nMONTHLY PERFORMANCE:")
        print(monthly.to_string())
        
        # Total Stats
        total_pnl = df_trades['pnl'].sum()
        win_rate = (df_trades['pnl'] > 0).mean() * 100
        
        print("\nOVERALL:")
        print(f"Total Trades: {len(df_trades)}")
        print(f"Win Rate:     {win_rate:.2f}%")
        print(f"Total PnL:    {total_pnl*100:+.2f}% (uncompounded)")
        
        # Add Cumulative PnL for plotting
        df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
        
        # Save to CSV for the user
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
            trades_path = os.path.join(self.output_dir, "trades.csv")
            monthly_path = os.path.join(self.output_dir, "monthly.csv")
        else:
            trades_path = "backtest_trades.csv"
            monthly_path = "backtest_monthly.csv"
        df_trades.to_csv(trades_path, index=False)
        monthly.to_csv(monthly_path)
        print(f"\n[SUCCESS] Detailed data saved to '{trades_path}' and '{monthly_path}'")
        print("="*50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='BTC/USDT')
    parser.add_argument('--start', default='2022-02-01')
    parser.add_argument('--end', default=None)
    parser.add_argument('--output-dir', default=None, help='Directory to save results')
    args = parser.parse_args()
    
    engine = BacktestEngine(args.symbol, args.start, args.end, output_dir=args.output_dir)
    if engine.load_data():
        engine.run()
