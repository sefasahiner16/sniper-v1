"""
Sniper V3 - Main Entry Point
=============================
Data-driven cryptocurrency trading bot for MEXC.

V3 Features:
- Multi-slot async dispatcher (3 concurrent trades)
- RSI Hook, Zombie Filter, Chameleon Mode
- Dead hours, Ratchet trailing stop
- Multi-timeframe confirmation (coming soon)

Usage:
    python main.py              # Run V3 multi-slot dispatcher
    python main.py --legacy     # Run V1 sync loop
    python main.py --test       # Test API connection
    python main.py --stats      # Show performance stats
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime

from config.settings import (
    SCAN_INTERVAL_SECONDS, PAPER_TRADING,
    MEXC_API_KEY, TELEGRAM_BOT_TOKEN,
    DEAD_HOURS_ENABLED, DEAD_HOURS_START_UTC, DEAD_HOURS_END_UTC
)
from modules.scanner import get_scanner
from modules.analyzer import get_analyzer
from modules.executor import get_executor
from modules.dispatcher import get_dispatcher
from modules.capital_manager import get_capital_manager
from utils.logger import print_performance_summary, get_performance_stats
from utils.notifier import send_message


def test_connection() -> bool:
    """Test API connectivity and configuration."""
    print("\n" + "="*50)
    print("🔌 TESTING CONNECTION (V3)")
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
    
    # V2: Test market regime detection
    regime, btc_price, btc_sma = scanner.get_market_regime()
    if regime != "UNKNOWN":
        print(f"✅ Chameleon Mode: {regime} market (BTC: ${btc_price:,.0f} vs SMA50: ${btc_sma:,.0f})")
    
    # V2: Check dead hours status
    capital_manager = get_capital_manager()
    if DEAD_HOURS_ENABLED:
        is_dead, minutes_until = capital_manager.get_dead_hours_status()
        if is_dead:
            print(f"⚠️ Dead hours active - trading paused for {minutes_until} minutes")
        else:
            print(f"✅ Dead hours: OFF (active {DEAD_HOURS_START_UTC}:00 - {DEAD_HOURS_END_UTC}:00 UTC)")
    
    # Test Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_bot_token_here":
        version = os.getenv("BOT_VERSION", "v3").upper()
        if send_message(f"🔌 Sniper {version} connection test successful!"):
            print("✅ Telegram notifications working")
        else:
            print("⚠️ Telegram configured but could not send message")
    else:
        print("⚠️ Telegram not configured (notifications disabled)")
    
    print("="*50 + "\n")
    return True


def run_v3_dispatcher():
    """Run the V3 async dispatcher."""
    dispatcher = get_dispatcher()
    
    try:
        asyncio.run(dispatcher.run())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        dispatcher.stop()


def run_v1_legacy_loop():
    """Run the V1 synchronous loop (legacy mode)."""
    import time
    
    print("\n" + "="*50)
    print("🚀 SNIPER V2 - LEGACY MODE (V1 LOOP)")
    print("="*50)
    print(f"Mode: {'PAPER TRADING' if PAPER_TRADING else '⚠️ LIVE TRADING'}")
    print(f"Scan Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    print("="*50 + "\n")
    
    scanner = get_scanner()
    analyzer = get_analyzer()
    executor = get_executor()
    capital_manager = get_capital_manager()
    
    executor.startup()
    
    try:
        cycle = 0
        while True:
            cycle += 1
            print(f"\n{'─'*50}")
            print(f"📊 CYCLE #{cycle}")
            print(f"{'─'*50}")
            
            # V2: Check dead hours
            if capital_manager.is_dead_hours():
                is_dead, minutes_until = capital_manager.get_dead_hours_status()
                print(f"🌙 Dead hours active. Sleeping for {minutes_until} minutes...")
                time.sleep(60)  # Check again in 1 minute
                continue
            
            # Check if we can trade
            if not executor.can_trade():
                if executor.current_position:
                    executor.monitor_position()
                time.sleep(30)
                continue
            
            # Generate watchlist
            watchlist = scanner.generate_watchlist()
            
            if not watchlist:
                print("[MAIN] No candidates found this cycle")
            else:
                print(f"[MAIN] Analyzing {len(watchlist)} candidates...")
                
                for candidate in watchlist:
                    symbol = candidate['symbol']
                    result = analyzer.analyze(symbol, ticker_data=candidate)
                    
                    if result.is_buy_signal:
                        print(f"\n🎯 BUY SIGNAL: {symbol}")
                        print(result)
                        
                        if executor.enter_position(result):
                            print(f"[MAIN] Position opened for {symbol}")
                            break
                    else:
                        print(f"[{symbol}] ❌ {result.rejection_reason}")
            
            print(f"\n⏳ Waiting {SCAN_INTERVAL_SECONDS // 60} minutes...")
            
            for _ in range(SCAN_INTERVAL_SECONDS // 10):
                time.sleep(10)
                if executor.current_position:
                    executor.monitor_position()
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        
        if executor.current_position:
            print("Closing open position...")
            executor.exit_position("MANUAL")
        
        print_performance_summary()
        print("Goodbye! 👋")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Sniper V3 Trading Bot")
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--stats', action='store_true', help='Show performance stats')
    parser.add_argument('--scan', action='store_true', help='Run a single scan (no trading)')
    parser.add_argument('--legacy', action='store_true', help='Run V1 sync loop')
    parser.add_argument('--regime', action='store_true', help='Show current market regime')
    parser.add_argument('--version', type=str, choices=['v2', 'v3'], default='v3', help='Run V2 (single slot) or V3 (multi-slot)')
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
        if not test_connection():
            sys.exit(1)
        scanner = get_scanner()
        watchlist = scanner.generate_watchlist()
        print(f"\n📋 WATCHLIST ({len(watchlist)} candidates):")
        print("-" * 60)
        for i, c in enumerate(watchlist, 1):
            print(f"{i:2}. {c['symbol']:12} | ${c['price']:.6f} | {c['change_24h']:+.2f}% | Vol: ${c['volume_24h']:,.0f}")
        sys.exit(0)
    
    elif args.regime:
        scanner = get_scanner()
        regime, btc_price, btc_sma = scanner.get_market_regime()
        print(f"\n🦎 Market Regime: {regime}")
        if btc_price and btc_sma:
            print(f"   BTC Price: ${btc_price:,.2f}")
            print(f"   BTC SMA50: ${btc_sma:,.2f}")
            diff_pct = ((btc_price - btc_sma) / btc_sma) * 100
            print(f"   Difference: {diff_pct:+.2f}%")
        sys.exit(0)
    
    elif args.legacy:
        # V1 legacy mode
        if not test_connection():
            print("\n❌ Connection test failed. Fix issues above and retry.")
            sys.exit(1)
        run_v1_legacy_loop()
    
    else:
        # V2 or V3 based on BOT_VERSION env var (for Railway) or --version flag
        if not test_connection():
            print("\n❌ Connection test failed. Fix issues above and retry.")
            sys.exit(1)
        
        # Priority: Environment variable > Command line argument
        version = os.getenv("BOT_VERSION", args.version).lower()
        
        if version == 'v2':
            # V2: Single-slot mode (uses legacy loop with V2 features)
            print("\n🔄 Running in V2 mode (single-slot)...")
            run_v1_legacy_loop()
        else:
            # V3: Multi-slot mode (default)
            print("\n🚀 Running in V3 mode (multi-slot)...")
            run_v3_dispatcher()


if __name__ == "__main__":
    main()

