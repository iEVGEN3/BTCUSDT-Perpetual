import requests
from tradingview_ta import TA_Handler, Interval
import time
from functools import lru_cache
import socket
import urllib3.util.connection as connection

# IPv4 hack
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

PROXY_BASE = "https://binance-proxy.glove-shramko.workers.dev"

def get_binance_price(ticker: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    # 1. Direct Binance spot
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return float(res.json()['price'])
    except Exception as e:
        print(f"Direct Binance price error: {e}")
        
    # 2. Proxy Binance spot
    try:
        url = f"{PROXY_BASE}/api/v3/ticker/price?symbol={symbol}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return float(res.json()['price'])
    except Exception as e:
        print(f"Proxy Binance price error: {e}")
    raise ValueError(f"Не удалось получить цену Binance для {ticker}")

def get_bybit_price(ticker: str) -> float:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    # 1. Direct Bybit
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                return float(data['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"Direct Bybit price error: {e}")
        
    # 2. Proxy Bybit
    try:
        url = f"{PROXY_BASE}/bybit/v5/market/tickers?category=linear&symbol={symbol}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                return float(data['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"Proxy Bybit price error: {e}")

    # 3. Fallback to TradingView
    try:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {"symbols": {"tickers": [f"BYBIT:{symbol}"]}, "columns": ["close"]}
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200 and res.json().get('data'):
            return float(res.json()['data'][0]['d'][0])
    except:
        pass
    raise ValueError(f"Не удалось получить цену Bybit для {ticker}")

def get_live_price(ticker: str) -> float:
    prices = []
    try:
        prices.append(get_binance_price(ticker))
    except Exception as e:
        print(f"Ошибка получения цены Binance: {e}")
    try:
        prices.append(get_bybit_price(ticker))
    except Exception as e:
        print(f"Ошибка получения цены Bybit: {e}")
        
    if not prices:
        raise ValueError(f"Не удалось получить цену ни от одного источника для {ticker}")
    return sum(prices) / len(prices)

def map_interval_to_bybit(interval: str) -> str:
    mapping = {
        '1m': '1',
        '3m': '3',
        '5m': '5',
        '15m': '15',
        '30m': '30',
        '1h': '60',
        '2h': '120',
        '4h': '240',
        '6h': '360',
        '12h': '720',
        '1d': 'D',
        '1w': 'W',
    }
    return mapping.get(interval, '15')

def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
        
    # Source 1: Direct Binance Futures API
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) >= 20:
                print(f"✅ Клайны через Direct Binance OK для {symbol}")
                return data
    except Exception as e:
        print(f"Direct Binance klines error: {e}")
        
    # Source 2: Binance via Proxy
    try:
        url = f"{PROXY_BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) >= 20:
                print(f"✅ Клайны через Proxy Binance OK для {symbol}")
                return data
    except Exception as e:
        print(f"Proxy Binance klines error: {e}")

    # Source 3: Direct Bybit Futures API
    try:
        bybit_interval = map_interval_to_bybit(interval)
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={bybit_interval}&limit={limit}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                raw_list = data['result']['list']
                raw_list.reverse()
                print(f"✅ Клайны через Direct Bybit OK для {symbol}")
                return raw_list
    except Exception as e:
        print(f"Direct Bybit klines error: {e}")

    # Source 4: Bybit via Proxy
    try:
        bybit_interval = map_interval_to_bybit(interval)
        url = f"{PROXY_BASE}/bybit/v5/market/kline?category=linear&symbol={symbol}&interval={bybit_interval}&limit={limit}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                raw_list = data['result']['list']
                raw_list.reverse()
                print(f"✅ Клайны через Proxy Bybit OK для {symbol}")
                return raw_list
    except Exception as e:
        print(f"Proxy Bybit klines error: {e}")

    print(f"❌ Failed to fetch klines for {symbol} from all sources.")
    return []

# === Индикаторы ===
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

def calculate_atr(klines: list, period: int = 14) -> float:
    if len(klines) < period + 1:
        return 0.0
    tr_list = []
    first_k = klines[0]
    tr_list.append(float(first_k[2]) - float(first_k[3]))
    for i in range(1, len(klines)):
        h = float(klines[i][2])
        l = float(klines[i][3])
        prev_c = float(klines[i-1][4])
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)
    atr = sum(tr_list[:period]) / period
    for tr in tr_list[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr

def calculate_adx(klines: list, period: int = 14) -> float:
    if len(klines) < 2 * period + 1:
        return 0.0
    tr_list = []
    pdm_list = []
    mdm_list = []
    for i in range(1, len(klines)):
        h = float(klines[i][2])
        l = float(klines[i][3])
        prev_h = float(klines[i-1][2])
        prev_l = float(klines[i-1][3])
        prev_c = float(klines[i-1][4])
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)
        up_move = h - prev_h
        down_move = prev_l - l
        pdm = up_move if (up_move > down_move and up_move > 0) else 0.0
        pdm_list.append(pdm)
        mdm = down_move if (down_move > up_move and down_move > 0) else 0.0
        mdm_list.append(mdm)
    str_val = sum(tr_list[:period]) / period
    spdm_val = sum(pdm_list[:period]) / period
    smdm_val = sum(mdm_list[:period]) / period
    dx_list = []
    pdi = 100 * (spdm_val / str_val) if str_val != 0 else 0
    mdi = 100 * (smdm_val / str_val) if str_val != 0 else 0
    dx = 100 * (abs(pdi - mdi) / (pdi + mdi)) if (pdi + mdi) != 0 else 0
    dx_list.append(dx)
    for i in range(period, len(tr_list)):
        str_val = (str_val * (period - 1) + tr_list[i]) / period
        spdm_val = (spdm_val * (period - 1) + pdm_list[i]) / period
        smdm_val = (smdm_val * (period - 1) + mdm_list[i]) / period
        pdi = 100 * (spdm_val / str_val) if str_val != 0 else 0
        mdi = 100 * (smdm_val / str_val) if str_val != 0 else 0
        dx = 100 * (abs(pdi - mdi) / (pdi + mdi)) if (pdi + mdi) != 0 else 0
        dx_list.append(dx)
    if len(dx_list) < period:
        return 0.0
    adx = sum(dx_list[:period]) / period
    for dx_val in dx_list[period:]:
        adx = (adx * (period - 1) + dx_val) / period
    return adx

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
        return {'success': False, 'error': str(e)}
    
    try:
        klines = get_klines(ticker, interval, 100)
        close_prices = [float(k[4]) for k in klines] if klines else []
        
        rsi = calculate_rsi(close_prices) if close_prices else 50.0
        macd = calculate_macd(close_prices) if close_prices else {'macd_curr':0,'signal_curr':0,'macd_prev':0,'signal_prev':0}
        ema50 = calculate_ema(close_prices) if close_prices else price
        atr = calculate_atr(klines) if klines else 0.0
        adx = calculate_adx(klines) if klines else 0.0
        
        return {
            'success': True,
            'price': price,
            'rsi': rsi,
            'macd': macd,
            'ema50': ema50,
            'atr': atr,
            'adx': adx,
            'prices_series': close_prices,
            'tradingview_recommendation': get_tradingview_recommendation(ticker)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
