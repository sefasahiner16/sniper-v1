
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from modules.scanner import get_scanner
    from modules.regime_detector import detect_regime
    
    print("Initializing scanner...")
    scanner = get_scanner()
    
    print("Detecting regime...")
    regime = detect_regime(scanner.exchange)
    
    print(f"\n--- MARKET DIAGNOSTICS ---")
    print(str(regime))
    
    # Check BTC price trend
    btc_change_15m = scanner.get_btc_change(15)
    if btc_change_15m is not None:
        print(f"BTC 15m Change: {btc_change_15m:.2f}%")
    else:
        print("BTC 15m Change: FAILED TO FETCH")
    
    btc_change_1h = scanner.get_btc_change(60)
    if btc_change_1h is not None:
        print(f"BTC 1h Change: {btc_change_1h:.2f}%")
    else:
        print("BTC 1h Change: FAILED TO FETCH")
    
    # Check relevant strategy settings
    strategy = scanner.get_active_strategy()
    if strategy:
        print(f"\nActive Strategy: {strategy.get('name', 'UNKNOWN')}")
        print(f"RSI Limit: {strategy.get('rsi_limit', 'N/A')}")
        print(f"Stop Loss: {strategy.get('min_stop_loss_pct', 'N/A')}%")
    else:
        print("\nActive Strategy: FAILED TO DETERMINE")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
