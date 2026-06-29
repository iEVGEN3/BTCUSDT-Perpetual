import os
import time
import threading
import json
import requests
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types
from dotenv import load_dotenv
from groq import Groq

# Принудительное использование IPv4 для обхода проблем с IPv6 на серверах Hugging Face
import socket
import urllib3.util.connection as connection
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

# Загрузка конфигурации (поиск .env в текущей папке и всех родительских)
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

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("Ошибка: Токен TELEGRAM_BOT_TOKEN не найден в .env файле!")

bot = telebot.TeleBot(TOKEN)

# Перенаправлення всіх запитів через прокси-сервер Google Apps Script для обходу блокування
telebot.apihelper.API_URL = "https://script.google.com/macros/s/AKfycbz2D6gLAkk7ZMPaC3BrZat9bNEr23d1S4TsQ69ZDvtozl_qa_Lm1VAPXVGFn60qTwSBEg/exec?token={0}&method={1}"

# Кастомна функція скачування файлів через проксі
def custom_download_file(file_path):
    url = f"https://script.google.com/macros/s/AKfycbz2D6gLAkk7ZMPaC3BrZat9bNEr23d1S4TsQ69ZDvtozl_qa_Lm1VAPXVGFn60qTwSBEg/exec?token={TOKEN}&file={file_path}"
    res = requests.get(url, timeout=30)
    data = res.json()
    import base64
    return base64.b64decode(data['base64'])

bot.download_file = custom_download_file

# Налаштування тайм-аутів для запобігання помилок мережі на серверах Hugging Face
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 60

# Налаштування команд меню для появи кнопки "Меню" / "Старт"
try:
    bot.set_my_commands([
        types.BotCommand("start", "Запустити бота та оновити меню"),
        types.BotCommand("help", "Отримати довідку та інструкцію"),
        types.BotCommand("subscribe", "Підписатися на торгові сигнали"),
        types.BotCommand("unsubscribe", "Відписатися від торгових сигналів"),
        types.BotCommand("subscribe_arbitrage", "Підписатися на арбітражні алерти"),
        types.BotCommand("unsubscribe_arbitrage", "Відписатися від арбітражних алертів")
    ])
    print("Команди меню успішно налаштовані.")
except Exception as e:
    print(f"Помилка при налаштуванні команд меню: {e}")

# Діагностика мережі на старті
def run_network_diagnostics():
    print("=== ДІАГНОСТИКА МЕРЕЖІ ===")
    hosts = [
        "google.com",
        "api.telegram.org",
        "bitter-truth-1725.glove-shramko.workers.dev",
        "fapi.binance.com",
        "api.binance.com",
        "data-api.binance.vision",
        "api.bybit.com",
        "api.bytick.com"
    ]
    for host in hosts:
        try:
            start_t = time.time()
            ip = socket.gethostbyname(host)
            conn_t = time.time() - start_t
            print(f"DNS: {host} -> {ip} (за {conn_t:.3f}с)")
            
            # Спроба підключення
            test_url = f"https://{host}"
            res = requests.get(test_url, timeout=5)
            print(f"HTTP GET {test_url} -> Статус {res.status_code}")
        except Exception as err:
            print(f"ПОМИЛКА {host}: {err}")
    print("=========================")

run_network_diagnostics()

# Импорт наших модулей (находятся в той же папке features)
import database
from signals import generate_signal, check_arbitrage

# Список основных монет
MAJOR_COINS = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'NOT']

def get_main_keyboard():
    """Створює основну клавіатуру бота."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("📈 Сигнал BTC"),
        types.KeyboardButton("📈 Сигнал ETH"),
        types.KeyboardButton("📈 Сигнал SOL"),
        types.KeyboardButton("📈 Сигнал TON"),
        types.KeyboardButton("🔔 Сигнали / Алерти"),
        types.KeyboardButton("🔕 Відписатися від сигналів"),
        types.KeyboardButton("🚨 Арбітраж / Алерти"),
        types.KeyboardButton("🔕 Відписатися від арбітражу")
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Привітальне повідомлення бота."""
    welcome_html = (
        "<h2>📊 Привіт! Я твій ф'ючерсний асистент</h2>"
        "<p>Моя головна мета — <b>допомогти тобі зберегти депозит</b> та надавати зважені торгові рекомендації "
        "на основе технічного аналізу ключових ринкових індикаторів у реальному часі.</p>"
        "<hr/>"
        "<blockquote>"
        "⚠️ <b>Правило ризик-менеджменту:</b> Рекомендується залишатися поза ринком (статус «ЧЕКАЙ») за відсутності чітких сигналів, "
        "щоб уникнути невиправданих ризиків."
        "</blockquote>"
        "<hr/>"
        "<h4>Як отримати сигнал?</h4>"
        "<ul>"
        "  <li>Натисни на одну з кнопок на клавіатурі.</li>"
        "  <li>Надішли мені тикер монети текстом (наприклад: <code>BTC</code>, <code>ETH</code>, <code>SOL</code> або <code>TON</code>).</li>"
        "  <li>🎙️ <b>Запиши голосове повідомлення</b> з назвою монети (наприклад, скажи: «Біткоїн», «Ефір», «Солана» або «Тон»).</li>"
        "</ul>"
        "<br/>"
        "<footer>Також ти можеш підписатися на автоматичні алерти за сигналами або арбітражними зв'язками через кнопки в меню!</footer>"
    )
    send_rich_message(
        message.chat.id, 
        welcome_html, 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🔔 Сигнали / Алерти")
@bot.message_handler(commands=['subscribe'])
def handle_subscribe(message):
    """Підписка користувача на розсилку торгових сигналів."""
    chat_id = message.chat.id
    username = message.from_user.username
    
    if database.is_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "😊 Ви вже підписані на торгові алерти!",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.subscribe_user(chat_id, username):
            bot.send_message(
                chat_id, 
                "🎉 **Ви успішно підписалися на торгові алерти.**\n"
                "Як тільки по основних монетах буде зафіксовано сильний технічний сигнал (Купівля або Продаж), я одразу ж вам повідомлю!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Щось пішло не так при збереженні підписки. Спробуйте пізніше.",
                reply_markup=get_main_keyboard()
            )

@bot.message_handler(func=lambda message: message.text == "🔕 Відписатися від сигналів")
@bot.message_handler(commands=['unsubscribe'])
def handle_unsubscribe(message):
    """Відписка користувача від розсилки торгових сигналів."""
    chat_id = message.chat.id
    if not database.is_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "🤷 Ви не підписані на торгові алерти.",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.unsubscribe_user(chat_id):
            bot.send_message(
                chat_id, 
                "😴 Ви успішно відписалися від розсилки сигналів.",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Не вдалося відписатися. Спробуйте ще раз.",
                reply_markup=get_main_keyboard()
            )

@bot.message_handler(func=lambda message: message.text == "🚨 Арбітраж / Алерти")
@bot.message_handler(commands=['subscribe_arbitrage'])
def handle_subscribe_arbitrage(message):
    """Підписка користувача на арбітражні алерти."""
    chat_id = message.chat.id
    username = message.from_user.username
    
    if database.is_arbitrage_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "😊 Ви вже підписані на арбітражні алерти!",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.subscribe_arbitrage(chat_id, username):
            bot.send_message(
                chat_id, 
                "🎉 **Ви успішно підписалися на арбітражні алерти.**\n"
                "Я буду відстежувати різницю курсів на Binance та Bybit. Як тільки спред перевищить 0.15%, я надішлю вам зв'язку!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Не вдалося підключити арбітражні алерти. Спробуйте пізніше.",
                reply_markup=get_main_keyboard()
            )

@bot.message_handler(func=lambda message: message.text == "🔕 Відписатися від арбітражу")
@bot.message_handler(commands=['unsubscribe_arbitrage'])
def handle_unsubscribe_arbitrage(message):
    """Відписка користувача від арбітражних алертів."""
    chat_id = message.chat.id
    if not database.is_arbitrage_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "🤷 Ви не підписані на арбітражні алерти.",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.unsubscribe_arbitrage(chat_id):
            bot.send_message(
                chat_id, 
                "😴 Ви успішно відключили арбітражні алерти.",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Не вдалося відключити алерти. Спробуйте ще раз.",
                reply_markup=get_main_keyboard()
            )

def get_rich_alternatives_html(current_ticker):
    """Проверяет альтернативные монеты и возвращает блок альтернатив в формате Rich HTML."""
    other_tickers = [t for t in ['BTC', 'ETH', 'SOL', 'TON'] if t != current_ticker]
    active_alternative = None
    
    for t in other_tickers:
        res = generate_signal(t)
        if res['success'] and res['signal'] in ["✅ КУПУЙ", "❌ ПРОДАВАЙ"]:
            active_alternative = res
            break
            
    if active_alternative:
        ticker_alt = active_alternative['ticker'].replace('USDT', '')
        sig_alt = active_alternative['signal']
        reason_alt = active_alternative['metaphor'].split('.')[0] + '.'
        price_alt = active_alternative['price']
        sl_alt = active_alternative['stop_loss']
        tp_alt = active_alternative['target1']
        
        return (
            "<hr/>"
            "<details open>"
            "  <summary>💡 Доступна альтернатива</summary>"
            f"  <p>Рекомендується розглянути: <b>{ticker_alt}</b> (статус: <mark>{sig_alt}</mark>)</p>"
            "  <ul>"
            f"    <li>Вхід: ${price_alt}</li>"
            f"    <li>Стоп-лосс: ${sl_alt}</li>"
            f"    <li>Ціль 1: ${tp_alt}</li>"
            "  </ul>"
            f"  <blockquote>{reason_alt}</blockquote>"
            "</details>"
        )
    else:
        return (
            "<hr/>"
            "<details>"
            "  <summary>💡 Альтернативні активи</summary>"
            "  <p>«Наразі по всіх інших основних монетах також рекомендується очікувати оптимальних точок входу.»</p>"
            "</details>"
        )

def format_rich_signal_message(sig_data):
    """Форматирует сигнал в красивый Rich HTML."""
    clean_ticker = sig_data['ticker'].replace('USDT', '')
    recommendation = sig_data['signal']
    
    alt_block = ""
    if sig_data['signal'] == "⏳ ЧЕКАЙ":
        alt_block = get_rich_alternatives_html(clean_ticker)
        
    html = (
        f"<h2>📈 Актив: {clean_ticker}</h2>"
        f"<p>Поточна консенсус-ціна: <b>${sig_data['price']}</b></p>"
        f"<h3>Рекомендація: <mark>{recommendation}</mark></h3>"
        "<hr/>"
        "<h4>Інструкція по кроках:</h4>"
        "<ol>"
        f"  <li>{sig_data['steps'][0]}</li>"
        f"  <li>{sig_data['steps'][1]}</li>"
        f"  <li>{sig_data['steps'][2]}</li>"
        "</ol>"
        "<hr/>"
        "<h4>Рівні угоди та ризик-менеджмент:</h4>"
        "<table bordered striped>"
        "  <tr><th>Параметр</th><th>Значение</th></tr>"
        f"  <tr><td>🛡️ <b>Стоп-лосс</b> (обмеження ризику)</td><td>${sig_data['stop_loss']}</td></tr>"
        f"  <tr><td>🎯 <b>Ціль 1</b> (фіксація 50%)</td><td>${sig_data['target1']}</td></tr>"
        f"  <tr><td>🎯 <b>Ціль 2</b> (фіксація 50%)</td><td>${sig_data['target2']}</td></tr>"
        "</table>"
        "<br/>"
        "<blockquote>"
        f"  <b>Обґрунтування:</b> {sig_data['metaphor']}"
        "</blockquote>"
        "<hr/>"
        "<details open>"
        "  <summary>📊 Параметри ризику</summary>"
        "  <ul>"
        "    <li>Рекомендований ризик на угоду: <b>0.5–1% від депозиту</b></li>"
        f"    <li>Впевненість моделі: <b>{sig_data['confidence']}%</b></li>"
        f"    <li>Резюме: <i>{sig_data['one_liner']}</i></li>"
        "  </ul>"
        "</details>"
        f"{alt_block}"
    )
    return html

def format_rich_arbitrage_message(arb_data):
    """Форматирует арбитражный сигнал в красивый Rich HTML."""
    clean_ticker = arb_data['ticker'].replace('USDT', '')
    spread = arb_data['spread_pct']
    binance_p = arb_data['binance_price']
    bybit_p = arb_data['bybit_price']
    
    html = (
        f"<h2>🚨 АРБІТРАЖНА ЗВ'ЯЗКА ДЕТЕКТОВАНА 🚨</h2>"
        f"<p>Актив: <b>{clean_ticker}</b></p>"
        f"<p>Різниця в ціні (спред): <b>{spread}%</b></p>"
        f"<hr/>"
        f"<p>📈 Купівля на Binance: <b>${binance_p}</b></p>"
        f"<p>📉 Продаж на Bybit: <b>${bybit_p}</b></p>"
        f"<hr/>"
        f"<h4>Що робити по кроках:</h4>"
        f"<ol>"
        f"  <li>Купити актив на спотовому/фьючерсному ринку Binance за ${binance_p}.</li>"
        f"  <li>Переказати / хеджувати позицію на Bybit за ціною ${bybit_p}.</li>"
        f"  <li>Закрити угоду при схлопуванні спреду.</li>"
        f"</ol>"
        f"<blockquote>Рекомендований ризик: Мінімальний (без плеча)</blockquote>"
        f"<footer>Мониторинг активный 24/7.</footer>"
    )
    return html

def send_rich_message(chat_id, html_content, reply_markup=None):
    """Отправляет Rich Message с поддержкой HTML форматирования (Bot API 10.1)."""
    url = f"https://script.google.com/macros/s/AKfycbz2D6gLAkk7ZMPaC3BrZat9bNEr23d1S4TsQ69ZDvtozl_qa_Lm1VAPXVGFn60qTwSBEg/exec?token={TOKEN}&method=sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": {
            "html": html_content
        }
    }
    if reply_markup:
        if hasattr(reply_markup, 'to_json'):
            payload["reply_markup"] = json.loads(reply_markup.to_json())
        else:
            payload["reply_markup"] = reply_markup
            
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        if not res_json.get("ok"):
            print(f"Ошибка sendRichMessage: {res_json}")
            fallback_text = html_content.replace("<br>", "\n").replace("<br/>", "\n")
            import re
            fallback_text = re.sub(r'<[^>]+>', '', fallback_text)
            return bot.send_message(chat_id, fallback_text, reply_markup=reply_markup)
        return res_json
    except Exception as e:
        print(f"Ошибка при вызове sendRichMessage: {e}")
        fallback_text = html_content.replace("<br>", "\n").replace("<br/>", "\n")
        import re
        fallback_text = re.sub(r'<[^>]+>', '', fallback_text)
        return bot.send_message(chat_id, fallback_text, reply_markup=reply_markup)

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    """Принимает голосовое сообщение, переводит в текст через Groq Whisper на украинском и выдает сигнал."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        bot.reply_to(message, "🔇 Функцію голосового введення тимчасово вимкнено (відсутній ключ GROQ_API_KEY).")
        return
        
    bot.send_chat_action(message.chat.id, 'record_audio')
    
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        voice_filename = f"voice_{message.chat.id}_{int(time.time())}.ogg"
        with open(voice_filename, 'wb') as f:
            f.write(downloaded_file)
            
        bot.send_chat_action(message.chat.id, 'typing')
        
        client = Groq(api_key=api_key)
        with open(voice_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(voice_filename, audio_file.read()),
                model="whisper-large-v3",
                language="uk",
                temperature=0.0
            )
            
        if os.path.exists(voice_filename):
            os.remove(voice_filename)
            
        transcribed_text = transcription.text.strip().lower()
        print(f"Распознанный голос (укр): {transcribed_text}")
        
        ticker = None
        if any(w in transcribed_text for w in ["біткоїн", "bitcoin", "бтк", "btc", "биткоин"]):
            ticker = "BTC"
        elif any(w in transcribed_text for w in ["ефір", "ефіріум", "ethereum", "eth", "эфир"]):
            ticker = "ETH"
        elif any(w in transcribed_text for w in ["солана", "солан", "solana", "sol"]):
            ticker = "SOL"
        elif any(w in transcribed_text for w in ["тонкоїн", "тон", "toncoin", "ton"]):
            ticker = "TON"
        elif any(w in transcribed_text for w in ["догікоїн", "догі", "дог", "doge", "доги"]):
            ticker = "DOGE"
        elif any(w in transcribed_text for w in ["ноткоїн", "нот", "notcoin", "not"]):
            ticker = "NOT"
            
        if not ticker:
            bot.reply_to(
                message, 
                f"👂 Розпізнаний текст: «{transcribed_text}».\n"
                "На жаль, тикер криптовалюти не визначено. Будь ласка, назвіть монету чітко: Біткоїн, Ефір, Солана, Тон, Догі або Нот."
            )
            return
            
        bot.send_message(message.chat.id, f"🎙️ **Голосовий запит:** {ticker}\n(Розпізнано: «{transcribed_text}»)", parse_mode='Markdown')
        
        sig_res = generate_signal(ticker)
        
        if not sig_res['success']:
            bot.reply_to(message, "Ринковий аналізатор тимчасово недоступний.")
            return
            
        formatted_msg = format_rich_signal_message(sig_res)
        send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())
        
    except Exception as e:
        print(f"Ошибка голосового ввода: {e}")
        bot.reply_to(message, f"❌ Виникла помилка під час обробки голосового повідомлення: {e}")

@bot.message_handler(func=lambda message: True)
def handle_ticker_request(message):
    """Обрабатывает текстовые запросы тикеров."""
    text = message.text.strip().upper()
    
    if text.startswith("📈 СИГНАЛ "):
        ticker = text.replace("📈 СИГНАЛ ", "")
    elif text.startswith("📈 СИГНАЛ"):
        ticker = text.replace("📈 СИГНАЛ", "")
    else:
        ticker = text
        
    ticker = ticker.replace("/", "")
    
    if not ticker or len(ticker) > 10:
        return
        
    bot.send_chat_action(message.chat.id, 'typing')
    sig_res = generate_signal(ticker)
    
    if not sig_res['success']:
        warning_msg = (
            "Ринковий аналізатор тимчасово недоступний. Перевірте підключення до мережі.\n"
            "Будь ласка, переконайтеся, що тикер введено правильно (наприклад: BTC, ETH, SOL, TON)."
        )
        bot.reply_to(message, warning_msg)
        return
        
    formatted_msg = format_rich_signal_message(sig_res)
    send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())

# --- Фоновый планировщик алертов ---
def alert_scheduler_loop():
    """Фоновый цикл проверки рынка для подписчиков каждые 15 минут."""
    print("Запущен фоновый планировщик сигналов...")
    while True:
        try:
            time.sleep(900)
            
            subscribers = database.get_all_subscribers()
            if not subscribers:
                continue
                
            for ticker in ['BTC', 'ETH', 'SOL', 'TON']:
                sig_res = generate_signal(ticker)
                if not sig_res['success']:
                    continue
                    
                if sig_res['signal'] in ["✅ КУПУЙ", "❌ ПРОДАВАЙ"]:
                    last_sig = database.get_last_signal(ticker)
                    
                    if not last_sig or last_sig['signal_type'] != sig_res['signal']:
                        database.save_signal(ticker, sig_res['raw_price'], sig_res['signal'])
                        
                        rich_alert_html = (
                            "<h2>🚨 УВАГА! ТЕХНІЧНИЙ АЛЕРТ ПО РИНКУ! 🚨</h2>"
                            f"{format_rich_signal_message(sig_res)}"
                        )
                        
                        for chat_id in subscribers:
                            try:
                                send_rich_message(chat_id, rich_alert_html)
                                time.sleep(0.05)
                            except Exception as sub_err:
                                print(f"Не удалось отправить алерт пользователю {chat_id}: {sub_err}")
                                
        except Exception as loop_err:
            print(f"Ошибка в цикле планировщика алертов: {loop_err}")
            time.sleep(60)

def arbitrage_scheduler_loop():
    """Фоновый цикл проверки арбитража каждую минуту."""
    print("Запущен фоновый планировщик арбитража...")
    while True:
        try:
            time.sleep(60)
            subscribers = database.get_all_arbitrage_subscribers()
            if not subscribers:
                continue
                
            for ticker in ['BTC', 'ETH', 'SOL', 'TON']:
                arb_res = check_arbitrage(ticker, threshold_pct=0.15)
                if not arb_res['success'] or not arb_res['is_opportunity']:
                    continue
                    
                last_arb = database.get_last_arbitrage_opportunity(ticker)
                should_send = True
                
                if last_arb:
                    last_time = last_arb['timestamp']
                    if isinstance(last_time, str):
                        try:
                            last_time = datetime.datetime.strptime(last_time.split('.')[0], "%Y-%m-%d %H:%M:%S")
                        except Exception as parse_err:
                            print(f"Ошибка парсинга даты: {parse_err}")
                            last_time = None
                    if last_time:
                        delta = (datetime.datetime.now() - last_time).total_seconds()
                        if delta < 300:
                            should_send = False
                            
                if should_send:
                    database.save_arbitrage_opportunity(
                        ticker, 
                        arb_res['binance_price'], 
                        arb_res['bybit_price'], 
                        arb_res['spread_pct']
                    )
                    rich_html = format_rich_arbitrage_message(arb_res)
                    for chat_id in subscribers:
                        try:
                            send_rich_message(chat_id, rich_html)
                            time.sleep(0.05)
                        except Exception as sub_err:
                            print(f"Не удалось отправить арбитраж на {chat_id}: {sub_err}")
                            
        except Exception as loop_err:
            print(f"Ошибка в цикле планировщика арбитража: {loop_err}")
            time.sleep(10)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Класс для обработки пингов проверки работоспособности (Render/Koyeb/HuggingFace) и вебхуков Telegram."""
    def do_GET(self):
        if self.path in ['/', '/ping']:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/webhook':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                json_string = post_data.decode('utf-8')
                update = types.Update.de_json(json_string)
                bot.process_new_updates([update])
                self.send_response(200)
                self.end_headers()
            except Exception as e:
                print(f"Помилка обробки вебхука Telegram: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.getenv('PORT', 7860))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Запущен веб-сервер проверки здоровья на порту {port}...")
    server.serve_forever()

if __name__ == '__main__':
    # Инициализация веб-сервера
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    scheduler_thread = threading.Thread(target=alert_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    arbitrage_thread = threading.Thread(target=arbitrage_scheduler_loop, daemon=True)
    arbitrage_thread.start()
    
    # Налаштування вебхука замість Polling для стабільності на Hugging Face Spaces
    time.sleep(2)  # Даємо серверу запуститися
    space_id = os.getenv('SPACE_ID')
    if space_id:
        subdomain = space_id.lower().replace('/', '-')
        webhook_url = f"https://{subdomain}.hf.space/webhook"
    else:
        webhook_url = "https://glove-3-futures-coach-bot.hf.space/webhook"
        
    # Вебхук встановлюється вручну з ПК один раз, щоб уникнути проблем з передачею urlencoded параметрів через проксі
    print("Вебхук налаштований вручну. Пропускаємо автоматичне встановлення.")
        
    print("Бот успішно запущений в режимі Webhook і готов до роботи...")
    
    # Підтримуємо активність головного потоку
    while True:
        time.sleep(3600)
