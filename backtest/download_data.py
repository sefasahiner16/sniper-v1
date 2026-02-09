import ccxt
import pandas as pd
import os
import time
import argparse
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

def download_data(symbol='BTC/USDT', start_date='2022-02-01', end_date=None, timeframe='15m', exchange_id='mexc'):
    """
    Downloads historical OHLCV data from an exchange in monthly chunks.
    """
    print(f"🚀 Starting download for {symbol} ({timeframe}) from {exchange_id}")
    print(f"📅 Start Date: {start_date}")
    
    # Initialize Exchange
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    # Parse Dates (UTC)
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
    
    # Iterate Month by Month
    while current_dt < end_dt:
        # Define Month Start and End
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
        
        # Fetch Data for this specific month
        monthly_data = []
        since = int(month_start.timestamp() * 1000)
        end_ts = int(month_end.timestamp() * 1000)
        
        while since < end_ts:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if not ohlcv:
                    print("   ⚠️ No data returned")
                    break
                
                monthly_data.extend(ohlcv)
                
                # Update 'since' to the timestamp of the last candle + 1 timeframe
                last_ts = ohlcv[-1][0]
                since = last_ts + 1  # ccxt usually handles the next candle by timestamp
                
                # Safety break if we overshoot
                if last_ts >= end_ts:
                    break
                    
                print(f"   ...fetched {len(ohlcv)} candles (Last: {datetime.fromtimestamp(last_ts/1000, timezone.utc)})")
                time.sleep(exchange.rateLimit / 1000) # Respect rate limit
                
            except Exception as e:
                print(f"❌ Error fetching data: {e}")
                time.sleep(5) # Backoff
                
        # Save to CSV
        if monthly_data:
            df = pd.DataFrame(monthly_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Filter strictly within the month range (to avoid overlaps at edges)
            # Actually, standard is [start, end), so let's keep it simple.
            # But duplicate cleaning is good.
            df = df.drop_duplicates(subset=['timestamp'])
            
            # Filter out any data beyond the month_end (just in case)
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
            
        # Move to next month
        current_dt += relativedelta(months=1)

    print("\n✨ Download Complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sniper Data Downloader')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='Trading Pair')
    parser.add_argument('--start', type=str, default='2022-02-01', help='Start Date YYYY-MM-DD')
    parser.add_argument('--end', type=str, default=None, help='End Date YYYY-MM-DD')
    parser.add_argument('--timeframe', type=str, default='15m', help='Timeframe')
    parser.add_argument('--exchange', type=str, default='mexc', help='Exchange (mexc, binance, etc)')
    
    args = parser.parse_args()
    
    download_data(args.symbol, args.start, args.end, args.timeframe, args.exchange)
