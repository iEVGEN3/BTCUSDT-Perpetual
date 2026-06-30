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

def get_groq_explanation(ticker: str, price: str, signal_type: str, rsi: float, macd: dict, ema50: float) -> dict:
    """Запитує у Groq Llama 3 просте пояснення ситуації на ринку для новачків українською мовою."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return None
        
    try:
        client = Groq(api_key=api_key)
        
        system_instruction = (
            "Ти — асистент з ф'ючерсної торгівлі для трейдерів-початківців. Твоя мета — надавати лаконічні, "
            "зрозумілі та прості торгові рекомендації українською мовою. Пояснюй складні технічні терміни простою мовою "
            "або пиши їхній переклад/значення у дужках (наприклад, 'лонг (купівля на зростання)', 'шорт (продаж на падіння)', "
            "'тейк-профіт (фіксація прибутку)', 'стоп-лосс (обмеження збитків)'). Уникай як дитячих метафор "
            "(ніяких ведмедиків, биків, парканів, квітів та казок), так і складного професійного жаргону без пояснень."
        )
        
        trend_description = "вище" if float(price) > ema50 else "нижче"
        
        prompt = (
            f"Актив для аналізу: {ticker}\n"
            f"Поточна ціна: {price}\n"
            f"Рекомендація: {signal_type}\n"
            f"Показники ринку:\n"
            f"- Індекс сили (RSI): {rsi:.2f}\n"
            f"- Напрямок сили (MACD): Поточний MACD={macd['macd_curr']:.4f}, сигнальна лінія={macd['signal_curr']:.4f}\n"
            f"- Загальний тренд (EMA 50): Ціна {trend_description} за середню ковзну EMA 50 ({ema50:.2f})\n\n"
            "Згенеруй пояснення для трейдера-початківця українською мовою. Пиши просто, зрозуміло, по справі, розшифровуючи професійні "
            "терміни. Уникай дитячих метафор, казок та спрощений для дітей, але пиши доступною для новачків мовою. "
            "Відповідь має бути строго в форматі JSON з ключами:\n"
            "1. \"metaphor\": технічне пояснення поточного стану ринку та сигналу простими словами для новачків українською мовою (1-2 речення, з поясненнями термінів у дужках).\n"
            "2. \"one_liner\": коротка практична порада з управління ризиками або угодою одним рядком українською мовою.\n"
            "3. \"steps\": список рівно з 3 простих кроків дій (наприклад: відкрити позицію, встановити стоп-лосс, встановити тейк-профіт), адаптованих для новачка українською мовою (з поясненнями в дужках).\n\n"
            "Поверни тільки валідний JSON, без розмітки markdown на кшталт ```json ... ```."
        )
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500
        )
        
        content = chat_completion.choices[0].message.content.strip()
        result = json.loads(content)
        if "metaphor" in result and "one_liner" in result and "steps" in result and len(result["steps"]) == 3:
            return result
    except Exception as e:
        print(f"Ошибка при вызове Groq API: {e}")
        
    return None

def get_gemini_explanation(ticker: str, price: str, signal_type: str, rsi: float, macd: dict, ema50: float) -> dict:
    """Запитує у Gemini просте пояснення ситуації на ринку українською мовою."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
        
    try:
        genai.configure(api_key=api_key)
        
        model_names = ["gemini-2.5-flash", "gemini-1.5-flash"]
        model = None
        system_instruction = (
            "Ти — асистент з ф'ючерсної торгівлі для трейдерів-початківців. Твоя мета — надавати лаконічні, "
            "зрозумілі та прості торгові рекомендації українською мовою. Пояснюй складні технічні терміни простою мовою "
            "або пиши їхній переклад/значення у дужках (наприклад, 'лонг (купівля на зростання)', 'шорт (продаж на падіння)', "
            "'тейк-профіт (фіксація прибутку)', 'стоп-лосс (обмеження збитків)'). Уникай як дитячих метафор "
            "(ніяких ведмедиків, биків, парканів, квітів та казок), так і складного професійного жаргону без пояснень."
        )
        
        for name in model_names:
            try:
                model = genai.GenerativeModel(
                    model_name=name,
                    system_instruction=system_instruction
                )
                break
            except Exception as e:
                print(f"Не удалось инициализировать модель {name}: {e}")
                continue
                
        if not model:
            return None
            
        trend_description = "вище" if float(price) > ema50 else "нижче"
        
        prompt = (
            f"Актив для аналізу: {ticker}\n"
            f"Поточна ціна: {price}\n"
            f"Рекомендація: {signal_type}\n"
            f"Показники ринку:\n"
            f"- Індекс сили (RSI): {rsi:.2f}\n"
            f"- Напрямок сили (MACD): Поточний MACD={macd['macd_curr']:.4f}, сигнальна лінія={macd['signal_curr']:.4f}\n"
            f"- Загальний тренд (EMA 50): Ціна {trend_description} за середню ковзну EMA 50 ({ema50:.2f})\n\n"
            "Згенеруй пояснення для трейдера-початківця українською мовою. Пиши просто, зрозуміло, по справі, розшифровуючи професійні "
            "терміни. Уникай дитячих метафор, казок та спрощений для дітей, але пиши доступною для новачків мовою. "
            "Відповідь має бути строго в форматі JSON з ключами:\n"
            "1. \"metaphor\": технічне пояснення поточного стану ринку та сигналу простими словами для новачків українською мовою (1-2 речення, з поясненнями термінів у дужках).\n"
            "2. \"one_liner\": коротка практична порада з управління ризиками або угодою одним рядком українською мовою.\n"
            "3. \"steps\": список рівно з 3 простих кроків дій (наприклад: відкрити позицію, встановити стоп-лосс, встановити тейк-профіт), адаптованих для новачка українською мовою (з поясненнями в дужках).\n\n"
            "Відповідь має бути строго в форматі JSON, без зайвого тексту, без символів форматування ```json ... ```."
        )
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text.strip())
        if "metaphor" in result and "one_liner" in result and "steps" in result and len(result["steps"]) == 3:
            return result
    except Exception as e:
        print(f"Ошибка при вызове Gemini API: {e}")
        
    return None

def generate_signal(ticker: str) -> dict:
    """Генерація сигналу на основі консенсусу (співпадіння мінімум 3 параметрів)."""
    data = analyze_market(ticker)
    if not data['success']:
        return {'success': False, 'error': data.get('error', 'Помилка аналізу')}

    price = data['price']
    rsi = data['rsi']
    macd = data['macd']
    ema50 = data['ema50']
    tv_rec = data.get('tradingview_recommendation', 'NEUTRAL')

    # Консенсусна логіка (мінімум 3 індикатори)
    macd_bullish = macd['macd_curr'] > macd['signal_curr']
    rsi_long = 30 < rsi < 58
    tv_long = tv_rec in ['BUY', 'STRONG_BUY']
    trend_long = price > ema50

    long_conditions = [trend_long, macd_bullish, rsi_long, tv_long]
    long_score = sum(1 for c in long_conditions if c)

    macd_bearish = macd['macd_curr'] < macd['signal_curr']
    rsi_short = 42 < rsi < 70
    tv_short = tv_rec in ['SELL', 'STRONG_SELL']
    trend_short = price < ema50

    short_conditions = [trend_short, macd_bearish, rsi_short, tv_short]
    short_score = sum(1 for c in short_conditions if c)

    signal_type = "⏳ ЧЕКАЙ"
    confidence = 40
    metaphor = "Технічні показники нейтральні, виражений трендовий рух відсутній."
    one_liner = "Рекомендується перебувати поза угодами до появи зрозумілих сигналів."
    
    # Визначаємо тип сигналу
    if long_score >= 3:
        signal_type = "✅ КУПУЙ"
        confidence = 85 if long_score == 4 else 70
        metaphor = "Сильний бичачий імпульс: більшість технічних індикаторів (включаючи EMA50, MACD та RSI) вказують на зростання."
        one_liner = "Відкриття угоди на купівлю з обов'язковим обмеженням ризиків."
    elif short_score >= 3:
        signal_type = "❌ ПРОДАВАЙ"
        confidence = 85 if short_score == 4 else 70
        metaphor = "Ведмежий імпульс підтверджено: технічні індикатори сигналізують про спадний рух ціни."
        one_liner = "Відкриття угоди на продаж з обов'язковим обмеженням ризиків."

    # Округлення ціни
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

    if price < 10:
        stop_loss = round(stop_loss, 4)
        target1 = round(target1, 4)
        target2 = round(target2, 4)
    else:
        stop_loss = int(round(stop_loss))
        target1 = int(round(target1))
        target2 = int(round(target2))

    # Локальні кроки українською мовою
    if signal_type == "✅ КУПУЙ":
        steps = [
            "Відкрити довгу позицію - лонг (купівля з розрахунком на зростання ціни) за поточною ціною.",
            f"Встановити захисний стоп-лосс (обмеження збитків) на рівні ${stop_loss}.",
            f"Виставити лімітні ордери тейк-профіт (фіксація прибутку) на рівнях ${target1} та ${target2}."
        ]
    elif signal_type == "❌ ПРОДАВАЙ":
        steps = [
            "Відкрити коротку позицію - шорт (продаж з розрахунком на падіння ціни) за поточною ціною.",
            f"Встановити захисний стоп-лосс (обмеження збитків) на рівні ${stop_loss}.",
            f"Виставити лімітні ордери тейк-профіт (фіксація прибутку) на рівнях ${target1} та ${target2}."
        ]
    else:
        steps = [
            "Утриматися від відкриття угод по активу (залишатися поза ринком).",
            "Спостерігати за поведінкою ціни біля ключових рівнів підтримки та опору.",
            "Очікувати формування підтвердженого сигналу від індикаторів ринку."
        ]

    # AI-пояснення
    explanation = None
    try:
        explanation = get_groq_explanation(ticker.upper(), price_str, signal_type, rsi, macd, ema50)
        if not explanation:
            explanation = get_gemini_explanation(ticker.upper(), price_str, signal_type, rsi, macd, ema50)
    except Exception as e:
        print(f"Ошибка при запросе AI-объяснения: {e}")

    if explanation:
        metaphor = explanation.get('metaphor', metaphor)
        one_liner = explanation.get('one_liner', one_liner)
        steps = explanation.get('steps', steps)

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

def check_arbitrage(ticker: str, threshold_pct: float = 0.15) -> dict:
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
