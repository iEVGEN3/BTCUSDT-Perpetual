import requests
from tradingview_ta import TA_Handler, Interval
import time
from functools import lru_cache
import socket
import urllib3.util.connection as connection

def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

@lru_cache(maxsize=32)
def get_cached_price(ticker: str, exchange: str) -> float:
    return _get_price_internal(ticker, exchange)

def _get_price_internal(ticker: str, exchange: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    sources = []
    if exchange == "binance":
        sources = [
            f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}",
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            "https://scanner.tradingview.com/crypto/scan",
        ]
    else:
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
            except:
                time.sleep(1)
    raise ValueError(f"Цена {symbol} не получена")

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
    for ex in ["binance", "bybit"]:
        try:
            prices.append(get_binance_price(ticker) if ex == "binance" else get_bybit_price(ticker))
        except:
            pass
    if not prices:
        raise ValueError(f"Нет цены для {ticker}")
    return sum(prices) / len(prices)

def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    sources = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}",
    ]
    
    for url in sources:
        for attempt in range(4):
            try:
                response = requests.get(url, headers=headers, timeout=12)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) >= 20:
                        print(f"✅ Клайны {symbol} OK ({len(data)} свечей)")
                        return data
            except Exception as e:
                print(f"Клайны попытка {attempt+1} failed: {e}")
                time.sleep(1.5)
    
    print(f"⚠️ Нет клайнов для {symbol}, используем TradingView fallback")
    return []

# Индикаторы (без изменений)
def calculate_ema_list(prices: list, period: int) -> list:
    if not prices: return []
    alpha = 2.0 / (period + 1.0)
    ema = [prices[0]]
    for p in prices[1:]:
        ema.append(p * alpha + ema[-1] * (1 - alpha))
    return ema

def calculate_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1: return 50.0
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0: return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1 + avg_gain / avg_loss))

def calculate_macd(prices: list) -> dict:
    if len(prices) < 26:
        return {'macd_curr':0,'signal_curr':0,'macd_prev':0,'signal_prev':0}
    ema12 = calculate_ema_list(prices, 12)
    ema26 = calculate_ema_list(prices, 26)
    macd = [a - b for a,b in zip(ema12, ema26)]
    signal = calculate_ema_list(macd, 9)
    return {'macd_curr':macd[-1],'signal_curr':signal[-1],'macd_prev':macd[-2],'signal_prev':signal[-2]}

def calculate_ema(prices: list, period: int = 50) -> float:
    return calculate_ema_list(prices, period)[-1] if prices else 0.0

def get_tradingview_recommendation(ticker: str, interval: str = '15m') -> str:
    try:
        handler = TA_Handler(symbol=ticker+"USDT", screener="crypto", exchange="BINANCE", interval=Interval.INTERVAL_15_MINUTES)
        return handler.get_analysis().summary.get('RECOMMENDATION', 'NEUTRAL')
    except:
        return 'NEUTRAL'

def analyze_market(ticker: str, interval: str = '15m') -> dict:
    try:
        price = get_live_price(ticker)
    except Exception as e:
        return {'success': False, 'error': f"Цена: {e}"}
    
    try:
        klines = get_klines(ticker, interval, 100)
        close_prices = [float(k[4]) for k in klines] if klines else []
        
        rsi = calculate_rsi(close_prices) if close_prices else 50.0
        macd = calculate_macd(close_prices) if close_prices else {'macd_curr':0,'signal_curr':0,'macd_prev':0,'signal_prev':0}
        ema50 = calculate_ema(close_prices) if close_prices else price
        tv = get_tradingview_recommendation(ticker)
        
        return {
            'success': True,
            'price': price,
            'rsi': rsi,
            'macd': macd,
            'ema50': ema50,
            'prices_series': close_prices,
            'tradingview_recommendation': tv
        }
    except Exception as e:
        print(f"Анализ {ticker} ошибка: {e}")
        return {'success': False, 'error': str(e)}
