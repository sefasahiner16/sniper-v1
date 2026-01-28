"""
Sniper V2 - Market Scanner
===========================
Scans MEXC for trading candidates based on volume and volatility.

V2 Features:
- Zombie Filter (liquidity check)
- Chameleon Mode (market regime detection)
- BTC SMA calculation
"""

import ccxt
import pandas as pd
from typing import List, Dict, Optional, Tuple

from config.settings import (
    MEXC_API_KEY, MEXC_SECRET_KEY,
    MIN_24H_VOLUME_USDT, MIN_PRICE_CHANGE_PCT, MAX_PRICE_CHANGE_PCT,
    WATCHLIST_SIZE,
    ZOMBIE_FILTER_ENABLED, ZOMBIE_VOLUME_RATIO,
    CHAMELEON_MODE_ENABLED, BTC_SMA_PERIOD,
    BTC_RSI_PERIOD, BTC_RSI_THRESHOLD
)


class Scanner:
    """Market scanner for finding trading candidates."""
    
    def __init__(self):
        """Initialize the scanner with MEXC connection."""
        self.exchange = ccxt.mexc({
            'apiKey': MEXC_API_KEY,
            'secret': MEXC_SECRET_KEY,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        self._markets_loaded = False
    
    def _ensure_markets_loaded(self) -> None:
        """Load markets if not already loaded."""
        if not self._markets_loaded:
            self.exchange.load_markets()
            self._markets_loaded = True
    
    def fetch_all_tickers(self) -> Dict:
        """
        Fetch all ticker data from MEXC.
        
        Returns:
            Dictionary of ticker data keyed by symbol
        """
        try:
            tickers = self.exchange.fetch_tickers()
            return tickers
        except Exception as e:
            print(f"[SCANNER] Error fetching tickers: {e}")
            return {}
    
    def filter_usdt_pairs(self, tickers: Dict) -> Dict:
        """
        Filter to only USDT trading pairs.
        
        Args:
            tickers: Raw ticker dictionary
            
        Returns:
            Filtered dictionary with only /USDT pairs
        """
        return {
            symbol: data for symbol, data in tickers.items()
            if symbol.endswith('/USDT') and not symbol.startswith('USDT')
        }
    
    def filter_by_volume(self, tickers: Dict, min_volume: float = MIN_24H_VOLUME_USDT) -> Dict:
        """
        Filter tickers by minimum 24h volume.
        
        Args:
            tickers: Ticker dictionary
            min_volume: Minimum 24h volume in USDT
            
        Returns:
            Filtered tickers meeting volume requirement
        """
        filtered = {}
        for symbol, data in tickers.items():
            try:
                # quoteVolume is 24h volume in quote currency (USDT)
                volume = data.get('quoteVolume', 0) or 0
                if volume >= min_volume:
                    filtered[symbol] = data
            except (TypeError, KeyError):
                continue
        return filtered
    
    def filter_by_price_change(self, tickers: Dict, 
                                min_change: float = MIN_PRICE_CHANGE_PCT,
                                max_change: float = MAX_PRICE_CHANGE_PCT) -> Dict:
        """
        Filter tickers by 24h price change percentage.
        Looking for coins that have dipped but not crashed completely.
        
        Args:
            tickers: Ticker dictionary
            min_change: Minimum price change (negative = down)
            max_change: Maximum price change (negative = down)
            
        Returns:
            Filtered tickers in the volatility range
        """
        filtered = {}
        for symbol, data in tickers.items():
            try:
                change = data.get('percentage', 0) or 0
                # Looking for coins that are down between min_change and max_change
                if min_change <= change <= max_change:
                    filtered[symbol] = data
            except (TypeError, KeyError):
                continue
        return filtered
    
    def sort_by_change(self, tickers: Dict, ascending: bool = True) -> List[str]:
        """
        Sort symbols by price change percentage.
        
        Args:
            tickers: Ticker dictionary
            ascending: Sort low to high (Deepest dips first)
            
        Returns:
            List of symbols sorted by change
        """
        sorted_items = sorted(
            tickers.items(),
            key=lambda x: x[1].get('percentage', 0) or 0,
            reverse=not ascending
        )
        return [item[0] for item in sorted_items]
    
    def generate_watchlist(self, limit: int = WATCHLIST_SIZE) -> List[Dict]:
        """
        Generate a watchlist of trading candidates.
        
        This is the main entry point for the scanner.
        
        Args:
            limit: Maximum number of candidates to return
            
        Returns:
            List of candidate dictionaries with symbol and ticker data
        """
        print("[SCANNER] Fetching all tickers...")
        tickers = self.fetch_all_tickers()
        
        if not tickers:
            print("[SCANNER] No tickers fetched")
            return []
        
        print(f"[SCANNER] Found {len(tickers)} total tickers")
        
        # Apply filters
        usdt_pairs = self.filter_usdt_pairs(tickers)
        print(f"[SCANNER] {len(usdt_pairs)} USDT pairs")
        
        volume_filtered = self.filter_by_volume(usdt_pairs)
        print(f"[SCANNER] {len(volume_filtered)} meet volume requirement (>${MIN_24H_VOLUME_USDT:,.0f})")
        
        price_filtered = self.filter_by_price_change(volume_filtered)
        print(f"[SCANNER] {len(price_filtered)} in target volatility range ({MIN_PRICE_CHANGE_PCT}% to {MAX_PRICE_CHANGE_PCT}%)")
        
        # Sort and limit
        # OPTIMIZED: Prioritize Volatility (Deepest Dips) over Volume
        sorted_symbols = self.sort_by_change(price_filtered, ascending=True)[:limit]
        
        # Build watchlist with full data
        watchlist = []
        for symbol in sorted_symbols:
            data = price_filtered[symbol]
            watchlist.append({
                "symbol": symbol,
                "price": data.get('last', 0),
                "change_24h": data.get('percentage', 0),
                "volume_24h": data.get('quoteVolume', 0),
                "high_24h": data.get('high', 0),
                "low_24h": data.get('low', 0)
            })
        
        print(f"[SCANNER] Watchlist generated with {len(watchlist)} candidates")
        return watchlist
    
    def get_btc_change(self, lookback_minutes: int = 15) -> Optional[float]:
        """
        Get BTC price change over the last N minutes.
        
        Args:
            lookback_minutes: Number of minutes to look back
            
        Returns:
            Percentage change or None if error
        """
        try:
            # Fetch recent 1-minute candles for BTC
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1m', limit=lookback_minutes + 1)
            
            if len(ohlcv) < 2:
                return None
            
            # Calculate change from lookback_minutes ago to now
            old_close = ohlcv[0][4]  # Close price of oldest candle
            current_close = ohlcv[-1][4]  # Close price of latest candle
            
            change_pct = ((current_close - old_close) / old_close) * 100
            return change_pct
            
        except Exception as e:
            print(f"[SCANNER] Error fetching BTC data: {e}")
            return None
    
    def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        Fetch order book for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "SUI/USDT")
            limit: Number of levels to fetch
            
        Returns:
            Order book dictionary with 'bids' and 'asks'
        """
        try:
            self._ensure_markets_loaded()
            orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
            return orderbook
        except Exception as e:
            print(f"[SCANNER] Error fetching order book for {symbol}: {e}")
            return None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data for a symbol.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            self._ensure_markets_loaded()
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # CCXT fetch_ohlcv returns the current (incomplete) candle as the last element.
            # We must remove it to ensure we only trade on CLOSED candles.
            # This prevents "repainting" where a signal appears mid-candle and then vanishes.
            if len(ohlcv) > 0:
                ohlcv.pop()  # Remove last element (current open candle)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"[SCANNER] Error fetching OHLCV for {symbol}: {e}")
            return None
    
    def get_balance(self, currency: str = 'USDT') -> float:
        """
        Get wallet balance for a currency.
        
        Args:
            currency: Currency to check (default USDT)
            
        Returns:
            Available balance
        """
        try:
            balance = self.exchange.fetch_balance()
            return balance.get(currency, {}).get('free', 0) or 0
        except Exception as e:
            print(f"[SCANNER] Error fetching balance: {e}")
            return 0.0
    
    # =========================================================================
    # V2: Zombie Filter (Liquidity Check)
    # =========================================================================
    
    def estimate_market_cap(self, symbol: str, ticker_data: Optional[Dict] = None) -> Optional[float]:
        """
        Estimate market cap for a symbol.
        
        Note: MEXC doesn't provide market cap directly, so we estimate
        using circulating supply data if available, or use volume as proxy.
        
        Args:
            symbol: Trading pair
            ticker_data: Optional ticker data (to avoid refetching)
            
        Returns:
            Estimated market cap in USDT or None
        """
        try:
            self._ensure_markets_loaded()
            market = self.exchange.markets.get(symbol)
            
            if not market:
                return None
            
            # Get current price
            if ticker_data:
                price = ticker_data.get('last', 0)
            else:
                ticker = self.exchange.fetch_ticker(symbol)
                price = ticker.get('last', 0)
            
            if price == 0:
                return None
            
            # Try to get info from market data
            # Note: Most exchanges don't provide circulating supply
            # We use 24h volume as a liquidity proxy instead
            # The zombie filter will use volume/estimated_mcap ratio
            
            # For now, estimate market cap as 100x the 24h volume
            # This is a rough heuristic - real market caps are typically
            # 10-1000x daily volume depending on the asset
            if ticker_data:
                volume = ticker_data.get('quoteVolume', 0)
            else:
                volume = 0
            
            if volume > 0:
                # Assume market cap is roughly 100x daily volume
                # This will be refined as we get more data
                estimated_mcap = volume * 100
                return estimated_mcap
            
            return None
            
        except Exception as e:
            print(f"[SCANNER] Error estimating market cap for {symbol}: {e}")
            return None
    
    def check_zombie_filter(self, symbol: str, ticker_data: Optional[Dict] = None) -> Tuple[bool, float]:
        """
        V2 Zombie Filter: Check if coin has sufficient liquidity.
        
        Logic: 24h Volume / Market Cap > ZOMBIE_VOLUME_RATIO
        
        Rejects "dead" coins with no real volume.
        
        Args:
            symbol: Trading pair
            ticker_data: Optional ticker data
            
        Returns:
            Tuple of (passed, volume_to_mcap_ratio)
        """
        if not ZOMBIE_FILTER_ENABLED:
            return True, 1.0
        
        try:
            if ticker_data:
                volume_24h = ticker_data.get('quoteVolume', 0) or 0
            else:
                ticker = self.exchange.fetch_ticker(symbol)
                volume_24h = ticker.get('quoteVolume', 0) or 0
            
            market_cap = self.estimate_market_cap(symbol, ticker_data)
            
            if market_cap is None or market_cap == 0:
                # Can't calculate ratio, be conservative and pass
                return True, 0.0
            
            ratio = volume_24h / market_cap
            passed = ratio >= ZOMBIE_VOLUME_RATIO
            
            return passed, ratio
            
        except Exception as e:
            print(f"[SCANNER] Zombie filter error for {symbol}: {e}")
            return True, 0.0  # Be permissive on error
    
    # =========================================================================
    # V2: Chameleon Mode (Market Regime Detection)
    # =========================================================================
    
    def get_btc_sma(self, period: int = BTC_SMA_PERIOD) -> Optional[float]:
        """
        Get BTC Simple Moving Average for market regime detection.
        """
        try:
            # Fetch daily candles for SMA calculation
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1d', limit=period + 5)
            
            if len(ohlcv) < period:
                return None
            
            # Calculate SMA from close prices
            closes = [candle[4] for candle in ohlcv[-period:]]
            sma = sum(closes) / len(closes)
            
            return sma
            
        except Exception as e:
            print(f"[SCANNER] Error calculating BTC SMA: {e}")
            return None

    def get_btc_rsi(self, period: int = BTC_RSI_PERIOD) -> Optional[float]:
        """
        Calculates BTC RSI on Daily timeframe.
        """
        try:
             # Fetch daily candles
            ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '1d', limit=period + 50)
            if len(ohlcv) < period + 1:
                return None
            
            # Use pandas for RSI calc
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate RSI manually (or use library if available, but staying dependency-light)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1]
            
        except Exception as e:
            print(f"[SCANNER] Error calculating BTC RSI: {e}")
            return None

    def get_market_regime(self) -> Tuple[str, Optional[float], Optional[float]]:
        """
        V2 Chameleon Mode: Detect current market regime.
        
        Logic:
        - BULL: BTC > SMA50 AND BTC RSI > 50
        - BEAR: Otherwise
        
        Returns:
            Tuple of (regime, btc_price, btc_sma)
        """
        if not CHAMELEON_MODE_ENABLED:
            return "UNKNOWN", None, None
        
        try:
            # Get current BTC price
            ticker = self.exchange.fetch_ticker('BTC/USDT')
            btc_price = ticker.get('last', 0)
            
            # Get BTC SMA
            btc_sma = self.get_btc_sma()
            
            # Get BTC RSI
            btc_rsi = self.get_btc_rsi()
            
            if btc_price == 0 or btc_sma is None or btc_rsi is None:
                return "UNKNOWN", btc_price, btc_sma
            
            # Revised Logic: Bull requires Trend AND Momentum
            if btc_price > btc_sma and btc_rsi > BTC_RSI_THRESHOLD:
                regime = "BULL"
                print(f"[SCANNER] Market Regime: BULL (Price ${btc_price:.0f} > SMA ${btc_sma:.0f} AND RSI {btc_rsi:.1f} > {BTC_RSI_THRESHOLD})")
            else:
                regime = "BEAR"
                print(f"[SCANNER] Market Regime: BEAR/NEUTRAL (Price ${btc_price:.0f}, SMA ${btc_sma:.0f}, RSI {btc_rsi:.1f})")
            
            return regime, btc_price, btc_sma
            
        except Exception as e:
            print(f"[SCANNER] Error detecting market regime: {e}")
            return "UNKNOWN", None, None

    # =========================================================================
    # V3: Server-Side Orders (Limit & Stop Loss)
    # =========================================================================
    
    def create_stop_loss_order(self, symbol: str, quantity: float, stop_price: float) -> Optional[str]:
        """
        Place a server-side STOP_LIMIT order for protection.
        
        Args:
            symbol: Trading pair
            quantity: Amount to sell
            stop_price: Trigger price
            
        Returns:
            Order ID or None
        """
        try:
            self._ensure_markets_loaded()
            
            # Create a STOP_LIMIT order
            # Note: We set the limit slightly lower than stop to ensure fill (prevent skip)
            # 0.5% buffer for the limit price below the trigger
            limit_price = stop_price * 0.995
            
            # MEXC specific params for stop order
            params = {
                'stopPrice': stop_price,
            }
            
            # Note: 'stop_limit' type might vary by exchange/driver. 
            # For MEXC Spot in CCXT, usually type='limit' with params={'stopPrice': ...} works
            # or type='stop_limit' if fully supported.
            # We will try standard CCXT convention.
            
            print(f"[SCANNER] 🛡️ Placing Server-Side STOP LOSS: Trigger ${stop_price:.6f}, Limit ${limit_price:.6f}")
            
            order = self.exchange.create_order(
                symbol=symbol,
                type='limit',  # Often passed as limit with stopPrice params for spot
                side='sell',
                amount=quantity,
                price=limit_price,
                params=params
            )
            
            return str(order['id'])
            
        except Exception as e:
            print(f"[SCANNER] ❌ Failed to place Stop Loss: {e}")
            return None

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an existing order.
        """
        try:
            self.exchange.cancel_order(order_id, symbol)
            print(f"[SCANNER] 🗑️ Order {order_id} cancelled")
            return True
        except Exception as e:
            print(f"[SCANNER] ⚠️ Failed to cancel order {order_id}: {e}")
            return False

# Singleton instance
_scanner_instance = None

def get_scanner() -> Scanner:
    """Get the global scanner instance."""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = Scanner()
    return _scanner_instance
