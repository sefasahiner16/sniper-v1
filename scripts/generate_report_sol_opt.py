import pandas as pd
import glob
import os

def generate_report():
    # Base directory for Optimized Results
    base_dir = "backtest_results_SOL_OPT"
    output_file = os.path.join(base_dir, "full_report.md")
    
    print(f"Aggregating results from {base_dir}...")
    
    # 1. Gather all monthly.csv files
    # Only look for part folders that have completed
    files = glob.glob(os.path.join(base_dir, "part*", "monthly.csv"))
    
    if not files:
        print("❌ No monthly results found!")
        return

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not dfs:
        return

    full_df = pd.concat(dfs)
    # Sort by month
    full_df.sort_values('month', inplace=True)
    full_df.reset_index(drop=True, inplace=True)
    
    # Calculate Cumulative PnL
    full_df['cumulative_pnl'] = full_df['total_pnl'].cumsum()
    
    # 2. Comparison Data (Simple hardcoded map for Coin Change to allow side-by-side)
    # Ideally we load this from source, but for report generation we can rely on what we just ran
    # We will just print the bot stats for now.
    
    print("\n--- OPTIMIZED STRATEGY PERFORMANCE (Full 4 Years) ---")
    print(full_df.to_string())
    
    # 3. Overall Stats
    total_trades = full_df['trades'].sum()
    total_wins = full_df['wins'].sum()
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    total_pnl_simple = full_df['total_pnl'].sum()
    
    from datetime import datetime
    months_count = len(full_df)
    
    print("\n--- SUMMARY ---")
    print(f"Total Months: {months_count}")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate:.2f}%")
    print(f"Total PnL:    {total_pnl_simple*100:.2f}% (Simple Sum)")
    
    # Save to CSV for easy viewing
    full_df.to_csv(os.path.join(base_dir, "consolidated_monthly.csv"), index=False)
    print(f"Saved consolidated report to {base_dir}/consolidated_monthly.csv")

if __name__ == "__main__":
    generate_report()
