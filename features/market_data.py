PROXY_BASE = "https://binance-proxy.glove-shramko.workers.dev"
import requests
from tradingview_ta import TA_Handler, Interval
import time
from functools import lru_cache
import socket
import urllib3.util.connection as connection

def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

PROXY_BASE = "https://binance-proxy.glove-shramko.workers.dev"

def get_binance_price(ticker: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    try:
        url = f"{PROXY_BASE}/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return float(res.json()['price'])
    except:
        pass
    raise ValueError(f"Цена Binance не получена для {ticker}")

def get_bybit_price(ticker: str) -> float:
    # Bybit пока без прокси, или добавь позже
    try:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {"symbols": {"tickers": [f"BYBIT:{ticker}USDT"]}, "columns": ["close"]}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get('data'):
            return float(res.json()['data'][0]['d'][0])
    except:
        pass
    raise ValueError(f"Цена Bybit не получена")

def get_live_price(ticker: str) -> float:
    try:
        return get_binance_price(ticker)
    except:
        return get_bybit_price(ticker)

def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    try:
        url = f"{PROXY_BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) >= 20:
                print(f"✅ Клайны через прокси OK")
                return data
    except Exception as e:
        print(f"Прокси клайны ошибка: {e}")
    return []

# Остальные функции (EMA, RSI, MACD, analyze_market) оставь как в предыдущей версии
# ... (вставь их сюда)

def analyze_market(ticker: str, interval: str = '15m') -> dict:
    try:
        price = get_live_price(ticker)
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    try:
        klines = get_klines(ticker, interval, 100)
        close_prices = [float(k[4]) for k in klines] if klines else []
        # ... расчёты rsi, macd, ema50 (как раньше)
        return {
            'success': True,
            'price': price,
            'rsi': calculate_rsi(close_prices) if close_prices else 50,
            'macd': calculate_macd(close_prices) if close_prices else {},
            'ema50': calculate_ema(close_prices) if close_prices else price,
            'prices_series': close_prices
        }
    except:
        return {'success': False, 'error': 'Анализ не удался'}
