import os
import json
import math
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq
from market_data import analyze_market

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
    """Запрашивает у Groq Llama 3 простое объяснение ситуации на рынке для новичков."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return None
        
    try:
        client = Groq(api_key=api_key)
        
        system_instruction = (
            "Ты — ассистент по фьючерсной торговле для начинающих трейдеров. Твоя цель — давать лаконичные, "
            "понятные и простые торговые рекомендации. Объясняй сложные технические термины простым языком "
            "или пиши их перевод/значение в скобках (например, 'лонг (покупка на рост)', 'шорт (продажа на падение)', "
            "'тейк-профит (фиксация прибыли)', 'стоп-лосс (ограничение убытков)'). Избегай как детских метафор "
            "(никаких мишек, быков, заборов, цветов и сказок), так и сложного профессионального жаргона без объяснений."
        )
        
        trend_description = "выше" if float(price) > ema50 else "ниже"
        
        prompt = (
            f"Анализируемый актив: {ticker}\n"
            f"Текущая цена: {price}\n"
            f"Рекомендация: {signal_type}\n"
            f"Показатели рынка:\n"
            f"- Индекс силы (RSI): {rsi:.2f}\n"
            f"- Направление силы (MACD): Текущий MACD={macd['macd_curr']:.4f}, сигнальная линия={macd['signal_curr']:.4f}\n"
            f"- Общий тренд (EMA 50): Цена {trend_description} скользящей средней EMA 50 ({ema50:.2f})\n\n"
            "Сгенерируй объяснение для начинающего трейдера. Пиши просто, понятно, по делу, расшифровывая профессиональные "
            "термины. Избегай детских метафор, сказок и упрощений для детей, но пиши доступным для новичка языком. "
            "Ответ должен быть строго в формате JSON с ключами:\n"
            "1. \"metaphor\": техническое объяснение текущего состояния рынка и сигнала простыми словами для новичка (1-2 предложения, с пояснениями терминов в скобках).\n"
            "2. \"one_liner\": короткий практический совет по управлению рисками или сделкой одной строкой.\n"
            "3. \"steps\": список ровно из 3 простых шагов действий (например: открыть позицию, установить стоп-лосс, установить тейк-профит), адаптированных для новичка (с пояснениями в скобках).\n\n"
            "Верни только валидный JSON, без разметки markdown вроде ```json ... ```."
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
    """Запрашивает у Gemini простое объяснение ситуации на рынке в качестве альтернативы."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
        
    try:
        genai.configure(api_key=api_key)
        
        model_names = ["gemini-2.5-flash", "gemini-1.5-flash"]
        model = None
        system_instruction = (
            "Ты — ассистент по фьючерсной торговле для начинающих трейдеров. Твоя цель — давать лаконичные, "
            "понятные и простые торговые рекомендации. Объясняй сложные технические термины простым языком "
            "или пиши их перевод/значение в скобках (например, 'лонг (покупка на рост)', 'шорт (продажа на падение)', "
            "'тейк-профит (фиксация прибыли)', 'стоп-лосс (ограничение убытков)'). Избегай как детских метафор "
            "(никаких мишек, быков, заборов, цветов и сказок), так и сложного профессионального жаргона без объяснений."
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
            
        trend_description = "выше" if float(price) > ema50 else "ниже"
        
        prompt = (
            f"Анализируемый актив: {ticker}\n"
            f"Текущая цена: {price}\n"
            f"Рекомендация: {signal_type}\n"
            f"Показатели рынка:\n"
            f"- Индекс силы (RSI): {rsi:.2f}\n"
            f"- Направление силы (MACD): Текущий MACD={macd['macd_curr']:.4f}, сигнальная линия={macd['signal_curr']:.4f}\n"
            f"- Общий тренд (EMA 50): Цена {trend_description} скользящей средней EMA 50 ({ema50:.2f})\n\n"
            "Сгенерируй объяснение для начинающего трейдера. Пиши просто, понятно, по делу, расшифровывая профессиональные "
            "термины. Избегай детских метафор, сказок и упрощений для детей, но пиши доступным для новичка языком. "
            "Ответ должен быть строго в формате JSON с ключами:\n"
            "1. \"metaphor\": техническое объяснение текущего состояния рынка и сигнала простыми словами для новичка (1-2 предложения, с пояснениями терминов в скобках).\n"
            "2. \"one_liner\": короткий практический совет по управлению рисками или сделкой одной строкой.\n"
            "3. \"steps\": список ровно из 3 простых шагов действий (например: открыть позицию, установить стоп-лосс, установить тейк-профит), адаптированных для новичка (с пояснениями в скобках).\n\n"
            "Ответ должен быть строго в формате JSON, без лишнего текста, без символов форматирования ```json ... ```."
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
    """Анализирует рынок и генерирует детальный сигнал по шаблону осторожного тренера."""
    data = analyze_market(ticker)
    
    if not data['success']:
        return {
            'success': False,
            'error': data.get('error', 'Неизвестная ошибка анализа')
        }
        
    price = data['price']
    rsi = data['rsi']
    macd = data['macd']
    ema50 = data['ema50']
    
    # Инициализация переменных сигнала по умолчанию (резервный локальный шаблон)
    signal_type = "⏳ ЖДИ"
    confidence = 50
    metaphor = "Рынок находится в фазе неопределенности, технические индикаторы не дают однозначного направления движения."
    
    # Логика пересечения MACD
    macd_bullish_cross = (macd['macd_prev'] <= macd['signal_prev']) and (macd['macd_curr'] > macd['signal_curr'])
    macd_bearish_cross = (macd['macd_prev'] >= macd['signal_prev']) and (macd['macd_curr'] < macd['signal_curr'])
    
    # 1. Сигнал на ПОКУПКУ (LONG)
    if price > ema50 and rsi < 55 and macd_bullish_cross:
        signal_type = "✅ ПОКУПАЙ"
        confidence = int(85 - (rsi - 30) * 0.5)
        confidence = max(60, min(90, confidence))
        metaphor = "Цена находится выше EMA 50 (средняя цена за 50 свечей), и индикатор MACD показывает бычье пересечение (сигнал на покупку) при умеренном RSI, что указывает на силу покупателей."
        
    # 2. Сигнал на ПРОДАЖУ (SHORT)
    elif price < ema50 and rsi > 45 and macd_bearish_cross:
        signal_type = "❌ ПРОДАВАЙ"
        confidence = int(85 - (70 - rsi) * 0.5)
        confidence = max(60, min(90, confidence))
        metaphor = "Цена торгуется ниже EMA 50 (средняя цена за 50 свечей), и зафиксировано медвежье пересечение MACD (сигнал на продажу), что указывает на нисходящий импульс."
        
    # 3. Состояние ЖДИ
    else:
        signal_type = "⏳ ЖДИ"
        confidence = 50
        if rsi > 70:
            metaphor = "Актив находится в зоне перекупленности (RSI > 70, это означает, что цену подняли слишком высоко). Возможна техническая коррекция (временный спад), рекомендуется ожидать."
        elif rsi < 30:
            metaphor = "Актив находится в зоне перепроданности (RSI < 30, это означает, что цену опустили слишком низко). Возможен отскок вверх, но вход в сделку сейчас преждевременен."
        elif abs(price - ema50) / ema50 < 0.005:
            metaphor = "Цена колеблется непосредственно вблизи линии EMA 50 (средняя цена за 50 свечей). Направление тренда (общего движения) не определено."
        else:
            metaphor = "Технические индикаторы нейтральны, выраженное трендовое движение отсутствует."

    # Округление цены
    if price < 1.0:
        price_str = f"{round(price, 5):.5f}"
        if signal_type == "✅ ПОКУПАЙ":
            stop_loss = round(price * 0.985, 5); target1 = round(price * 1.03, 5); target2 = round(price * 1.06, 5)
        elif signal_type == "❌ ПРОДАВАЙ":
            stop_loss = round(price * 1.015, 5); target1 = round(price * 0.97, 5); target2 = round(price * 0.94, 5)
        else:
            stop_loss = round(price * 0.985, 5); target1 = round(price * 1.03, 5); target2 = round(price * 1.06, 5)
    else:
        price_str = f"{int(round(price))}"
        if signal_type == "✅ ПОКУПАЙ":
            stop_loss = int(round(price * 0.985)); target1 = int(round(price * 1.03)); target2 = int(round(price * 1.06))
        elif signal_type == "❌ ПРОДАВАЙ":
            stop_loss = int(round(price * 1.015)); target1 = int(round(price * 0.97)); target2 = int(round(price * 0.94))
        else:
            stop_loss = int(round(price * 0.985)); target1 = int(round(price * 1.03)); target2 = int(round(price * 1.06))

    # Локальные шаги по умолчанию
    if signal_type == "✅ ПОКУПАЙ":
        steps = [
            "Открыть длинную позицию - лонг (покупка с расчетом на рост цены) по текущей цене.", 
            "Установить защитный стоп-лосс (автоматическое закрытие сделки для ограничения убытков) на 1.5% ниже цены входа.", 
            "Выставить лимитные ордера тейк-профит (автоматическое закрытие сделки для фиксации прибыли) на уровнях Цели 1 и Цели 2."
        ]
        one_liner = "Открытие сделки на покупку с обязательным ограничением рисков."
    elif signal_type == "❌ ПРОДАВАЙ":
        steps = [
            "Открыть короткую позицию - шорт (продажа с расчетом на падение цены) по текущей цене.", 
            "Установить защитный стоп-лосс (автоматическое закрытие сделки для ограничения убытков) на 1.5% выше цены входа.", 
            "Выставить лимитные ордера тейк-профит (автоматическое закрытие сделки для фиксации прибыли) на уровнях Цели 1 и Цели 2."
        ]
        one_liner = "Открытие сделки на продажу с обязательным ограничением рисков."
    else:
        steps = [
            "Воздержаться от открытия сделок по активу (оставаться вне рынка).", 
            "Наблюдать за поведением цены около ключевых уровней поддержки и сопротивления.", 
            "Ожидать формирования подтвержденного сигнала от индикаторов рынка."
        ]
        one_liner = "Рекомендуется находиться вне сделок до появления понятных сигналов."

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
