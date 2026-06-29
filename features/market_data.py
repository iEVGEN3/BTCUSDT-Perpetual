import requests
from tradingview_ta import TA_Handler, Interval

# Принудительное использование IPv4 для обхода проблем с IPv6 на серверах Hugging Face
import socket
import urllib3.util.connection as connection
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

def get_binance_price(ticker: str) -> float:
    """Получает цену Binance через прокси Google Apps Script для обхода геоблока."""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    try:
        url = f"https://script.google.com/macros/s/AKfycbz2D6gLAkk7ZMPaC3BrZat9bNEr23d1S4TsQ69ZDvtozl_qa_Lm1VAPXVGFn60qTwSBEg/exec?binance_symbol={symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return float(response.json()['price'])
    except Exception as e:
        print(f"Исключение при запросе цены Binance через прокси для {symbol}: {e}")
        
    raise ValueError(f"Не удалось получить цену Binance для тикера {symbol}")

def get_bybit_price(ticker: str) -> float:
    """Получает цену Bybit через прокси Google Apps Script для обхода геоблока."""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    try:
        url = f"https://script.google.com/macros/s/AKfycbz2D6gLAkk7ZMPaC3BrZat9bNEr23d1S4TsQ69ZDvtozl_qa_Lm1VAPXVGFn60qTwSBEg/exec?bybit_symbol={symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0 and len(data.get('result', {}).get('list', [])) > 0:
                return float(data['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"Исключение при запросе цены Bybit через прокси для {symbol}: {e}")
        
    raise ValueError(f"Не удалось получить цену Bybit для тикера {symbol}")

def get_live_price(ticker: str) -> float:
    """Возвращает консенсус-цену (среднее арифметическое Binance и Bybit)."""
    prices = []
    
    try:
        prices.append(get_binance_price(ticker))
    except Exception:
        pass
        
    try:
        prices.append(get_bybit_price(ticker))
    except Exception:
        pass
        
    if not prices:
        raise ValueError(f"Не удалось получить цену ни от одного источника для {ticker}")
        
    return sum(prices) / len(prices)

def get_klines(ticker: str, interval: str = '15m', limit: int = 100) -> list:
    """Загружает исторические свечи (по умолчанию 15m) для расчета индикаторов."""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
        
    # 1. Попытка запроса к Futures API
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Исключение при запросе фьючерсных свечей для {symbol}: {e}")
        
    # 2. Попытка запроса к Spot API в качестве резерва
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Исключение при запросе спотовых свечей для {symbol}: {e}")
        
    raise ValueError(f"Не удалось получить исторические свечи для тикера {symbol}")

def calculate_ema_list(prices: list, period: int) -> list:
    """Вычисляет список значений EMA для всего ряда цен."""
    if not prices:
        return []
    alpha = 2.0 / (period + 1.0)
    ema_list = []
    current_ema = prices[0]
    ema_list.append(current_ema)
    for price in prices[1:]:
        current_ema = price * alpha + current_ema * (1.0 - alpha)
        ema_list.append(current_ema)
    return ema_list

def calculate_rsi(prices: list, period: int = 14) -> float:
    """Вычисляет индекс относительной силы (RSI) с использованием сглаживания Уайлдера."""
    if len(prices) < period + 1:
        return 50.0
        
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0.0 else 0.0 for d in deltas]
    losses = [-d if d < 0.0 else 0.0 for d in deltas]
    
    # Первое значение среднего прироста и убытка — простое скользящее среднее
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Сглаживание Wilder's
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
        
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_macd(prices: list) -> dict:
    """Вычисляет MACD линию, сигнальную линию на текущей и предыдущей свечах."""
    if len(prices) < 26:
        return {
            'macd_curr': 0.0, 'signal_curr': 0.0,
            'macd_prev': 0.0, 'signal_prev': 0.0
        }
        
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
    """Вычисляет экспоненциальную скользящую среднюю (EMA) для последней свечи."""
    if not prices:
        return 0.0
    ema_list = calculate_ema_list(prices, period)
    return ema_list[-1]

def get_tradingview_recommendation(ticker: str, interval: str = '15m') -> str:
    """Получает техническую рекомендацию от TradingView."""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
        
    intervals_map = {
        '1m': Interval.INTERVAL_1_MINUTE,
        '5m': Interval.INTERVAL_5_MINUTES,
        '15m': Interval.INTERVAL_15_MINUTES,
        '1h': Interval.INTERVAL_1_HOUR,
        '4h': Interval.INTERVAL_4_HOURS,
        '1d': Interval.INTERVAL_1_DAY
    }
    
    tv_interval = intervals_map.get(interval, Interval.INTERVAL_15_MINUTES)
    
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="crypto",
            exchange="BINANCE",
            interval=tv_interval
        )
        analysis = handler.get_analysis()
        return analysis.summary.get('RECOMMENDATION', 'NEUTRAL')
    except Exception as e:
        print(f"Ошибка при запросе ТА от TradingView для {symbol}: {e}")
        return 'NEUTRAL'

def analyze_market(ticker: str, interval: str = '15m') -> dict:
    """Загружает свечи и возвращает рассчитанные индикаторы вместе с ценами и консенсусом."""
    try:
        binance_p = get_binance_price(ticker)
    except Exception:
        binance_p = None
        
    try:
        bybit_p = get_bybit_price(ticker)
    except Exception:
        bybit_p = None
        
    if binance_p is None and bybit_p is None:
        return {
            'success': False,
            'error': f"Не удалось получить цены с бирж для {ticker}"
        }
        
    # Расчитываем консенсус
    active_prices = [p for p in [binance_p, bybit_p] if p is not None]
    consensus_price = sum(active_prices) / len(active_prices)
    
    try:
        klines = get_klines(ticker, interval=interval, limit=100)
        close_prices = [float(kline[4]) for kline in klines]
        
        rsi_val = calculate_rsi(close_prices, 14)
        macd_data = calculate_macd(close_prices)
        ema50_val = calculate_ema(close_prices, 50)
        
        tv_rec = get_tradingview_recommendation(ticker, interval=interval)
        
        return {
            'success': True,
            'price': consensus_price,
            'binance_price': binance_p if binance_p else consensus_price,
            'bybit_price': bybit_p if bybit_p else consensus_price,
            'rsi': rsi_val,
            'macd': macd_data,
            'ema50': ema50_val,
            'prices_series': close_prices,
            'tradingview_recommendation': tv_rec
        }
    except Exception as e:
        print(f"Ошибка при анализе рынка для {ticker}: {e}")
        return {
            'success': False,
            'error': str(e)
        }
