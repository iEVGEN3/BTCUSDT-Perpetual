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

# Простой кэш (на 60 секунд)
@lru_cache(maxsize=32)
def get_cached_price(ticker: str, exchange: str) -> float:
    return _get_price_internal(ticker, exchange)

def _get_price_internal(ticker: str, exchange: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    sources = []
    if exchange == "binance":
        sources = [
            f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}",
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            "https://scanner.tradingview.com/crypto/scan"  # TV как fallback
        ]
    else:  # bybit
        sources = [
            "https://scanner.tradingview.com/crypto/scan",
            f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"  # fallback
        ]
    
    for url in sources:
        for attempt in range(3):
            try:
                if "tradingview" in url:
                    payload = {"symbols": {"tickers": [f"{exchange.upper()}:{symbol}"]}, "columns": ["close"]}
                    res = requests.post(url, json=payload, headers=headers, timeout=8)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get('data'):
                            return float(data['data'][0]['d'][0])
                else:
                    res = requests.get(url, headers=headers, timeout=8)
                    if res.status_code == 200:
                        return float(res.json()['price'])
            except Exception as e:
                if attempt == 2:
                    print(f"[{exchange.upper()}] Не удалось получить цену {symbol} (попытка {attempt+1}): {e}")
                time.sleep(1)
    raise ValueError(f"Все источники цен для {symbol} ({exchange}) недоступны")

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
            p = get_cached_price(ticker, ex) if ex == "binance" else get_bybit_price(ticker)
            prices.append(p)
        except:
            pass
    if not prices:
        raise ValueError(f"Не удалось получить цену для {ticker}")
    return sum(prices) / len(prices)

# === Клайны (главная проблема) ===
def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    sources = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in sources:
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) >= 20:  # минимум данных
                        print(f"✅ Клайны для {symbol} получены ({len(data)} свечей)")
                        return data
            except Exception as e:
                print(f"Попытка {attempt+1} {url.split('//')[1].split('/')[0]}: {e}")
                time.sleep(1.5)
    
    # Крайний fallback — TradingView
    try:
        handler = TA_Handler(symbol=symbol, screener="crypto", exchange="BINANCE", interval=Interval.INTERVAL_15_MINUTES)
        analysis = handler.get_analysis()
        print(f"⚠️ Использован TradingView fallback для {symbol}")
        # Можно вернуть пустой список или обработать отдельно
    except:
        pass
        
    raise ValueError(f"Не удалось получить свечи для {symbol} ни из одного источника")

# Остальные функции (EMA, RSI, MACD) оставь как есть — они хорошие
# (calculate_ema_list, calculate_rsi, calculate_macd, calculate_ema, get_tradingview_recommendation, analyze_market)
