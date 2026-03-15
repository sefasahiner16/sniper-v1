import ccxt
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BYBIT_API_KEY")
secret = os.getenv("BYBIT_SECRET_KEY")

def try_connect(name, options):
    print(f"\n--- TESTING {name} ---")
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': secret,
        'options': options
    })
    
    if 'test' in name.lower():
        exchange.set_sandbox_mode(True)
    
    try:
        # Try to fetch balance
        balance = exchange.fetch_balance()
        print(f"SUCCESS {name}!")
        return True
    except Exception as e:
        print(f"FAILED {name}")
        # Print error details cleanly
        err_str = str(e)
        if 'json' in err_str:
            print("Error JSON found (partial):")
            print(err_str[:200]) # First 200 chars
        else:
            print(err_str[:200])
        return False

# 1. Mainnet Spot (Standard) - Attempted before
try_connect("MAINNET SPOT", {'defaultType': 'spot', 'adjustForTimeDifference': True})

# 2. Testnet Spot
try_connect("TESTNET SPOT", {'defaultType': 'spot', 'adjustForTimeDifference': True})

# 3. Mainnet Unified
print("\n--- TESTING MAINNET UNIFIED ---")
exchange = ccxt.bybit({
    'apiKey': api_key,
    'secret': secret,
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
})
try:
    # Explicit unified call
    bal = exchange.fetch_balance({'type': 'unified'})
    print("SUCCESS MAINNET UNIFIED")
except Exception as e:
    print(f"FAILED MAINNET UNIFIED: {str(e)[:200]}")
