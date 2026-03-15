import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BYBIT_API_KEY")
secret = os.getenv("BYBIT_SECRET_KEY")

print(f"Key: {api_key}")
print(f"Secret: {secret}")

bybit = ccxt.bybit({
    'apiKey': api_key,
    'secret': secret,
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
    }
})

print("\n--- TEST 1: Public Time ---")
try:
    server_time = bybit.publicGetV5MarketTime()
    print(f"Server Time: {server_time}")
except Exception as e:
    print(f"FAILED Public Time: {e}")

print("\n--- TEST 2: Public Ticker ---")
try:
    ticker = bybit.fetch_ticker('BTC/USDT')
    print(f"BTC Price: {ticker['last']}")
except Exception as e:
    print(f"FAILED Public Ticker: {e}")

print("\n--- TEST 3: Private Balance ---")
try:
    balance = bybit.fetch_balance()
    print("SUCCESS Balance")
except Exception as e:
    print(f"FAILED Balance: {e}")
