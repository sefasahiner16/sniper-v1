"""
ETH Backtest Runner - Downloads data and runs backtests in 6-month chunks.
Saves results to backtest_results_ETH/ folder mirroring the BTC structure.

Usage:
    python backtest/run_eth_backtest.py
"""
import os
import sys
import shutil
import subprocess
import time

# Run from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(PROJECT_ROOT)

# 8 x 6-month periods from Feb 2022 to Feb 2026
PERIODS = [
    ("part1_feb22_aug22",  "2022-02-01", "2022-08-01"),
    ("part2_aug22_feb23",  "2022-08-01", "2023-02-01"),
    ("part3_feb23_aug23",  "2023-02-01", "2023-08-01"),
    ("part4_aug23_feb24",  "2023-08-01", "2024-02-01"),
    ("part5_feb24_aug24",  "2024-02-01", "2024-08-01"),
    ("part6_aug24_feb25",  "2024-08-01", "2025-02-01"),
    ("part7_feb25_aug25",  "2025-02-01", "2025-08-01"),
    ("part8_aug25_feb26",  "2025-08-01", "2026-02-01"),
]

SYMBOL = "ETH/USDT"
RESULTS_DIR = os.path.join(PROJECT_ROOT, "backtest_results_ETH")
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "historical", "ETH_USDT")
PYTHON = sys.executable  # Use the same python interpreter


def download_period(start_date, end_date):
    """Download ETH data for a specific date range."""
    print(f"\n{'='*60}")
    print(f"📥 DOWNLOADING ETH DATA: {start_date} to {end_date}")
    print(f"{'='*60}")
    
    cmd = [
        PYTHON, "backtest/download_eth.py",
        "--symbol", SYMBOL,
        "--start", start_date,
        "--end", end_date,
        "--exchange", "bybit"
    ]
    
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"⚠️  Download had issues (return code {result.returncode})")
        return False
    return True


def run_backtest(start_date, end_date, output_dir):
    """Run backtest engine for a specific date range."""
    print(f"\n{'='*60}")
    print(f"🔬 RUNNING BACKTEST: {start_date} to {end_date}")
    print(f"📁 Output: {output_dir}")
    print(f"{'='*60}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        PYTHON, "backtest/engine.py",
        "--symbol", SYMBOL,
        "--start", start_date,
        "--end", end_date,
        "--output-dir", output_dir
    ]
    
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"⚠️  Backtest had issues (return code {result.returncode})")
        return False
    return True


def cleanup_data():
    """Remove downloaded ETH data to save disk space between chunks."""
    if os.path.exists(DATA_DIR):
        file_count = len(os.listdir(DATA_DIR))
        shutil.rmtree(DATA_DIR)
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"🧹 Cleaned up {file_count} data files")


def main():
    print("=" * 60)
    print("🚀 ETH BACKTEST RUNNER")
    print(f"   Symbol:  {SYMBOL}")
    print(f"   Periods: {len(PERIODS)} x 6 months")
    print(f"   Output:  {RESULTS_DIR}")
    print("=" * 60)
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    completed = 0
    failed = []
    
    for part_name, start_date, end_date in PERIODS:
        output_dir = os.path.join(RESULTS_DIR, part_name)
        
        # Skip if results already exist
        trades_file = os.path.join(output_dir, "trades.csv")
        if os.path.exists(trades_file):
            print(f"\n⏭️  Skipping {part_name} (results already exist)")
            completed += 1
            continue
        
        print(f"\n\n{'#'*60}")
        print(f"# PERIOD: {part_name}")
        print(f"# {start_date} -> {end_date}")
        print(f"{'#'*60}")
        
        # Step 1: Clean previous data
        # cleanup_data()  # DISABLED: Using placeholder data
        
        # Step 2: Download data for this period
        # Download extra data before start for indicator warmup (50 days ~ 2 months)
        # from datetime import datetime
        # from dateutil.relativedelta import relativedelta
        # warmup_start = datetime.strptime(start_date, "%Y-%m-%d") - relativedelta(months=2)
        # warmup_start_str = warmup_start.strftime("%Y-%m-%d")
        
        # if not download_period(warmup_start_str, end_date):
        #     print(f"❌ Download failed for {part_name}, skipping...")
        #     failed.append(part_name)
        #     continue
        print(f"⏩ Skipping download for {part_name} (Using placeholder data)")
        
        # Step 3: Run backtest
        if not run_backtest(start_date, end_date, output_dir):
            print(f"❌ Backtest failed for {part_name}")
            failed.append(part_name)
            continue
        
        completed += 1
        print(f"\n✅ {part_name} COMPLETE ({completed}/{len(PERIODS)})")
        
        # Brief pause between periods
        time.sleep(2)
    
    # Final cleanup
    cleanup_data()
    
    print(f"\n\n{'='*60}")
    print(f"🏁 ETH BACKTEST RUNNER COMPLETE")
    print(f"   ✅ Completed: {completed}/{len(PERIODS)}")
    if failed:
        print(f"   ❌ Failed:    {', '.join(failed)}")
    print(f"   📁 Results:   {RESULTS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
