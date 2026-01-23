"""
Sniper V1 - Main Entry Point
=============================
Data-driven cryptocurrency trading bot for MEXC.

Usage:
    python main.py              # Run the bot
    python main.py --test       # Test API connection
    python main.py --stats      # Show performance stats
"""

import sys
import time
import argparse
from datetime import datetime

from config.settings import (
    SCAN_INTERVAL_SECONDS, PAPER_TRADING,
    MEXC_API_KEY, TELEGRAM_BOT_TOKEN
)
from modules.scanner import get_scanner, Scanner
from modules.analyzer import get_analyzer, Analyzer
from modules.executor import get_executor, Executor, State
from utils.logger import print_performance_summary, get_performance_stats
from utils.notifier import send_message


def test_connection() -> bool:
    """Test API connectivity and configuration."""
    print("\n" + "="*50)
    print("🔌 TESTING CONNECTION")
    print("="*50)
    
    # Check API keys
    if not MEXC_API_KEY or MEXC_API_KEY == "your_api_key_here":
        print("❌ MEXC API key not configured")
        print("   Edit .env file with your API credentials")
        return False
    print("✅ MEXC API key configured")
    
    # Test exchange connection
    scanner = get_scanner()
    try:
        balance = scanner.get_balance('USDT')
        print(f"✅ Connected to MEXC | USDT Balance: ${balance:.4f}")
    except Exception as e:
        print(f"❌ MEXC connection failed: {e}")
        return False
    
    # Test BTC data fetch
    btc_change = scanner.get_btc_change()
    if btc_change is not None:
        print(f"✅ Market data accessible | BTC 15m change: {btc_change:+.2f}%")
    else:
        print("⚠️ Could not fetch BTC data (non-critical)")
    
    # Test Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_bot_token_here":
        if send_message("🔌 Sniper V1 connection test successful!"):
            print("✅ Telegram notifications working")
        else:
            print("⚠️ Telegram configured but could not send message")
    else:
        print("⚠️ Telegram not configured (notifications disabled)")
    
    print("="*50 + "\n")
    return True


def run_single_scan(scanner: Scanner, analyzer: Analyzer, executor: Executor) -> None:
    """Run a single scan cycle."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting scan cycle...")
    
    # Check if we can trade
    if not executor.can_trade():
        # Monitor existing position if any
        if executor.current_position:
            executor.monitor_position()
        return
    
    # Generate watchlist
    watchlist = scanner.generate_watchlist()
    
    if not watchlist:
        print("[MAIN] No candidates found this cycle")
        return
    
    print(f"[MAIN] Analyzing {len(watchlist)} candidates...")
    
    # Analyze each candidate
    for candidate in watchlist:
        symbol = candidate['symbol']
        
        # Run 5-layer analysis
        result = analyzer.analyze(symbol)
        
        if result.is_buy_signal:
            # Found a trade!
            print(f"\n🎯 BUY SIGNAL: {symbol}")
            print(result)
            
            # Enter position
            if executor.enter_position(result):
                print(f"[MAIN] Position opened for {symbol}")
                break  # Only one position at a time
        else:
            # Print rejection summary (compact)
            print(f"[{symbol}] ❌ {result.rejection_reason}")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scan cycle complete")


def main_loop() -> None:
    """Main trading loop."""
    print("\n" + "="*50)
    print("🚀 SNIPER V1 - STARTING MAIN LOOP")
    print("="*50)
    print(f"Mode: {'PAPER TRADING' if PAPER_TRADING else '⚠️ LIVE TRADING'}")
    print(f"Scan Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    print("="*50 + "\n")
    
    # Initialize modules
    scanner = get_scanner()
    analyzer = get_analyzer()
    executor = get_executor()
    
    # Run startup sequence
    executor.startup()
    
    try:
        cycle = 0
        while True:
            cycle += 1
            print(f"\n{'─'*50}")
            print(f"📊 CYCLE #{cycle}")
            print(f"{'─'*50}")
            
            # Run scan
            run_single_scan(scanner, analyzer, executor)
            
            # Monitor position if active
            if executor.current_position:
                time.sleep(30)  # Quick checks while in position
                executor.monitor_position()
            
            # Wait for next cycle
            print(f"\n⏳ Waiting {SCAN_INTERVAL_SECONDS // 60} minutes until next scan...")
            
            # Sleep in chunks to allow keyboard interrupt
            for _ in range(SCAN_INTERVAL_SECONDS // 10):
                time.sleep(10)
                
                # If in position, monitor more frequently
                if executor.current_position:
                    executor.monitor_position()
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        
        # Close any open position
        if executor.current_position:
            print("Closing open position...")
            executor.exit_position("MANUAL")
        
        # Print final stats
        print_performance_summary()
        print("Goodbye! 👋")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Sniper V1 Trading Bot")
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--stats', action='store_true', help='Show performance stats')
    parser.add_argument('--scan', action='store_true', help='Run a single scan (no trading)')
    args = parser.parse_args()
    
    if args.test:
        success = test_connection()
        sys.exit(0 if success else 1)
    
    elif args.stats:
        print_performance_summary()
        stats = get_performance_stats()
        if stats['total_trades'] > 0:
            print(f"Consecutive Losses: {stats['consecutive_losses']}")
        sys.exit(0)
    
    elif args.scan:
        # Single scan without trading
        if not test_connection():
            sys.exit(1)
        scanner = get_scanner()
        watchlist = scanner.generate_watchlist()
        print(f"\n📋 WATCHLIST ({len(watchlist)} candidates):")
        print("-" * 60)
        for i, c in enumerate(watchlist, 1):
            print(f"{i:2}. {c['symbol']:12} | ${c['price']:.6f} | {c['change_24h']:+.2f}% | Vol: ${c['volume_24h']:,.0f}")
        sys.exit(0)
    
    else:
        # Run main loop
        if not test_connection():
            print("\n❌ Connection test failed. Fix issues above and retry.")
            sys.exit(1)
        main_loop()


if __name__ == "__main__":
    main()
