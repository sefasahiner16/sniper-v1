"""
Download ETH/USDT historical 15m candle data.
Uses ccxt with SSL verification disabled to work around network SSL issues.
"""
import os

# Must set env var BEFORE importing anything SSL-related
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''

import ssl
# Monkey-patch ssl before anything else uses it
_orig_ctx = ssl._create_default_https_context
ssl._create_default_https_context = ssl._create_unverified_context

import ccxt
import pandas as pd
import time
import urllib3
import argparse
import requests
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_data(symbol='ETH/USDT', start_date='2022-02-01', end_date=None, 
                  timeframe='15m', exchange_id='bybit'):
    print(f"🚀 Starting download for {symbol} ({timeframe}) from {exchange_id}")
    print(f"📅 Start Date: {start_date}")
    
    # Initialize Exchange
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    
    # Monkey-patch the session AFTER construction
    exchange.session = requests.Session()
    exchange.session.verify = False
    exchange.verify = False
    
    # Parse Dates
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_dt = datetime.now(timezone.utc)
        
    print(f"📅 End Date:   {end_dt.strftime('%Y-%m-%d')}")
    
    # Create Output Directory
    symbol_clean = symbol.replace('/', '_')
    output_dir = os.path.join('data', 'historical', symbol_clean)
    os.makedirs(output_dir, exist_ok=True)
    
    current_dt = start_dt
    
    while current_dt < end_dt:
        month_start = current_dt
        month_end = month_start + relativedelta(months=1)
        if month_end > end_dt:
            month_end = end_dt
            
        month_str = month_start.strftime("%Y_%m")
        filename = os.path.join(output_dir, f"{month_str}.csv")
        
        if os.path.exists(filename):
            print(f"⏭️  Skipping {month_str} (File exists)")
            current_dt += relativedelta(months=1)
            continue
            
        print(f"📥 Downloading {month_str}...")
        
        monthly_data = []
        since = int(month_start.timestamp() * 1000)
        end_ts = int(month_end.timestamp() * 1000)
        
        retry_count = 0
        max_retries = 3
        
        while since < end_ts:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if not ohlcv:
                    print("   ⚠️ No data returned")
                    break
                
                monthly_data.extend(ohlcv)
                
                last_ts = ohlcv[-1][0]
                since = last_ts + 1
                retry_count = 0  # Reset on success
                
                if last_ts >= end_ts:
                    break
                    
                print(f"   ...fetched {len(ohlcv)} candles (Last: {datetime.fromtimestamp(last_ts/1000, timezone.utc)})")
                time.sleep(exchange.rateLimit / 1000)
                
            except Exception as e:
                retry_count += 1
                print(f"   ❌ Error (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    print(f"   ⚠️ Skipping rest of {month_str} after {max_retries} failures")
                    break
                time.sleep(5)
                
        # Save to CSV
        if monthly_data:
            df = pd.DataFrame(monthly_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.drop_duplicates(subset=['timestamp'])
            
            mask = (df['timestamp'] >= int(month_start.timestamp() * 1000)) & \
                   (df['timestamp'] < int(month_end.timestamp() * 1000))
            df = df[mask]
            
            if not df.empty:
                df.to_csv(filename, index=False)
                print(f"✅ Saved {len(df)} rows to {filename}")
            else:
                print(f"⚠️ No data found in range for {month_str}")
        else:
            print(f"⚠️ No data fetched for {month_str}")
            
        current_dt += relativedelta(months=1)

    print("\n✨ Download Complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ETH Data Downloader (SSL-disabled)')
    parser.add_argument('--symbol', type=str, default='ETH/USDT', help='Trading Pair')
    parser.add_argument('--start', type=str, default='2022-02-01', help='Start Date')
    parser.add_argument('--end', type=str, default=None, help='End Date')
    parser.add_argument('--exchange', type=str, default='bybit', help='Exchange')
    args = parser.parse_args()
    
    download_data(args.symbol, args.start, args.end, exchange_id=args.exchange)
