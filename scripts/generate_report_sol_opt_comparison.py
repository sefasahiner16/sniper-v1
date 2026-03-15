import pandas as pd
import os
import glob
from datetime import datetime

# Configuration
RESULTS_DIR = "backtest_results_SOL_OPT"  # Changed to Optimized Directory
DATA_DIR = "data/historical/SOL_USD"
EVENTS = {
    "2022-02": "Russia-Ukraine Conflict Begins",
    "2022-03": "Fed Starts Rate Hikes",
    "2022-04": "Market Correction",
    "2022-05": "Terra (LUNA) Collapse",
    "2022-06": "Celsius/3AC Liquidation Crisis",
    "2022-07": "Bear Market Relief Rally",
    "2022-08": "Tornado Cash Sanctions",
    "2022-09": "Ethereum Merge (PoS)",
    "2022-10": "Low Volatility Accumulation",
    "2022-11": "FTX Collapse",
    "2022-12": "Peak Fear / Bottoming",
    "2023-01": "New Year Rally",
    "2023-02": "Regulator Crackdown (Kraken)",
    "2023-03": "US Banking Crisis (SVB/USDC)",
    "2023-04": "Shapella Upgrade",
    "2023-05": "Meme Coin Mania (PEPE)",
    "2023-06": "BlackRock ETF Filing",
    "2023-07": "XRP SEC Victory",
    "2023-08": "Flash Crash",
    "2023-09": "FTX Liquidation Fears",
    "2023-10": "Uptober / ETF Hype Begins",
    "2023-11": "Binance Settlement",
    "2023-12": "End of Year Rally",
    "2024-01": "BTC ETF Approval",
    "2024-02": "Pre-Halving Rally",
    "2024-03": "New ATHs",
    "2024-04": "Geopolitical Tensions",
    "2024-05": "ETH ETF Approval",
    "2024-06": "Mt. Gox Distribution Fears",
    "2024-07": "German Govt BTC Sales",
    "2024-08": "Global Market Crash (Carry Trade)",
    "2024-09": "Fed Rate Cut Pivot",
    "2024-10": "Uptober Continuation",
    "2024-11": "US Election Volatility",
    "2024-12": "Santa Rally",
    "2025-01": "Post-Halving Bull Run",
    "2025-02": "Altseason Ignition",
    "2025-03": "Mid-Cycle Correction",
    "2025-04": "Recovery & Expansion",
    "2025-05": "DeFi 2.0 Boom",
    "2025-06": "Institution FOMO",
    "2025-07": "Blow-off Top Phase?",
    "2025-08": "Market Cooling",
    "2025-09": "September Seasonality",
    "2025-10": "Q4 Final Push",
    "2025-11": "Potential Cycle Peak",
    "2025-12": "Profit Taking",
    "2026-01": "Bear Market Onset?",
    "2026-02": "Capitulation?"
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
    
    for stat in all_monthly_stats:
        month_str = stat['month'] # YYYY-MM
        
        # Get Coin Change
        coin_pnl = get_coin_monthly_change(month_str)
        
        # Bot Stats
        bot_pnl = stat['total_pnl']
        try:
            trades = int(stat['trades'])
        except:
            trades = 0
        try:
            win_rate = float(stat['win_rate'])
        except:
            win_rate = 0.0
            
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

if __name__ == "__main__":
    main()
