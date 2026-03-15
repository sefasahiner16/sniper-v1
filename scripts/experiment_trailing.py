import pandas as pd
from datetime import datetime

# Load Part 8 Trades (SOL Bull Run) to analyze missed opportunities
# We need the source data to re-simulate
DATA_FILE = "data/historical/SOL_USD/2026_01.csv" 

def run_experiment():
    try:
        df = pd.read_csv(DATA_FILE)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # Focus on a known rally period: Jan 12-16 2026
    # From trades.csv: 
    # Trade 168: Entry 2026-01-12 22:00 @ 139.398 -> Exit 142.24 (+2.0%)
    # But price went to 147 on Jan 14.
    
    start_idx = df[df['datetime'] >= '2026-01-12 22:00:00+00:00'].index[0]
    
    entry_price = df.iloc[start_idx]['close']
    entry_time = df.iloc[start_idx]['datetime']
    print(f"--- Simulating Trade Entry: {entry_time} @ {entry_price:.2f} ---")
    
    # 3 Scenarios
    scenarios = [
        {"name": "Current", "trigger": 0.02, "callback": 0.005},
        {"name": "Relaxed A", "trigger": 0.03, "callback": 0.015},
        {"name": "Relaxed B", "trigger": 0.05, "callback": 0.02}, # Swing style
        {"name": "Dual Stage", "trigger": 0.02, "callback": 0.01, "trigger2": 0.05, "callback2": 0.02} # Example logic
    ]
    
    for sc in scenarios:
        outcome = "OPEN"
        pnl = 0.0
        max_profit = 0.0
        exit_price = 0.0
        exit_time = None
        
        print(f"\nScenario: {sc['name']}")
        
        for j in range(start_idx + 1, min(start_idx + 500, len(df))):
            row = df.iloc[j]
            high = row['high']
            low = row['low']
            close = row['close']
            
            curr_profit = (high - entry_price) / entry_price
            max_profit = max(max_profit, curr_profit)
            
            # Simple Trailing Logic
            if "trigger2" in sc:
                # Dual Stage
                callback = sc['callback']
                if max_profit >= sc['trigger2']:
                    callback = sc['callback2']
                elif max_profit < sc['trigger']:
                    callback = 999 # Inactive
                
                if callback != 999:
                    trail_price = entry_price * (1 + max_profit - callback)
                    if low <= trail_price:
                        outcome = "TRAIL_EXIT"
                        exit_price = trail_price
                        exit_time = row['datetime']
                        pnl = (exit_price - entry_price) / entry_price
                        break
            else:
                # Single Stage
                if max_profit >= sc['trigger']:
                    trail_price = entry_price * (1 + max_profit - sc['callback'])
                    if low <= trail_price:
                        outcome = "TRAIL_EXIT"
                        exit_price = trail_price
                        exit_time = row['datetime']
                        pnl = (exit_price - entry_price) / entry_price
                        break
                        
        if outcome == "OPEN":
            # Timeout
            pnl = (close - entry_price) / entry_price
            print(f"  Result: HELD until end. PnL: {pnl*100:.2f}% (Max: {max_profit*100:.2f}%)")
        else:
            print(f"  Result: {outcome} at {exit_time} @ {exit_price:.2f}. PnL: {pnl*100:.2f}% (Max: {max_profit*100:.2f}%)")

if __name__ == "__main__":
    run_experiment()
