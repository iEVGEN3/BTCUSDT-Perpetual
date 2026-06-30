import os
import json
import time
from functools import lru_cache
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
from market_data import analyze_market, get_binance_price, get_bybit_price

# IPv4 hack
import socket
import urllib3.util.connection as connection
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

def load_env_file():
    curr = os.path.dirname(os.path.abspath(__file__))
    while True:
        path = os.path.join(curr, '.env')
        if os.path.exists(path):
            load_dotenv(path)
            return True
        parent = os.path.dirname(curr)
        if parent == curr: break
        curr = parent
    load_dotenv()
    return False

load_env_file()

# Кэш для объяснений (чтобы не спамить LLM)
@lru_cache(maxsize=16)
def get_explanation_cached(ticker: str, signal_type: str, rsi: float, macd_str: str, ema50: float):
    # Здесь будет вызов Groq/Gemini
    pass  # реализация ниже

def calculate_atr(prices: list, period: int = 14) -> float:
    """Простой ATR для оценки волатильности."""
    if len(prices) < period + 1:
        return 0.0
    tr = []
    for i in range(1, len(prices)):
        high_low = abs(prices[i] - prices[i-1])  # упрощённо
        tr.append(high_low)
    return sum(tr[-period:]) / period

def generate_signal(ticker: str) -> dict:
    """Улучшенная генерация сигнала с более строгими условиями."""
    data = analyze_market(ticker)
    if not data['success']:
        return {'success': False, 'error': data.get('error', 'Ошибка анализа')}

    price = data['price']
    rsi = data['rsi']
    macd = data['macd']
    ema50 = data['ema50']
    close_prices = data.get('prices_series', [])

    # === СТРОГИЕ УСЛОВИЯ ===
    signal_type = "⏳ ЧЕКАЙ"
    confidence = 40
    metaphor = "Ринок в неопределённости. Ждём ясного сигнала."

    macd_bullish = (macd['macd_prev'] <= macd['signal_prev']) and (macd['macd_curr'] > macd['signal_curr'])
    macd_bearish = (macd['macd_prev'] >= macd['signal_prev']) and (macd['macd_curr'] < macd['signal_curr'])

    atr = calculate_atr(close_prices) if close_prices else 0.0
    price_change = abs(price - ema50) / ema50

    # LONG
    if (price > ema50 and rsi < 58 and rsi > 35 and macd_bullish and 
        price_change > 0.008 and atr > 0.001 * price):
        signal_type = "✅ КУПУЙ"
        confidence = 78
        metaphor = "Сильный бычий импульс: цена выше EMA50, MACD пересёк вверх, RSI в комфортной зоне."

    # SHORT
    elif (price < ema50 and rsi > 42 and rsi < 68 and macd_bearish and 
          price_change > 0.008 and atr > 0.001 * price):
        signal_type = "❌ ПРОДАВАЙ"
        confidence = 78
        metaphor = "Медвежий импульс подтверждён: цена ниже EMA50, MACD пересёк вниз."

    # Ценообразование
    if price < 10:
        price_str = f"{price:.4f}"
        mult = 10000
    else:
        price_str = f"{int(round(price))}"
        mult = 1

    if signal_type == "✅ КУПУЙ":
        stop_loss = round(price * 0.985 / mult) * mult
        target1 = round(price * 1.03 / mult) * mult
        target2 = round(price * 1.06 / mult) * mult
    elif signal_type == "❌ ПРОДАВАЙ":
        stop_loss = round(price * 1.015 / mult) * mult
        target1 = round(price * 0.97 / mult) * mult
        target2 = round(price * 0.94 / mult) * mult
    else:
        stop_loss = round(price * 0.985 / mult) * mult
        target1 = round(price * 1.03 / mult) * mult
        target2 = round(price * 1.06 / mult) * mult

    # AI-объяснение
    explanation = None
    try:
        macd_str = f"MACD={macd['macd_curr']:.4f}, Signal={macd['signal_curr']:.4f}"
        explanation = get_groq_explanation(ticker, price_str, signal_type, rsi, macd, ema50)
        if not explanation:
            explanation = get_gemini_explanation(ticker, price_str, signal_type, rsi, macd, ema50)
    except:
        pass

    if explanation:
        metaphor = explanation.get('metaphor', metaphor)
        one_liner = explanation.get('one_liner', "Управляй рисками.")
        steps = explanation.get('steps', ["Жди", "Анализируй", "Не рискуй"])
    else:
        # Локальные шаблоны
        one_liner = "Контролируй риски 0.5-1% от депозита."
        steps = ["Открыть позицию", "Поставить SL", "Поставить TP"] if "КУПУЙ" in signal_type or "ПРОДАВАЙ" in signal_type else ["Ждать", "Наблюдать", "Не входить"]

    return {
        'success': True,
        'ticker': ticker.upper(),
        'price': price_str,
        'signal': signal_type,
        'confidence': confidence,
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'metaphor': metaphor,
        'one_liner': one_liner,
        'steps': steps,
        'raw_price': price,
        'raw_rsi': rsi
    }

# Оставь функции get_groq_explanation и get_gemini_explanation как были (они хорошие)
# ... (вставь их сюда без изменений)

def check_arbitrage(ticker: str, threshold_pct: float = 0.15) -> dict:
    # Можно оставить как есть или чуть улучшить
    try:
        binance_price = get_binance_price(ticker)
        bybit_price = get_bybit_price(ticker)
        spread_pct = ((bybit_price - binance_price) / binance_price) * 100
        return {
            'success': True,
            'ticker': ticker.upper(),
            'binance_price': binance_price,
            'bybit_price': bybit_price,
            'spread_pct': round(spread_pct, 4),
            'is_opportunity': abs(spread_pct) >= threshold_pct
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
