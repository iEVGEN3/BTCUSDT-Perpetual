import requests

def get_live_price(ticker: str) -> float:
    """Получает текущую фьючерсную (или спотовую в качестве резерва) цену тикера с Binance."""
    symbol = ticker.upper()
    if not symbol.endswith('USDT'):
        symbol = f"{symbol}USDT"
    
    # 1. Попытка запроса к Futures API
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json()['price'])
    except Exception as e:
        print(f"Исключение при запросе фьючерсной цены для {symbol}: {e}")
        
    # 2. Попытка запроса к Spot API в качестве резерва
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json()['price'])
    except Exception as e:
        print(f"Исключение при запросе спотовой цены для {symbol}: {e}")
        
    raise ValueError(f"Не удалось получить цену для тикера {symbol}")

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

def analyze_market(ticker: str, interval: str = '15m') -> dict:
    """Загружает свечи и возвращает рассчитанные индикаторы вместе с текущей ценой."""
    try:
        current_price = get_live_price(ticker)
        klines = get_klines(ticker, interval=interval, limit=100)
        
        # Индекс 4 в свече Binance — это Close Price (Цена закрытия)
        close_prices = [float(kline[4]) for kline in klines]
        
        rsi_val = calculate_rsi(close_prices, 14)
        macd_data = calculate_macd(close_prices)
        ema50_val = calculate_ema(close_prices, 50)
        
        return {
            'success': True,
            'price': current_price,
            'rsi': rsi_val,
            'macd': macd_data,
            'ema50': ema50_val,
            'prices_series': close_prices
        }
    except Exception as e:
        print(f"Ошибка при анализе рынка для {ticker}: {e}")
        return {
            'success': False,
            'error': str(e)
        }
