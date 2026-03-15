import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta

SYMBOL = "solusd" # Bitstamp format
PAIR_NAME = "SOL_USD"
DATA_DIR = os.path.join("data", "historical", PAIR_NAME)
START_DATE = "2022-02-01"
END_DATE = "2022-09-01"
STEP = 900 # 15 minutes

def get_bitstamp_ohlc(pair, start_ts, step, limit=1000):
    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/"
    params = {
        "step": step,
        "limit": limit,
        "start": start_ts
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['data']['ohlc']
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return []

def save_to_monthly_csv(df):
    if df.empty:
        return

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df['month'] = df['datetime'].dt.strftime('%Y_%m')
    
    # Group by month
    grouped = df.groupby('month')
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for month, group in grouped:
        filename = f"{month}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        
        # timestamp in ms for compatibility with engine.py
        # Bitstamp gives seconds strings. Engine expects ms int or float?
        # Let's check existing files. Engine says: 
        # df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        # So we need MS timestamps.
        
        group = group.copy()
        group['timestamp'] = group['timestamp'].astype(int) * 1000
        
        # Columns: timestamp,open,high,low,close,volume,datetime
        output_df = group[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'datetime']]
        output_df.to_csv(filepath, index=False)
        print(f"Saved {filepath} with {len(output_df)} rows")

def main():
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    current_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    
    all_data = []
    
    print(f"Downloading {SYMBOL} from {START_DATE} to {END_DATE}...")
    
    while current_ts < end_ts:
        print(f"Fetching from {datetime.fromtimestamp(current_ts)}...")
        data = get_bitstamp_ohlc(SYMBOL, current_ts, STEP)
        
        if not data:
            print("No data returned. Moving forward...")
            current_ts += STEP * 1000
            continue
            
        # Parse data
        # Bitstamp: {'high': '...', 'timestamp': '...', 'volume': '...', 'low': '...', 'close': '...', 'open': '...'}
        batch_df = pd.DataFrame(data)
        batch_df = batch_df.astype({'high': float, 'low': float, 'open': float, 'close': float, 'volume': float, 'timestamp': int})
        
        all_data.append(batch_df)
        
        # Update current_ts
        last_ts = int(data[-1]['timestamp'])
        current_ts = last_ts + STEP
        
        # Avoid rate limits
        time.sleep(0.5)
        
    if all_data:
        full_df = pd.concat(all_data)
        full_df.drop_duplicates(subset=['timestamp'], inplace=True)
        full_df.sort_values('timestamp', inplace=True)
        
        save_to_monthly_csv(full_df)
        print("Download Complete.")
    else:
        print("No data downloaded.")

if __name__ == "__main__":
    main()
