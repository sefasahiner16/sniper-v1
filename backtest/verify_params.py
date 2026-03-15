
import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Engine
from backtest.engine import BacktestEngine, BacktestScanner
from unittest.mock import patch, MagicMock

# Define Scenarios
SCENARIOS = {
    "OLD_SETTINGS": {
        "BREAK_EVEN_TRIGGER_PCT": 0.8,
        "BREAK_EVEN_TARGET_PCT": 0.1,
        "QUIET_STOP_LOSS": 1.5,
        "TIME_EXIT_MIN_PROFIT": 1.0,
        "TRAILING_STOP_ACTIVATION": 1.5
    },
    "NEW_SETTINGS": {
        "BREAK_EVEN_TRIGGER_PCT": 1.5,   # Relaxed
        "BREAK_EVEN_TARGET_PCT": 0.2,    # Secure more
        "QUIET_STOP_LOSS": 1.0,          # Tighter
        "TIME_EXIT_MIN_PROFIT": 1.1,     # Higher
        "TRAILING_STOP_ACTIVATION": 1.5  # Same
    }
}

def run_benchmark():
    print("==================================================")
    print("🧪 PARAMETER BENCHMARK: OLD vs NEW")
    print("==================================================")
    
    results = {}
    
    for name, settings in SCENARIOS.items():
        print(f"\n🏃 Running Scenario: {name}")
        print(f"Settings: {settings}")
        
        # Patch settings for this run
        # We need to patch where they are imported/used
        # Analyzer uses them, Executor uses them (but backtest often mocks executor or re-implements logic)
        # engine.py re-implements logic in run() loop!
        # We need to patch the values 'engine.py' uses.
        
        # In engine.py: 
        #   entry_price = current_row['close']
        #   atr = ...
        #   tp = result.take_profit
        #   sl = result.stop_loss
        
        # And importantly, the TRAILING STOP logic in engine.py:
        # if max_profit > 0.02: ...
        
        # Wait, engine.py has HARDCODED trailing logic in the loop:
        # if max_profit > 0.02: # 2% profit to arm
        #    trail_price = high * (1 - 0.012)
        
        # This means engine.py DOES NOT respect config.settings for Trailing Stop!
        # It DOES respect result.stop_loss (which comes from Analyzer -> Scanner -> Strategy Config)
        
        # So to test Stop Loss changes (Quiet Mode), we need to patch Scanner.get_active_strategy 
        # or the config that Analyzer reads.
        
        # Let's patch `modules.scanner.REGIME_CONFIG` inside `backtest.engine` context?
        # Analyzer reads `scanner.get_active_strategy()`.
        # BacktestScanner.get_active_strategy() hardcodes return values!
        
        # We need to subclass/modify BacktestScanner to respect our test settings.
        
        pass

    # Actually, let's just create a modified engine script that allows injecting these params
    # Or cleaner: Modify engine.py to accept strategy overrides?
    
    # For now, let's write a targeted test that manually runs the logic on a sample of data
    # without running the full heavy engine if possible?
    # No, full engine provides realism.
    
    # We will modify BacktestScanner in this script and patch it into engine
    
    pass

# We will implement a custom BacktestScanner that listens to our global current_settings
CURRENT_SETTINGS = {}

class BenchmarkScanner(BacktestScanner):
    def get_active_strategy(self):
        regime, _, _ = self.get_market_regime()
        
        # Default defaults
        sl = 2.0
        if regime == "BULL":
            sl = 2.5
        else:
            # Applies to QUIET/TRANSITIONAL
            # Use our benchmark setting
            sl = CURRENT_SETTINGS.get("QUIET_STOP_LOSS", 2.0)
            
        return {
            'name': regime,
            'rsi_limit': 32 if regime != 'BULL' else 50,
            'stop_loss_pct': sl,
            'volume_spike_mult': 1.5
        }

# We also need to patch the LOOP in engine.py to check our Break Even settings
# Since engine.py hardcodes entry/exit logic in the loop lines 400+, we can't easily patch it without copy-paste.
# We will copy the run() method logic here briefly or straightforwardly use a temporary modified engine file.

# A better approach for this task:
# 1. Read engine.py
# 2. Inject our params
# 3. Save as `engine_benchmark.py`
# 4. Run it

def create_patched_engine(settings_name, settings):
    with open('backtest/engine.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace Hardcoded Trailing Logic in engine.py (lines 427)
    # Original: if max_profit > 0.02:
    # Target: if max_profit > {settings['TRAILING_STOP_ACTIVATION']/100}:
    
    # Replace Break Even Logic (which is missing in original engine.py! Original engine only has Trailing Stop!)
    # We need to ADD Break Even logic to the benchmark engine to test it.
    
    # Logic to insert before "Check Trailing Stop":
    # if max_profit > {settings['BREAK_EVEN_TRIGGER_PCT']/100}:
    #     sl = entry_price * (1 + {settings['BREAK_EVEN_TARGET_PCT']/100})
    
    # Let's construct the new loop block
    be_trigger = settings['BREAK_EVEN_TRIGGER_PCT'] / 100
    be_target = settings['BREAK_EVEN_TARGET_PCT'] / 100
    trail_act = settings['TRAILING_STOP_ACTIVATION'] / 100
    
    # We need to find where to inject.
    # Look for "# Check Trailing Stop"
    
    injection = f"""
                            # BENCHMARK: Break Even Logic
                            if max_profit > {be_trigger}:
                                new_sl = entry_price * (1 + {be_target})
                                if new_sl > sl:
                                    sl = new_sl
    """
    
    content = content.replace("# Check Trailing Stop", injection + "\n                            # Check Trailing Stop")
    
    # Also patch the Trailing Stop activation hardcode
    content = content.replace("if max_profit > 0.02:", f"if max_profit > {trail_act}:")
    
    # Patch Stop Loss in BacktestScanner (lines 165)
    # Original: 'stop_loss_pct': 2.0,
    # New: 'stop_loss_pct': {settings['QUIET_STOP_LOSS']},
    
    content = content.replace("'stop_loss_pct': 2.0,", f"'stop_loss_pct': {settings['QUIET_STOP_LOSS']},")
    
    filename = f"backtest/engine_{settings_name}.py"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filename

if __name__ == "__main__":
    import subprocess
    
    # 1. Generate Patched Engines
    files = []
    for name, settings in SCENARIOS.items():
        fname = create_patched_engine(name, settings)
        files.append((name, fname))
        
    # 2. Run Them
    summary = []
    for name, fname in files:
        print(f"\\n>>> RUNNING {name}...")
        # Run on recent data check (e.g. 2024-01-01 to now)
        try:
            # We assume data exists, if not it will fail gracefully
            cmd = ["python", fname, "--symbol", "BTC/USDT", "--start", "2023-01-01"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse Output for "Total PnL:"
            output = result.stdout
            pnl_line = [l for l in output.split('\\n') if "Total PnL:" in l]
            win_line = [l for l in output.split('\\n') if "Win Rate:" in l]
            
            pnl = pnl_line[0].split(':')[1].strip() if pnl_line else "N/A"
            win = win_line[0].split(':')[1].strip() if win_line else "N/A"
            
            summary.append({"Scenario": name, "PnL": pnl, "WinRate": win})
            # print(output) # debug
            
            # Clean up
            os.remove(fname)
            
        except Exception as e:
            print(f"Failed {name}: {e}")

    # 3. Report
    print("\\n================ RESULT ================")
    summary_df = pd.DataFrame(summary)
    print(summary_df)
