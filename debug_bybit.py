import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BYBIT_API_KEY")
secret = os.getenv("BYBIT_SECRET_KEY")

print(f"Key: {api_key[:4]}...{api_key[-4:] if api_key else 'None'}")
print(f"Secret: {secret[:4]}...{secret[-4:] if secret else 'None'}")

bybit = ccxt.bybit({
    'apiKey': api_key,
    'secret': secret,
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
    }
})

print("\nAttempts to fetch balance:")
try:
    balance = bybit.fetch_balance()
    print("SUCCESS")
    print(balance['USDT'])
except Exception as e:
    print("FAILED")
    print(e)
