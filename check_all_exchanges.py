
import requests

exchanges = {
    "Kraken": "https://api.kraken.com/0/public/Time",
    "Coinbase": "https://api.coinbase.com/v2/time",
    "KuCoin": "https://api.kucoin.com/api/v1/timestamp",
    "Bybit": "https://api.bybit.com/v5/market/time",
    "GateIO": "https://api.gateio.ws/api/v4/spot/time",
    "Bitstamp": "https://www.bitstamp.net/api/v2/ticker/btcusd",
    "OKX": "https://www.okx.com/api/v5/public/time"
}

print("Testing alternative exchanges...")
found_working = False

for name, url in exchanges.items():
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            print(f"✅ {name} is ACCESSIBLE!")
            found_working = True
        else:
            print(f"❌ {name} returned status {r.status_code}")
    except Exception as e:
        print(f"❌ {name} failed: Connection Error")

if not found_working:
    print("\n⚠️ ALL tested exchanges are blocked.")
else:
    print("\n✨ At least one exchange is open.")
