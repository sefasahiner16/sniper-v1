
import requests
import ccxt

def check_exchange(name, url):
    print(f"Testing {name} ({url})...")
    try:
        r = requests.get(url, timeout=5)
        print(f"✅ {name} Status: {r.status_code}")
    except Exception as e:
        print(f"❌ {name} Error: {e}")

check_exchange("MEXC", "https://api.mexc.com/api/v3/ping")
check_exchange("Binance", "https://api.binance.com/api/v3/ping")

print("\nTesting CCXT Load Markets...")
try:
    ex = ccxt.binance()
    ex.load_markets()
    print(f"✅ CCXT Binance Markets: {len(ex.markets)}")
except Exception as e:
    print(f"❌ CCXT Binance Error: {e}")
