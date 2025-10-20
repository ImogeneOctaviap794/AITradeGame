"""
Market data module - Binance API integration with advanced technical indicators
"""
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
from typing import Dict, List
import pandas as pd
import numpy as np
import warnings

# 忽略SSL警告
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

class MarketDataFetcher:
    """Fetch real-time market data from Binance API with advanced technical indicators"""
    
    def __init__(self):
        self.binance_base_url = "https://api.binance.com/api/v3"
        self.binance_futures_url = "https://fapi.binance.com/fapi/v1"
        
        # Binance symbol mapping
        self.binance_symbols = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'BNB': 'BNBUSDT',
            'XRP': 'XRPUSDT',
            'DOGE': 'DOGEUSDT'
        }
        
        self._cache = {}
        self._cache_time = {}
        self._cache_duration = 5  # Cache for 5 seconds
    
        # 创建一个可复用的session，配置重试策略
        self.session = self._create_session()
    
    def _create_session(self):
        """创建配置好的requests session，解决SSL问题"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 最多重试3次
            backoff_factor=1,  # 重试间隔: 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置请求头，模拟浏览器
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # SSL验证设置（如果遇到SSL问题，可以禁用验证）
        # 注意：生产环境不建议禁用SSL验证
        session.verify = True  # 先尝试正常验证
        
        return session
    
    def _make_request(self, url, params=None, timeout=10, use_futures=False):
        """统一的请求方法，处理SSL和重试"""
        max_attempts = 2
        
        for attempt in range(max_attempts):
            try:
                # 第一次尝试正常SSL验证，第二次尝试禁用验证
                verify_ssl = (attempt == 0)
                
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=timeout, 
                    verify=verify_ssl
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.SSLError as e:
                if attempt == 0:
                    # 第一次失败，下次循环会禁用SSL验证重试
                    continue
                else:
                    # 两次都失败，放弃
                    raise
                    
            except requests.exceptions.Timeout:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                else:
                    raise
                    
            except Exception as e:
                # 其他错误，不重试
                raise
        
        # 不应该到达这里
        raise Exception("Request failed after all attempts")
    
    def get_current_prices(self, coins: List[str]) -> Dict[str, Dict]:
        """Get current prices from Binance API"""
        # Check cache
        cache_key = 'prices_' + '_'.join(sorted(coins))
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self._cache_duration:
                return self._cache[cache_key]
        
        prices = {}
        
        try:
            # Batch fetch Binance 24h ticker data
            symbols = [self.binance_symbols.get(coin) for coin in coins if coin in self.binance_symbols]
            
            if symbols:
                symbols_param = '[' + ','.join([f'"{s}"' for s in symbols]) + ']'
                
                data = self._make_request(
                    f"{self.binance_base_url}/ticker/24hr",
                    params={'symbols': symbols_param},
                    timeout=10
                )
                
                # Parse data
                for item in data:
                    symbol = item['symbol']
                    for coin, binance_symbol in self.binance_symbols.items():
                        if binance_symbol == symbol:
                            prices[coin] = {
                                'price': float(item['lastPrice']),
                                'change_24h': float(item['priceChangePercent']),
                                'volume_24h': float(item['volume']),
                                'quote_volume_24h': float(item['quoteVolume'])
                            }
                            break
            
            # Update cache
            self._cache[cache_key] = prices
            self._cache_time[cache_key] = time.time()
            
            return prices
            
        except Exception as e:
            print(f"[ERROR] Binance API failed: {e}")
            return {coin: {'price': 0, 'change_24h': 0, 'volume_24h': 0, 'quote_volume_24h': 0} for coin in coins}
    
    def get_klines(self, coin: str, interval: str = '3m', limit: int = 100) -> List[Dict]:
        """
        Get K-line/candlestick data from Binance
        
        Args:
            coin: Coin symbol (BTC, ETH, etc.)
            interval: Kline interval (1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d)
            limit: Number of klines (max 1000)
        
        Returns:
            List of kline data
        """
        symbol = self.binance_symbols.get(coin)
        if not symbol:
            return []
        
        try:
            data = self._make_request(
                f"{self.binance_base_url}/klines",
                params={
                    'symbol': symbol,
                    'interval': interval,
                    'limit': limit
                },
                timeout=15
            )
            
            klines = []
            for k in data:
                klines.append({
                    'timestamp': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': k[6],
                    'quote_volume': float(k[7]),
                    'trades': int(k[8])
                })
            
            return klines
            
        except Exception as e:
            # 静默处理K线获取失败
            return []
    
    def get_open_interest(self, coin: str) -> Dict:
        """Get open interest for futures contract"""
        symbol = self.binance_symbols.get(coin)
        if not symbol:
            return {'open_interest': 0, 'timestamp': 0}
        
        try:
            data = self._make_request(
                f"{self.binance_futures_url}/openInterest",
                params={'symbol': symbol},
                timeout=10,
                use_futures=True
            )
            
            return {
                'open_interest': float(data['openInterest']),
                'timestamp': data['time']
            }
            
        except Exception as e:
            # 静默处理，返回默认值
            return {'open_interest': 0, 'timestamp': 0}
    
    def get_funding_rate(self, coin: str) -> Dict:
        """Get current funding rate for perpetual futures"""
        symbol = self.binance_symbols.get(coin)
        if not symbol:
            return {'funding_rate': 0, 'next_funding_time': 0, 'mark_price': 0}
        
        try:
            data = self._make_request(
                f"{self.binance_futures_url}/premiumIndex",
                params={'symbol': symbol},
                timeout=10,
                use_futures=True
            )
            
            return {
                'funding_rate': float(data['lastFundingRate']),
                'next_funding_time': data['nextFundingTime'],
                'mark_price': float(data['markPrice'])
            }
            
        except Exception as e:
            # 静默处理，返回默认值
            return {'funding_rate': 0, 'next_funding_time': 0, 'mark_price': 0}
    
    def calculate_technical_indicators(self, coin: str) -> Dict:
        """
        Calculate comprehensive technical indicators using recent kline data
        
        Returns indicators including:
        - EMA (12, 20, 26, 50)
        - SMA (7, 14)
        - MACD (12, 26, 9)
        - RSI (7, 14)
        - ATR (14)
        - Price trends
        """
        # Get kline data (3-minute interval, last 100 periods)
        klines_3m = self.get_klines(coin, '3m', 100)
        # Get 4-hour data for longer-term context
        klines_4h = self.get_klines(coin, '4h', 50)
        
        if not klines_3m:
            # Return default values if no data available
            current_price = self.get_current_prices([coin]).get(coin, {}).get('price', 0)
            return {
                'current_price': current_price,
                'ema_12': current_price,
                'ema_20': current_price,
                'ema_26': current_price,
                'ema_50': current_price,
                'sma_7': current_price,
                'sma_14': current_price,
                'macd': 0,
                'macd_signal': 0,
                'macd_histogram': 0,
                'rsi_7': 50,
                'rsi_14': 50,
                'atr_14': 0,
                'recent_prices': [current_price] * 10,
                'volume_avg': 0,
                'price_change_pct': 0
            }
        
        # Convert to DataFrame for easier calculation
        df = pd.DataFrame(klines_3m)
        df_4h = pd.DataFrame(klines_4h) if klines_4h else df
        
        # Calculate EMAs
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # Calculate SMAs
        df['sma_7'] = df['close'].rolling(window=7).mean()
        df['sma_14'] = df['close'].rolling(window=14).mean()
        
        # Calculate MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss
        df['rsi_7'] = 100 - (100 / (1 + rs))
        
        gain_14 = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss_14 = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs_14 = gain_14 / loss_14
        df['rsi_14'] = 100 - (100 / (1 + rs_14))
        
        # Calculate ATR (Average True Range)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr_14'] = df['tr'].rolling(window=14).mean()
        
        # Get latest values
        latest = df.iloc[-1]
        
        # Get recent 10 prices for time series
        recent_prices = df['close'].tail(10).tolist()
        
        # Calculate average volume
        volume_avg = df['volume'].tail(20).mean()
        
        # Calculate price change percentage
        if len(df) > 1:
            price_change_pct = ((latest['close'] - df.iloc[0]['close']) / df.iloc[0]['close']) * 100
        else:
            price_change_pct = 0
        
        # Get 4-hour indicators for longer-term context
        context_4h = {}
        if len(df_4h) >= 50:
            df_4h['ema_20'] = df_4h['close'].ewm(span=20, adjust=False).mean()
            df_4h['ema_50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
            df_4h['atr_14'] = df_4h['tr'].rolling(window=14).mean() if 'tr' in df_4h.columns else 0
            
            delta_4h = df_4h['close'].diff()
            gain_4h = (delta_4h.where(delta_4h > 0, 0)).rolling(window=14).mean()
            loss_4h = (-delta_4h.where(delta_4h < 0, 0)).rolling(window=14).mean()
            rs_4h = gain_4h / loss_4h
            df_4h['rsi_14'] = 100 - (100 / (1 + rs_4h))
            
            latest_4h = df_4h.iloc[-1]
            context_4h = {
                'ema_20_4h': latest_4h.get('ema_20', 0),
                'ema_50_4h': latest_4h.get('ema_50', 0),
                'atr_14_4h': latest_4h.get('atr_14', 0),
                'rsi_14_4h': latest_4h.get('rsi_14', 50),
                'volume_avg_4h': df_4h['volume'].tail(20).mean()
            }
        
        return {
            # Current price
            'current_price': latest['close'],
            
            # EMAs
            'ema_12': latest.get('ema_12', latest['close']),
            'ema_20': latest.get('ema_20', latest['close']),
            'ema_26': latest.get('ema_26', latest['close']),
            'ema_50': latest.get('ema_50', latest['close']),
            
            # SMAs
            'sma_7': latest.get('sma_7', latest['close']),
            'sma_14': latest.get('sma_14', latest['close']),
            
            # MACD
            'macd': latest.get('macd', 0),
            'macd_signal': latest.get('macd_signal', 0),
            'macd_histogram': latest.get('macd_histogram', 0),
            
            # RSI
            'rsi_7': latest.get('rsi_7', 50),
            'rsi_14': latest.get('rsi_14', 50),
            
            # ATR
            'atr_14': latest.get('atr_14', 0),
            
            # Time series
            'recent_prices': recent_prices,
            
            # Volume
            'volume_avg': volume_avg,
            'current_volume': latest['volume'],
            
            # Price change
            'price_change_pct': price_change_pct,
            
            # 4-hour context
            **context_4h
        }
    
    def get_complete_market_data(self, coins: List[str]) -> Dict:
        """
        Get comprehensive market data for all coins including:
        - Current prices
        - Technical indicators (MACD, EMA, RSI, ATR)
        - Open interest
        - Funding rates
        - Recent price history
        """
        market_data = {}
        
        # Get current prices first
        current_prices = self.get_current_prices(coins)
        
        for coin in coins:
            try:
                # Get technical indicators
                indicators = self.calculate_technical_indicators(coin)
                
                # Get open interest and funding rate
                oi_data = self.get_open_interest(coin)
                funding_data = self.get_funding_rate(coin)
                
                # Combine all data
                market_data[coin] = {
                    **current_prices.get(coin, {}),
                    'indicators': indicators,
                    'open_interest': oi_data['open_interest'],
                    'funding_rate': funding_data['funding_rate'],
                    'mark_price': funding_data['mark_price']
                }
                
            except Exception as e:
                print(f"[ERROR] Failed to get complete data for {coin}: {e}")
                market_data[coin] = {
                    'price': 0,
                    'change_24h': 0,
                    'indicators': {}
                }
        
        return market_data
