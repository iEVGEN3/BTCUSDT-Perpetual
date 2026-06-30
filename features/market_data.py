import requests
from tradingview_ta import TA_Handler, Interval
import time
from functools import lru_cache
import socket
import urllib3.util.connection as connection

# IPv4 hack для HF
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

# Кэш цен (60 секунд)
@lru_cache(maxsize=32)
def get_cached_price(ticker: str, exchange: str) -> float:
    return _get_price_internal(ticker, exchange)

def _get_price_internal(ticker: str, exchange: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    if exchange == "binance":
        sources = [
            f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}",   # лучший
            f"https://data.binance.vision/api/v3/ticker/price?symbol={symbol}",
            "https://scanner.tradingview.com/crypto/scan",
        ]
    else:  # bybit
        sources = [
            "https://scanner.tradingview.com/crypto/scan",
            f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}",
        ]
    
    for url in sources:
        for attempt in range(3):
            try:
                if "tradingview" in url:
                    payload = {"symbols": {"tickers": [f"{exchange.upper()}:{symbol}"]}, "columns": ["close"]}
                    res = requests.post(url, json=payload, headers=headers, timeout=10)
                    if res.status_code == 200 and res.json().get('data'):
                        return float(res.json()['data'][0]['d'][0])
                else:
                    res = requests.get(url, headers=headers, timeout=10)
                    if res.status_code == 200:
                        return float(res.json()['price'])
            except Exception as e:
                print(f"[{exchange}] Попытка {attempt+1} не удалась: {e}")
                time.sleep(1)
    raise ValueError(f"Не удалось получить цену {symbol} от {exchange}")

def get_binance_price(ticker: str) -> float:
    return get_cached_price(ticker, "binance")

def get_bybit_price(ticker: str) -> float:
    try:
        return get_cached_price(ticker, "bybit")
    except:
        if ticker.upper() == 'TON':
            return get_binance_price(ticker)
        raise

def get_live_price(ticker: str) -> float:
    prices = []
    try:
        prices.append(get_binance_price(ticker))
    except:
        pass
    try:
        prices.append(get_bybit_price(ticker))
    except:
        pass
    if not prices:
        raise ValueError(f"Не удалось получить цену для {ticker}")
    return sum(prices) / len(prices)

def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    """Улучшенная версия с приоритетом data-api.binance.vision"""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    sources = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://data.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
    ]
    
    for url in sources:
        for attempt in range(4):
            try:
                response = requests.get(url, headers=headers, timeout=12)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) >= 30:
                        print(f"✅ Клайны {symbol} получены ({len(data)} свечей) от {url.split('//')[1].split('/')[0]}")
                        return data
            except Exception as e:
                print(f"Попытка {attempt+1} {url.split('//')[1].split('/')[0]}: {e}")
                time.sleep(1.5)
    
    print(f"❌ Не удалось получить клайны для {symbol}. Возвращаем пустой список.")
    return []  # fallback — бот не упадёт

# === Остальные функции (оставляем как были, они норм) ===
def calculate_ema_list(prices: list, period: int) -> list:
    if not prices:
        return []
    alpha = 2.0 / (period + 1.0)
    ema_list = [prices[0]]
    for price in prices[1:]:
        ema_list.append(price * alpha + ema_list[-1] * (1 - alpha))
    return ema_list

def calculate_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_macd(prices: list) -> dict:
    if len(prices) < 26:
        return {'macd_curr': 0, 'signal_curr': 0, 'macd_prev': 0, 'signal_prev': 0}
    ema12 = calculate_ema_list(prices, 12)
    ema26 = calculate_ema_list(prices, 26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_line = calculate_ema_list(macd_line, 9)
    return {
        'macd_curr': macd_line[-1],
        'signal_curr': signal_line[-1],
        'macd_prev': macd_line[-2],
        'signal_prev': signal_line[-2]
    }

def calculate_ema(prices: list, period: int = 50) -> float:
    if not prices:
        return 0.0
    return calculate_ema_list(prices, period)[-1]

def get_tradingview_recommendation(ticker: str, interval: str = '15m') -> str:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    intervals_map = {'15m': Interval.INTERVAL_15_MINUTES, '1h': Interval.INTERVAL_1_HOUR}
    tv_interval = intervals_map.get(interval, Interval.INTERVAL_15_MINUTES)
    try:
        handler = TA_Handler(symbol=symbol, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
        return analysis.summary.get('RECOMMENDATION', 'NEUTRAL')
    except:
        return 'NEUTRAL'

def analyze_market(ticker: str, interval: str = '15m') -> dict:
    try:
        binance_p = get_binance_price(ticker)
    except:
        binance_p = None
    try:
        bybit_p = get_bybit_price(ticker)
    except:
        bybit_p = None
        
    if binance_p is None and bybit_p is None:
        return {'success': False, 'error': f"Не удалось получить цены для {ticker}"}
    
    consensus_price = sum(p for p in [binance_p, bybit_p] if p is not None) / (1 if binance_p is None or bybit_p is None else 2)
    
    try:
        klines = get_klines(ticker, interval=interval, limit=100)
        if len(klines) < 30:
            raise ValueError("Мало данных")
        close_prices = [float(k[4]) for k in klines]
        
        rsi_val = calculate_rsi(close_prices)
        macd_data = calculate_macd(close_prices)
        ema50_val = calculate_ema(close_prices)
        tv_rec = get_tradingview_recommendation(ticker, interval)
        
        return {
            'success': True,
            'price': consensus_price,
            'binance_price': binance_p or consensus_price,
            'bybit_price': bybit_p or consensus_price,
            'rsi': rsi_val,
            'macd': macd_data,
            'ema50': ema50_val,
            'prices_series': close_prices,
            'tradingview_recommendation': tv_rec
        }
    except Exception as e:
        print(f"Ошибка анализа {ticker}: {e}")
        return {'success': False, 'error': str(e)}
