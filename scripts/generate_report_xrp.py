import pandas as pd
import os
import glob
from datetime import datetime

# Configuration
RESULTS_DIR = "backtest_results_XRP"
DATA_DIR = "data/historical/XRP_USD"
EVENTS = {
    # 2022
    "2022-02": "Bear Market Begins",
    "2022-05": "LUNA Collapse",
    "2022-06": "Celsius/3AC Crisis",
    "2022-11": "FTX Collapse",
    
    # 2023
    "2023-01": "New Year Rally",
    "2023-06": "Hinman Docs Release",
    "2023-07": "XRP SEC Victory (Summary Judgment)",
    "2023-08": "SEC Appeal Request",
    "2023-10": "SEC Drops Charges vs Execs",
    
    # 2024
    "2024-01": "BTC ETF Approval",
    "2024-04": "BTC Halving",
    "2024-05": "ETH ETF Approval",
    "2024-08": "Global Market Crash",
    
    # 2025
    "2025-01": "Regulatory Clarity?",
    "2025-05": "DeFi 2.0 Boom",
    "2025-11": "Cycle Peak?",
    "2026-01": "Bear Market Onset?"
}

def get_coin_monthly_change(year_month):
    # Format: YYYY_MM
    csv_path = os.path.join(DATA_DIR, f"{year_month.replace('-', '_')}.csv")
    if not os.path.exists(csv_path):
        return 0.0
    
    try:
        # Read only first and last few rows for speed if possible, 
        # but pandas read_csv is easiest.
        df = pd.read_csv(csv_path)
        if df.empty:
            return 0.0
            
        open_price = df.iloc[0]['open']
        close_price = df.iloc[-1]['close']
        
        return ((close_price - open_price) / open_price)
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return 0.0

def main():
    # 1. Aggregate Bot Results
    all_monthly_stats = []
    
    # Order of parts matters? No, we sort by date later.
    part_dirs = sorted(glob.glob(os.path.join(RESULTS_DIR, "part*")))
    
    if not part_dirs:
        print(f"No result directories found in {RESULTS_DIR}")
        return

    for p_dir in part_dirs:
        m_file = os.path.join(p_dir, "monthly.csv")
        if os.path.exists(m_file):
            try:
                df = pd.read_csv(m_file)
                # Ensure month column exists and normalize
                if 'month' in df.columns:
                    for _, row in df.iterrows():
                        all_monthly_stats.append(row.to_dict())
            except Exception as e:
                print(f"Error reading {m_file}: {e}")

    # 2. Build Final Table
    # Sort by month
    all_monthly_stats.sort(key=lambda x: x['month'])
    
    print("| Month | Bot Profit | Coin Change | Trades | Win Rate | Key Event |")
    print("| :--- | :--- | :--- | :---: | :---: | :--- |")
    
    total_bot_pnl = 0
    total_trades = 0
    total_wins = 0
    
    for stat in all_monthly_stats:
        month_str = stat['month'] # YYYY-MM
        
        # Get Coin Change
        coin_pnl = get_coin_monthly_change(month_str)
        
        # Bot Stats
        bot_pnl = stat['total_pnl']
        try:
            trades = int(stat['trades'])
            total_trades += trades
        except:
            trades = 0
        try:
            wins = int(stat['wins'])
            total_wins += wins
        except:
            wins = 0
            
        try:
            win_rate = float(stat['win_rate'])
        except:
            win_rate = 0.0
            
        total_bot_pnl += bot_pnl
            
        event = EVENTS.get(month_str, "-")
        
        # Formatting
        bot_pnl_str = f"**{bot_pnl*100:+.1f}%**"
        coin_pnl_str = f"{coin_pnl*100:+.1f}%"
        win_rate_str = f"{win_rate:.1f}%"
        
        # Highlight Bot Outperformance
        if bot_pnl > coin_pnl and bot_pnl > 0:
            bot_pnl_str = f"🚀 {bot_pnl_str}"
        elif bot_pnl > coin_pnl and bot_pnl <= 0:
             bot_pnl_str = f"🛡️ {bot_pnl_str}"
             
        print(f"| {month_str} | {bot_pnl_str} | {coin_pnl_str} | {trades} | {win_rate_str} | {event} |")

    # Summary
    print("\n--- SUMMARY ---")
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {overall_win_rate:.2f}%")
    print(f"Total PnL:    {total_bot_pnl*100:.2f}% (Simple Sum)")

if __name__ == "__main__":
    main()
