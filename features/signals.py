import os
import json
import math
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
from market_data import analyze_market, get_binance_price, get_bybit_price

# Принудительное использование IPv4 для обхода проблем с IPv6 на серверах Hugging Face
import socket
import urllib3.util.connection as connection
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

# Загружаем переменные окружения из .env (поиск .env в текущей папке и всех родительских)
def load_env_file():
    curr = os.path.dirname(os.path.abspath(__file__))
    while True:
        path = os.path.join(curr, '.env')
        if os.path.exists(path):
            load_dotenv(path)
            return True
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    load_dotenv()
    return False

load_env_file()

def get_groq_explanation(ticker: str, price: str, signal_type: str, rsi: float, macd: dict, ema50: float) -> dict:
    """Запрашивает у Groq Llama 3 простое объяснение ситуации на рынке для новичков на украинском языке."""
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
            "терміни. Уникай дитячих метафор, казок та спрощень для дітей, але пиши доступною для новачків мовою. "
            "Відповідь має бути строго в форматі JSON з ключами:\n"
            "1. \"metaphor\": технічне пояснення поточного стану ринку та сигналу простими словами для новачків українською мовою (1-2 речення, з поясненнями термінів у дужках).\n"
            "2. \"one_liner\": коротка практична порада з управління ризиками або угодою одним рядком українською мовою.\n"
            "3. \"steps\": список рівно з 3 простих кроків дій (наприклад: відкрити позицію, встановити стоп-лосс, встановити тейк-профіт), адаптованих для новачка українською мовою (з поясненнями в дужках).\n\n"
            "Поверни тільки валідний JSON, без розмітки markdown на кшталт ```json ... ```."
        )
        
        # Используем мощную модель Llama 3.3 70B
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
    """Запрашивает у Gemini простое объяснение ситуации на рынке на украинском языке в качестве альтернативы."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
        
    try:
        genai.configure(api_key=api_key)
        
        model_names = ["gemini-2.5-flash", "gemini-1.5-flash"]
        model = None
        system_instruction = (
            "Ти — асистент з ф'ючерсної торгівлі для трейдерів-початківців. Твоя мета — надавати лаконічні, "
            "зрозумілі та прості торгові рекомендации українською мовою. Пояснюй складні технічні терміни простою мовою "
            "або пиши їхній переклад/значення у дужках (наприклад, 'лонг (купівля на зростання)', 'шорт (продажа на падіння)', "
            "'тейк-профіт (фіксація прибутку)', 'стоп-лосс (обмеження збитків)'). Уникай як дитячих метафор "
            "(ніяких ведмедиків, биків, парканів, квітів та казок), так и складного професійного жаргону без пояснень."
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
            "термины. Уникай дитячих метафор, казок та спрощень для дітей, але пиши доступною для новачків мовою. "
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
    """Анализирует рынок и генерирует детальный сигнал по шаблону осторожного тренера на украинском языке."""
    data = analyze_market(ticker)
    
    if not data['success']:
        return {
            'success': False,
            'error': data.get('error', 'Невідома помилка аналізу ринку')
        }
        
    price = data['price']
    rsi = data['rsi']
    macd = data['macd']
    ema50 = data['ema50']
    
    # Инициализация переменных сигнала по умолчанию (резервный локальный шаблон на украинском)
    signal_type = "⏳ ЧЕКАЙ"
    confidence = 50
    metaphor = "Ринок перебуває у фазі невизначеності, технічні індикатори не дають однозначного напрямку руху."
    
    # Логика пересечения MACD
    macd_bullish_cross = (macd['macd_prev'] <= macd['signal_prev']) and (macd['macd_curr'] > macd['signal_curr'])
    macd_bearish_cross = (macd['macd_prev'] >= macd['signal_prev']) and (macd['macd_curr'] < macd['signal_curr'])
    
    # 1. Сигнал на ПОКУПКУ (LONG)
    if price > ema50 and rsi < 55 and macd_bullish_cross:
        signal_type = "✅ КУПУЙ"
        confidence = int(85 - (rsi - 30) * 0.5)
        confidence = max(60, min(90, confidence))
        metaphor = "Ціна знаходиться вище EMA 50 (середня ціна за 50 свічок), і індикатор MACD показує бичаче перехрещення (сигнал на купівлю) при помірному RSI, що вказує на силу покупців."
        
    # 2. Сигнал на ПРОДАЖУ (SHORT)
    elif price < ema50 and rsi > 45 and macd_bearish_cross:
        signal_type = "❌ ПРОДАВАЙ"
        confidence = int(85 - (70 - rsi) * 0.5)
        confidence = max(60, min(90, confidence))
        metaphor = "Ціна торгується нижче EMA 50 (середня ціна за 50 свічок), і зафіксовано ведмеже перехрещення MACD (сигнал на продаж), що вказує на спадний імпульс."
        
    # 3. Состояние ЧЕКАЙ
    else:
        signal_type = "⏳ ЧЕКАЙ"
        confidence = 50
        if rsi > 70:
            metaphor = "Актив знаходиться в зоні перекупленості (RSI > 70, це означає, що ціну підняли занадто високо). Можлива технічна корекція (тимчасовий спад), рекомендується зачекати."
        elif rsi < 30:
            metaphor = "Актив знаходиться в зоні перепроданості (RSI < 30, це означає, що ціну опустили занадто низько). Можливий відскік вгору, але вхід в угоду зараз передчасний."
        elif abs(price - ema50) / ema50 < 0.005:
            metaphor = "Ціна коливається безпосередньо поблизу лінії EMA 50 (середня ціна за 50 свічок). Напрямок тренду (загального руху) не визначено."
        else:
            metaphor = "Технічні індикатори нейтральні, виражений трендовий рух відсутній."

    # Округление цены
    if price < 1.0:
        price_str = f"{round(price, 5):.5f}"
        if signal_type == "✅ КУПУЙ":
            stop_loss = round(price * 0.985, 5); target1 = round(price * 1.03, 5); target2 = round(price * 1.06, 5)
        elif signal_type == "❌ ПРОДАВАЙ":
            stop_loss = round(price * 1.015, 5); target1 = round(price * 0.97, 5); target2 = round(price * 0.94, 5)
        else:
            stop_loss = round(price * 0.985, 5); target1 = round(price * 1.03, 5); target2 = round(price * 1.06, 5)
    else:
        price_str = f"{int(round(price))}"
        if signal_type == "✅ КУПУЙ":
            stop_loss = int(round(price * 0.985)); target1 = int(round(price * 1.03)); target2 = int(round(price * 1.06))
        elif signal_type == "❌ ПРОДАВАЙ":
            stop_loss = int(round(price * 1.015)); target1 = int(round(price * 0.97)); target2 = int(round(price * 0.94))
        else:
            stop_loss = int(round(price * 0.985)); target1 = int(round(price * 1.03)); target2 = int(round(price * 1.06))

    # Локальные шаги по умолчанию (на украинском)
    if signal_type == "✅ КУПУЙ":
        steps = [
            "Відкрити довгу позицію - лонг (купівля з розрахунком на зростання ціни) за поточною ціною.", 
            "Встановити захисний стоп-лосс (автоматичне закриття угоди для обмеження збитків) на 1.5% нижче ціни входу.", 
            "Виставити лімітні ордери тейк-профіт (автоматичне закриття угоди для фіксації прибутку) на рівнях Цілі 1 та Цілі 2."
        ]
        one_liner = "Відкриття угоди на купівлю з обов'язковим обмеженням ризиків."
    elif signal_type == "❌ ПРОДАВАЙ":
        steps = [
            "Відкрити коротку позицію - шорт (продаж з розрахунком на падіння ціни) за поточною ціною.", 
            "Встановити захисний стоп-лосс (автоматичне закриття угоди для обмеження збитків) на 1.5% вище ціни входу.", 
            "Виставити лімітні ордери тейк-профит (автоматичне закриття угоди для фіксації прибутку) на рівнях Цілі 1 та Цілі 2."
        ]
        one_liner = "Відкриття угоди на продаж з обов'язковим обмеженням ризиків."
    else:
        steps = [
            "Утриматися від відкриття угод по активу (залишатися поза ринком).", 
            "Спостерігати за поведінкою ціни біля ключових рівнів підтримки та опору.", 
            "Очікувати формування підтвердженого сигналу від індикаторів ринку."
        ]
        one_liner = "Рекомендується перебувати поза угодами до появи зрозумілих сигналів."

    # Сначала пытаемся получить объяснение от Groq (Llama 3)
    explanation = get_groq_explanation(ticker.upper(), price_str, signal_type, rsi, macd, ema50)
    
    # Если Groq недоступен/лимит превышен, пробуем Gemini
    if not explanation:
        print("Использование Gemini API в качестве резервного источника объяснения...")
        explanation = get_gemini_explanation(ticker.upper(), price_str, signal_type, rsi, macd, ema50)
        
    # Если внешние LLM вернули ответ, обогащаем наш сигнал
    if explanation:
        metaphor = explanation['metaphor']
        one_liner = explanation['one_liner']
        steps = explanation['steps']

    return {
        'success': True,
        'ticker': ticker.upper(),
        'price': price_str,
        'signal': signal_type,
        'steps': steps,
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'metaphor': metaphor,
        'confidence': confidence,
        'one_liner': one_liner,
        'raw_price': price,
        'raw_rsi': rsi
    }

def check_arbitrage(ticker: str, threshold_pct: float = 0.1) -> dict:
    """Проверяет арбитражный спред для тикера между Binance и Bybit."""
    try:
        binance_price = get_binance_price(ticker)
        bybit_price = get_bybit_price(ticker)
        
        # Расчет спреда
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
        print(f"Ошибка проверки арбитража для {ticker}: {e}")
        return {
            'success': False,
            'error': str(e)
        }
