import os
import time
import threading
import json
import requests
import datetime
import socket
import urllib3.util.connection as connection
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types
from dotenv import load_dotenv
from groq import Groq

# IPv4 hack
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

# Завантаження .env
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

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен TELEGRAM_BOT_TOKEN не знайдено!")

bot = telebot.TeleBot(TOKEN)

# Налаштування тайм-аутів
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 60

# Команди меню
try:
    bot.set_my_commands([
        types.BotCommand("start", "Запустити бота та відкрити меню"),
        types.BotCommand("help", "Отримати інструкцію"),
        types.BotCommand("subscribe", "Підписатися на сигнали"),
        types.BotCommand("unsubscribe", "Відписатися від сигналів"),
        types.BotCommand("subscribe_arbitrage", "Підписатися на арбітраж"),
        types.BotCommand("unsubscribe_arbitrage", "Відписатися від арбитражу")
    ])
    print("Команди меню налаштовані.")
except Exception as e:
    print(f"Помилка встановлення меню: {e}")

# Діагностика мережі
def run_network_diagnostics():
    print("=== ДІАГНОСТИКА МЕРЕЖІ ===")
    hosts = [
        "google.com",
        "api.telegram.org",
        "binance-proxy.glove-shramko.workers.dev",
        "fapi.binance.com",
        "api.binance.com"
    ]
    for host in hosts:
        try:
            start_t = time.time()
            ip = socket.gethostbyname(host)
            conn_t = time.time() - start_t
            print(f"DNS: {host} -> {ip} (за {conn_t:.3f}с)")
            
            test_url = f"https://{host}"
            res = requests.get(test_url, timeout=5)
            print(f"HTTP GET {test_url} -> Статус {res.status_code}")
        except Exception as err:
            print(f"ПОМИЛКА {host}: {err}")
    print("=========================")

run_network_diagnostics()

import database
from signals import generate_signal, check_arbitrage

MAJOR_COINS = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'NOT']

def get_main_keyboard():
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
    welcome_text = (
        "<b>📊 Привіт! Я твій ф'ючерсний асистент</b>\n\n"
        "Моя мета — допомогти тобі зберегти депозит та надавати зважені торгові "
        "рекомендації на основі технічного аналізу ключових індикаторів.\n\n"
        "⚠️ <b>Ризик-менеджмент:</b> Завжди використовуй стоп-лосс та контролюй ризик на угоду (0.5–1%).\n\n"
        "<b>Доступні функції:</b>\n"
        "• Натискай кнопки під моїм повідомленням для отримання миттєвого сигналу.\n"
        "• Запиши мені голосове повідомлення з назвою монети (наприклад: «біткоїн», «ефір», «солана»).\n"
        "• Підпишись на розсилку сигналів або арбітражних алертов через меню або кнопки."
    )
    send_rich_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

# --- Обробка підписок ---

@bot.message_handler(func=lambda message: message.text == "🔔 Сигнали / Алерти")
@bot.message_handler(commands=['subscribe'])
def handle_subscribe(message):
    chat_id = message.chat.id
    username = message.from_user.username
    if database.is_subscribed(chat_id):
        bot.send_message(chat_id, "😊 Ви вже підписані на торгові алерти!", reply_markup=get_main_keyboard())
    else:
        if database.subscribe_user(chat_id, username):
            bot.send_message(
                chat_id, 
                "🎉 <b>Ви успішно підписалися на торгові алерти.</b>\n"
                "Я надішлю вам сповіщення, як тільки з'явиться сильний сигнал по основних активах!",
                parse_mode='HTML',
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Не вдалося зберегти підписку. Спробуйте пізніше.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔕 Відписатися від сигналів")
@bot.message_handler(commands=['unsubscribe'])
def handle_unsubscribe(message):
    chat_id = message.chat.id
    if not database.is_subscribed(chat_id):
        bot.send_message(chat_id, "🤷 Ви не підписані на алерти.", reply_markup=get_main_keyboard())
    else:
        if database.unsubscribe_user(chat_id):
            bot.send_message(chat_id, "😴 Ви відписалися від розсилки сигналів.", reply_markup=get_main_keyboard())
        else:
            bot.send_message(chat_id, "❌ Сталася помилка при відписці.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🚨 Арбітраж / Алерти")
@bot.message_handler(commands=['subscribe_arbitrage'])
def handle_subscribe_arbitrage(message):
    chat_id = message.chat.id
    username = message.from_user.username
    if database.is_arbitrage_subscribed(chat_id):
        bot.send_message(chat_id, "😊 Ви вже підписані на арбітражні алерти!", reply_markup=get_main_keyboard())
    else:
        if database.subscribe_arbitrage(chat_id, username):
            bot.send_message(
                chat_id,
                "🎉 <b>Ви успішно підписалися на арбітражні алерти.</b>\n"
                "Я буду моніторити різницю цін на Binance та Bybit та сповіщу, як тільки спред перевищить 0.15%!",
                parse_mode='HTML',
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Не вдалося зберегти підписку. Спробуйте пізніше.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔕 Відписатися від арбітражу")
@bot.message_handler(commands=['unsubscribe_arbitrage'])
def handle_unsubscribe_arbitrage(message):
    chat_id = message.chat.id
    if not database.is_arbitrage_subscribed(chat_id):
        bot.send_message(chat_id, "🤷 Ви не підписані на арбітражні алерти.", reply_markup=get_main_keyboard())
    else:
        if database.unsubscribe_arbitrage(chat_id):
            bot.send_message(chat_id, "😴 Ви успішно відключили арбітражні алерти.", reply_markup=get_main_keyboard())
        else:
            bot.send_message(chat_id, "❌ Сталася помилка при відписці.", reply_markup=get_main_keyboard())

# --- Обробка сигналів та повідомлень ---

def get_rich_alternatives_html(current_ticker):
    """Шукає альтернативні монети та повертає блок альтернатив."""
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
            "\n-------------------------------------\n"
            f"💡 <b>Доступна альтернатива:</b>\n"
            f"Рекомендується розглянути: <b>{ticker_alt}</b> (статус: <b>{sig_alt}</b>)\n"
            f"• Вхід: ${price_alt}\n"
            f"• Стоп-лосс: ${sl_alt}\n"
            f"• Ціль 1: ${tp_alt}\n"
            f"<blockquote>{reason_alt}</blockquote>"
        )
    else:
        return (
            "\n-------------------------------------\n"
            f"💡 <b>Альтернативні активи:</b>\n"
            "Наразі по всіх інших основних монетах також рекомендується очікувати оптимальних точок входу."
        )

def format_rich_signal_message(sig_data):
    """Форматує сигнал у красивий Rich HTML (дозволені теги Telegram)."""
    clean_ticker = sig_data['ticker'].replace('USDT', '')
    recommendation = sig_data['signal']
    
    alt_block = ""
    if sig_data['signal'] == "⏳ ЧЕКАЙ":
        alt_block = get_rich_alternatives_html(clean_ticker)
        
    steps_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(sig_data['steps'])])
    
    html = (
        f"<b>📈 Актив: {clean_ticker}</b>\n"
        f"Поточна консенсус-ціна: <b>${sig_data['price']}</b>\n"
        f"Рекомендація: <b>{recommendation}</b>\n"
        "-------------------------------------\n"
        f"<b>Інструкція по кроках:</b>\n{steps_formatted}\n"
        "-------------------------------------\n"
        f"<b>Рівні угоди та ризик-менеджмент:</b>\n"
        f"🛡️ <b>Стоп-лосс:</b> ${sig_data['stop_loss']}\n"
        f"🎯 <b>Ціль 1:</b> ${sig_data['target1']}\n"
        f"🎯 <b>Ціль 2:</b> ${sig_data['target2']}\n\n"
        f"<blockquote><b>Обґрунтування:</b> {sig_data['metaphor']}</blockquote>\n"
        "-------------------------------------\n"
        f"📊 <b>Параметри ризику:</b>\n"
        f"• Рекомендований ризик: <b>0.5–1% від депозиту</b>\n"
        f"• Впевненість моделі: <b>{sig_data['confidence']}%</b>\n"
        f"• Резюме: <i>{sig_data['one_liner']}</i>\n"
        f"{alt_block}"
    )
    return html

def format_rich_arbitrage_message(arb_data):
    """Форматує арбітражний сигнал у красивий Rich HTML."""
    clean_ticker = arb_data['ticker'].replace('USDT', '')
    spread = arb_data['spread_pct']
    binance_p = arb_data['binance_price']
    bybit_p = arb_data['bybit_price']
    
    html = (
        f"<b>🚨 АРБІТРАЖНА ЗВ'ЯЗКА ДЕТЕКТОВАНА 🚨</b>\n"
        f"Актив: <b>{clean_ticker}</b>\n"
        f"Різниця в ціні (спред): <b>{spread}%</b>\n"
        f"-------------------------------------\n"
        f"📈 Купівля на Binance: <b>${binance_p}</b>\n"
        f"📉 Продаж на Bybit: <b>${bybit_p}</b>\n"
        f"-------------------------------------\n"
        f"<b>Що робити по кроках:</b>\n"
        f"1. Купити актив на спотовому/фьючерсному ринку Binance за ${binance_p}.\n"
        f"2. Переказати / хеджувати позицію на Bybit за ціною ${bybit_p}.\n"
        f"3. Закрити угоду при схлопуванні спреду.\n\n"
        f"<blockquote>Рекомендований ризик: Мінімальний (без плеча)</blockquote>\n"
        f"<i>Моніторинг активний 24/7.</i>"
    )
    return html

def send_rich_message(chat_id, html_content, reply_markup=None):
    """Відправляє HTML-повідомлення в Telegram з безпечним фоллбеком."""
    try:
        return bot.send_message(chat_id, html_content, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        print(f"Помилка відправки HTML: {e}")
        import re
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        return bot.send_message(chat_id, clean_text, reply_markup=reply_markup)

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    """Отримує голосове повідомлення, трансформує в текст через Groq Whisper та генерує сигнал."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        bot.reply_to(message, "🔇 Функцію голосового введення тимчасово вимкнено (відсутній Groq API Key).")
        return
        
    bot.send_chat_action(message.chat.id, 'record_audio')
    
    try:
        file_info = bot.get_file(message.voice.file_id)
        # Скачування файлу
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        res = requests.get(file_url, timeout=30)
        
        voice_filename = f"voice_{message.chat.id}_{int(time.time())}.ogg"
        with open(voice_filename, 'wb') as f:
            f.write(res.content)
            
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
        print(f"Розпізнаний голос (укр): {transcribed_text}")
        
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
                "На жаль, тикер активу не визначено. Скажіть назву чіткіше (Біткоїн, Ефір, Солана, Тон)."
            )
            return
            
        bot.send_message(message.chat.id, f"🎙️ <b>Голосовий запит:</b> {ticker} (Розпізнано: «{transcribed_text}»)", parse_mode='HTML')
        
        sig_res = generate_signal(ticker)
        if not sig_res['success']:
            bot.reply_to(message, "Ринковий аналізатор тимчасово недоступний.")
            return
            
        formatted_msg = format_rich_signal_message(sig_res)
        send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())
        
    except Exception as e:
        print(f"Помилка обробки голосового повідомлення: {e}")
        bot.reply_to(message, f"❌ Помилка обробки голосу: {e}")

@bot.message_handler(func=lambda message: True)
def handle_ticker_request(message):
    text = message.text.strip().upper()
    if text.startswith("📈 СИГНАЛ "):
        ticker = text.replace("📈 СИГНАЛ ", "")
    elif text.startswith("📈 СИГНАЛ"):
        ticker = text.replace("📈 СИГНАЛ", "")
    else:
        ticker = text
        
    ticker = ticker.replace("/", "")
    if len(ticker) > 10:
        return
        
    bot.send_chat_action(message.chat.id, 'typing')
    sig_res = generate_signal(ticker)
    
    if not sig_res['success']:
        bot.reply_to(message, f"Ринковий аналізатор недоступний для {ticker}. Перевірте введення (наприклад: BTC, ETH, SOL, TON).")
        return
        
    formatted_msg = format_rich_signal_message(sig_res)
    send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())

# --- Фоновий планувальник алертов ---

def alert_scheduler_loop():
    """Фоновий цикл перевірки ринку кожні 15 хвилин."""
    print("Запущено фоновий планувальник сигналів...")
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
                            "<b>🚨 УВАГА! ТЕХНІЧНИЙ АЛЕРТ ПО РИНКУ! 🚨</b>\n\n"
                            f"{format_rich_signal_message(sig_res)}"
                        )
                        for chat_id in subscribers:
                            try:
                                send_rich_message(chat_id, rich_alert_html)
                                time.sleep(0.05)
                            except Exception as sub_err:
                                print(f"Не вдалося надіслати алерт на {chat_id}: {sub_err}")
        except Exception as e:
            print(f"Помилка в планувальнику сигналів: {e}")
            time.sleep(60)

def arbitrage_scheduler_loop():
    """Фоновий цикл перевірки арбітражу щохвилини."""
    print("Запущено фоновий планувальник арбітражу...")
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
                            print(f"Помилка парсингу дати: {parse_err}")
                            last_time = None
                    if last_time:
                        delta = (datetime.datetime.now() - last_time).total_seconds()
                        if delta < 300: # Інтервал 5 хвилин між повідомленнями про один актив
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
                            print(f"Не вдалося надіслати арбітраж на {chat_id}: {sub_err}")
        except Exception as e:
            print(f"Помилка в планувальнику арбітражу: {e}")
            time.sleep(10)

# --- Веб-сервер перевірки працездатності (Health Check) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/ping']:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return

def run_health_server():
    raw_port = os.getenv('PORT', '8080')
    # Очищуємо значення порту від можливих інлайн-коментарів
    port_str = raw_port.split('#')[0].strip()
    try:
        port = int(port_str)
    except ValueError:
        print(f"Помилка парсингу порту '{raw_port}', встановлено дефолтний 8080")
        port = 8080
        
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Запущено веб-сервер перевірки здоров'я на порту {port}...")
    server.serve_forever()

if __name__ == '__main__':
    # Запуск веб-сервера для Railway
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Запуск планувальників
    scheduler_thread = threading.Thread(target=alert_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    arbitrage_thread = threading.Thread(target=arbitrage_scheduler_loop, daemon=True)
    arbitrage_thread.start()
    
    print("Запуск боту в режимі polling...")
    bot.infinity_polling(none_stop=True)
