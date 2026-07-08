import os
import time
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import logging
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
telebot.apihelper.ENABLE_MIDDLEWARE = True
telebot.logger.setLevel(logging.CRITICAL)
bot = telebot.TeleBot(TOKEN)

# --- Clean Screen (Чистый Чат) Middleware & Wrapper ---
original_send_message = bot.send_message

def send_message_with_tracking(*args, **kwargs):
    sent_msg = original_send_message(*args, **kwargs)
    if sent_msg and hasattr(sent_msg, 'chat') and hasattr(sent_msg, 'message_id'):
        if sent_msg.chat.type == 'private':
            import database
            database.update_last_message_id(sent_msg.chat.id, sent_msg.message_id)
    return sent_msg

bot.send_message = send_message_with_tracking

@bot.middleware_handler(update_types=['message'])
def clean_screen_middleware(bot_instance, message):
    if message.chat.type == 'private':
        chat_id = message.chat.id
        
        # 1. Видаляємо вхідне повідомлення користувача
        try:
            bot_instance.delete_message(chat_id, message.message_id)
        except Exception as e:
            print(f"Помилка видалення вхідного повідомлення: {e}")
            
        # 2. Видаляємо останнє повідомлення бота
        import database
        last_msg_id = database.get_last_message_id(chat_id)
        if last_msg_id:
            try:
                bot_instance.delete_message(chat_id, last_msg_id)
            except Exception as e:
                pass

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
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📊 Сигнали", callback_data="menu_signals"),
        types.InlineKeyboardButton("🔔 Сповіщення", callback_data="menu_notifications")
    )
    return markup

def get_signals_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📈 BTC", callback_data="sig_BTC"),
        types.InlineKeyboardButton("📈 ETH", callback_data="sig_ETH")
    )
    markup.row(
        types.InlineKeyboardButton("📈 SOL", callback_data="sig_SOL"),
        types.InlineKeyboardButton("📈 TON", callback_data="sig_TON")
    )
    markup.row(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")
    )
    return markup

def get_notifications_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔔 Ф'ючерси", callback_data="sub_futures"),
        types.InlineKeyboardButton("🔕 Ф'ючерси", callback_data="unsub_futures")
    )
    markup.row(
        types.InlineKeyboardButton("🔔 Арбітраж", callback_data="sub_arbitrage"),
        types.InlineKeyboardButton("🔕 Арбітраж", callback_data="unsub_arbitrage")
    )
    markup.row(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")
    )
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    send_rich_message(message.chat.id, "🏠 <b>Головне меню:</b>", reply_markup=get_main_keyboard())

# --- Навігаційне меню (Текстовий фоллбек) ---

@bot.message_handler(func=lambda message: message.text == "📊 Сигнали")
def show_signals_menu(message):
    bot.send_message(message.chat.id, "📊 Оберіть актив для отримання сигналу або надішліть назву монети голосом/текстом:", reply_markup=get_signals_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔔 Сповіщення")
def show_notifications_menu(message):
    bot.send_message(message.chat.id, "🔔 Налаштування сповіщень про сигнали та арбітраж:", reply_markup=get_notifications_keyboard())

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def show_main_menu(message):
    bot.send_message(message.chat.id, "🏠 Головне меню:", reply_markup=get_main_keyboard())

# --- Обробка підписок (Команди) ---

@bot.message_handler(commands=['subscribe'])
def cmd_subscribe(message):
    chat_id = message.chat.id
    username = message.from_user.username
    if database.is_subscribed(chat_id):
        bot.send_message(chat_id, "😊 Ви вже підписані на торгові алерти!", reply_markup=get_notifications_keyboard())
    else:
        if database.subscribe_user(chat_id, username):
            bot.send_message(
                chat_id, 
                "🎉 <b>Ви успішно підписалися на торгові алерти.</b>\n"
                "Я надішлю вам сповіщення, як тільки з'явиться сильний сигнал по основних активах!",
                parse_mode='HTML',
                reply_markup=get_notifications_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Не вдалося зберегти підписку.", reply_markup=get_notifications_keyboard())

@bot.message_handler(commands=['unsubscribe'])
def cmd_unsubscribe(message):
    chat_id = message.chat.id
    if not database.is_subscribed(chat_id):
        bot.send_message(chat_id, "🤷 Ви не підписані на алерти.", reply_markup=get_notifications_keyboard())
    else:
        if database.unsubscribe_user(chat_id):
            bot.send_message(chat_id, "😴 Ви відписалися від розсилки сигналів.", reply_markup=get_notifications_keyboard())
        else:
            bot.send_message(chat_id, "❌ Сталася помилка при відписці.", reply_markup=get_notifications_keyboard())

@bot.message_handler(commands=['subscribe_arbitrage'])
def cmd_subscribe_arbitrage(message):
    chat_id = message.chat.id
    username = message.from_user.username
    if database.is_arbitrage_subscribed(chat_id):
        bot.send_message(chat_id, "😊 Ви вже підписані на арбітражні алерти!", reply_markup=get_notifications_keyboard())
    else:
        if database.subscribe_arbitrage(chat_id, username):
            bot.send_message(
                chat_id,
                "🎉 <b>Ви успішно підписалися на арбітражні алерти.</b>\n"
                "Я буду моніторити різницю цін на Binance та Bybit та сповіщу, як тільки спред перевищить 0.15%!",
                parse_mode='HTML',
                reply_markup=get_notifications_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Не вдалося зберегти підписку.", reply_markup=get_notifications_keyboard())

@bot.message_handler(commands=['unsubscribe_arbitrage'])
def cmd_unsubscribe_arbitrage(message):
    chat_id = message.chat.id
    if not database.is_arbitrage_subscribed(chat_id):
        bot.send_message(chat_id, "🤷 Ви не підписані на арбітражні алерти.", reply_markup=get_notifications_keyboard())
    else:
        if database.unsubscribe_arbitrage(chat_id):
            bot.send_message(chat_id, "😴 Ви успішно відключили арбітражні алерти.", reply_markup=get_notifications_keyboard())
        else:
            bot.send_message(chat_id, "❌ Сталася помилка при відписці.", reply_markup=get_notifications_keyboard())

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
    """Форматує сигнал у красивий Rich HTML (дозволені теги Telegram) залежно від типу рекомендації."""
    clean_ticker = sig_data['ticker'].replace('USDT', '')
    recommendation = sig_data['signal']
    
    if recommendation == "⏳ ЧЕКАЙ":
        alt_block = get_rich_alternatives_html(clean_ticker)
        html = (
            f"<b>📈 Актив: {clean_ticker}</b>\n"
            f"Поточна консенсус-ціна: <b>${sig_data['price']}</b>\n"
            f"Рекомендація: <b>{recommendation}</b>\n"
            "-------------------------------------\n"
            f"<blockquote><b>Обґрунтування:</b> {sig_data['metaphor']}</blockquote>\n"
            f"{alt_block}"
        )
        return html
        
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
        f"• Резюме: <i>{sig_data['one_liner']}</i>"
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

def edit_rich_message(chat_id, message_id, html_content, reply_markup=None):
    """Редагує HTML-повідомлення в Telegram з безпечним фоллбеком."""
    try:
        return bot.edit_message_text(html_content, chat_id=chat_id, message_id=message_id, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        print(f"Помилка редагування HTML: {e}")
        import re
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        try:
            return bot.edit_message_text(clean_text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
        except Exception as e2:
            print(f"Помилка редагування чистого тексту: {e2}")

def extract_ticker_from_text(text: str) -> str:
    text_clean = text.lower().strip()
    
    # 1. Локальний словник популярних коінів
    mappings = {
        "BTC": ["біткоїн", "bitcoin", "бтк", "btc", "биткоин"],
        "ETH": ["ефір", "ефіріум", "ethereum", "eth", "эфир", "эфириум"],
        "SOL": ["солана", "солан", "solana", "sol"],
        "TON": ["тонкоїн", "тон", "toncoin", "ton"],
        "DOGE": ["догікоїн", "догі", "дог", "doge", "доги"],
        "NOT": ["ноткоїн", "нот", "notcoin", "not"],
        "TRX": ["трон", "tron", "trx"],
        "XRP": ["ріпл", "рипл", "ripple", "xrp"],
        "LTC": ["лайткоїн", "лайткоин", "litecoin", "ltc"],
        "BNB": ["бнб", "bnb", "бінанс", "бинанс"],
        "NEAR": ["ніар", "near"],
        "SUI": ["суї", "sui"],
        "APT": ["аптос", "aptos", "apt"],
        "PEPE": ["пепе", "pepe"],
        "SHIB": ["шиба", "shiba", "shib"],
        "ADA": ["кардано", "cardano", "ada"],
        "DOT": ["полкадот", "polkadot", "dot"],
        "AVAX": ["авакс", "avalanche", "avax"],
        "LINK": ["лінк", "чейнлінк", "chainlink", "link"],
        "UNI": ["унісвоп", "uniswap", "uni"],
        "ATOM": ["атом", "космос", "cosmos", "atom"],
        "ETC": ["класик", "ethereum classic", "etc"],
        "BCH": ["біткоїн кеш", "bitcoin cash", "bch"],
        "FIL": ["файлкоїн", "filecoin", "fil"],
        "ICP": ["айсіпі", "icp"],
        "IMX": ["імутабл", "imx"],
        "FTM": ["фантом", "fantom", "ftm"]
    }
    
    for ticker, keywords in mappings.items():
        if any(w in text_clean for w in keywords):
            return ticker
            
    # 2. Перевірка на пряме входження англійських літер
    import re
    words = re.findall(r'[a-zA-Z]{2,6}', text_clean)
    if words:
        return words[0].upper()
        
    # 3. AI-розпізнавання для складних запитів
    api_key = os.getenv('GROQ_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
        
    prompt = (
        f"Знайди назву криптовалюти в наступному тексті та поверни тільки її офіційний тикер (наприклад: BTC, ETH, SOL, TRX, LTC, ADA, XRP) в форматі одного слова. "
        f"Якщо тикер знайти не вдалося, поверни 'NONE'.\n"
        f"Текст: \"{text}\"\n"
        f"Тикер:"
    )
    
    if os.getenv('GROQ_API_KEY'):
        try:
            client = Groq(api_key=os.getenv('GROQ_API_KEY'))
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.0,
                max_tokens=10
            )
            res = chat_completion.choices[0].message.content.strip().upper()
            if res != "NONE" and 2 <= len(res) <= 6:
                return res
        except Exception as e:
            print(f"Помилка отримання тикера через Groq: {e}")
            
    if os.getenv('GEMINI_API_KEY'):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            res = response.text.strip().upper()
            if res != "NONE" and 2 <= len(res) <= 6:
                return res
        except Exception as e:
            print(f"Помилка отримання тикера через Gemini: {e}")
            
    return None

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
        
        # Створюємо тимчасову папку для голосових повідомлень (на Railway використовуємо /tmp)
        tmp_dir = "/tmp"
        if not os.path.exists(tmp_dir):
            tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            
        voice_filename = os.path.join(tmp_dir, f"voice_{message.chat.id}_{int(time.time())}.ogg")
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
        
        ticker = extract_ticker_from_text(transcribed_text)
            
        if not ticker:
            bot.send_message(
                message.chat.id, 
                f"👂 Розпізнаний текст: «{transcribed_text}».\n"
                "На жаль, тикер активу не визначено. Будь ласка, скажіть назву монети чіткіше (наприклад: Біткоїн, Ефір, Солана, Трон, Догі тощо)."
            )
            return
            
        status_msg = bot.send_message(message.chat.id, f"🎙️ <b>Голосовий запит:</b> {ticker} (Розпізнано: «{transcribed_text}»)", parse_mode='HTML')
        
        sig_res = generate_signal(ticker)
        if not sig_res['success']:
            bot.send_message(message.chat.id, "Ринковий аналізатор тимчасово недоступний.")
            return
            
        formatted_msg = format_rich_signal_message(sig_res)
        
        # Видаляємо тимчасовий статус перед відправкою фінального сигналу
        if status_msg:
            try:
                bot.delete_message(message.chat.id, status_msg.message_id)
            except:
                pass
                
        send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())
        
    except Exception as e:
        print(f"Помилка обробки голосового повідомлення: {e}")
        bot.send_message(message.chat.id, f"❌ Помилка обробки голосу: {e}")

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
        bot.send_message(message.chat.id, f"Ринковий аналізатор недоступний для {ticker}. Перевірте введення (наприклад: BTC, ETH, SOL, TON).")
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

# --- Обробка підписок та меню (Inline Callbacks) ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    username = call.from_user.username
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
        
    if data == "menu_main":
        edit_rich_message(chat_id, message_id, "🏠 <b>Головне меню:</b>", reply_markup=get_main_keyboard())
            
    elif data == "menu_signals":
        edit_rich_message(chat_id, message_id, "📊 <b>Оберіть актив для отримання сигналу або надішліть назву монети голосом/текстом:</b>", reply_markup=get_signals_keyboard())
            
    elif data == "menu_notifications":
        edit_rich_message(chat_id, message_id, "🔔 <b>Налаштування сповіщень про сигнали та арбітраж:</b>", reply_markup=get_notifications_keyboard())
            
    elif data.startswith("sig_"):
        ticker = data.split("_")[1]
        bot.send_chat_action(chat_id, 'typing')
        sig_res = generate_signal(ticker)
        if not sig_res['success']:
            edit_rich_message(chat_id, message_id, "❌ Ринковий аналізатор тимчасово недоступний.", reply_markup=get_signals_keyboard())
            return
        formatted_msg = format_rich_signal_message(sig_res)
        edit_rich_message(chat_id, message_id, formatted_msg, reply_markup=get_signals_keyboard())
        
    elif data == "sub_futures":
        if database.is_subscribed(chat_id):
            edit_rich_message(chat_id, message_id, "😊 Ви вже підписані на торгові алерти!", reply_markup=get_notifications_keyboard())
        else:
            if database.subscribe_user(chat_id, username):
                text = (
                    "🎉 <b>Ви успішно підписалися на торгові алерти.</b>\n"
                    "Я надішлю вам сповіщення, як тільки з'явиться сильний сигнал по основних активах!"
                )
                edit_rich_message(chat_id, message_id, text, reply_markup=get_notifications_keyboard())
            else:
                edit_rich_message(chat_id, message_id, "❌ Не вдалося зберегти підписку.", reply_markup=get_notifications_keyboard())
                
    elif data == "unsub_futures":
        if not database.is_subscribed(chat_id):
            edit_rich_message(chat_id, message_id, "🤷 Ви не підписані на алерти.", reply_markup=get_notifications_keyboard())
        else:
            if database.unsubscribe_user(chat_id):
                edit_rich_message(chat_id, message_id, "😴 Ви відписалися від розсилки сигналів.", reply_markup=get_notifications_keyboard())
            else:
                edit_rich_message(chat_id, message_id, "❌ Сталася помилка при відписці.", reply_markup=get_notifications_keyboard())
                
    elif data == "sub_arbitrage":
        if database.is_arbitrage_subscribed(chat_id):
            edit_rich_message(chat_id, message_id, "😊 Ви вже підписані на арбітражні алерти!", reply_markup=get_notifications_keyboard())
        else:
            if database.subscribe_arbitrage(chat_id, username):
                text = (
                    "🎉 <b>Ви успішно підписалися на арбітражні алерти.</b>\n"
                    "Я буду моніторити різницю цін на Binance та Bybit та сповіщу, як тільки спред перевищить 0.15%!"
                )
                edit_rich_message(chat_id, message_id, text, reply_markup=get_notifications_keyboard())
            else:
                edit_rich_message(chat_id, message_id, "❌ Не вдалося зберегти підписку.", reply_markup=get_notifications_keyboard())
                
    elif data == "unsub_arbitrage":
        if not database.is_arbitrage_subscribed(chat_id):
            edit_rich_message(chat_id, message_id, "🤷 Ви не підписані на арбітражні алерти.", reply_markup=get_notifications_keyboard())
        else:
            if database.unsubscribe_arbitrage(chat_id):
                edit_rich_message(chat_id, message_id, "😴 Ви успішно відключили арбітражні алерти.", reply_markup=get_notifications_keyboard())
            else:
                edit_rich_message(chat_id, message_id, "❌ Сталася помилка при відписці.", reply_markup=get_notifications_keyboard())

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

def hf_space_ping_loop():
    """Фоновий цикл пінгів для запобігання засинанню Hugging Face Space."""
    time.sleep(10)  # Даємо боту спокійно запуститися
    url = os.getenv('HF_SPACE_URL', 'https://glove-3-omniroute.hf.space/').strip()
    print(f"Запущено фоновий пінгер Hugging Face Space. Ціль: {url}")
    while True:
        try:
            print(f"Надсилання запиту до Space: {url}...")
            # Робимо HTTP GET запит
            res = requests.get(url, timeout=20)
            print(f"Результат запиту до Space: статус {res.status_code}")
        except Exception as e:
            print(f"Помилка при зверненні до Space: {e}")
        # Пінгуємо кожні 9 хвилин (540 секунд)
        time.sleep(540)

if __name__ == '__main__':
    # Запуск веб-сервера для Railway
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Видалення старого вебхука для уникнення конфлікту 409
    print("Видалення старого вебхука...")
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Помилка при видаленні вебхука: {e}")

    # Запуск планувальників
    scheduler_thread = threading.Thread(target=alert_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    arbitrage_thread = threading.Thread(target=arbitrage_scheduler_loop, daemon=True)
    arbitrage_thread.start()

    # Запуск пінгера для Hugging Face Space
    hf_ping_thread = threading.Thread(target=hf_space_ping_loop, daemon=True)
    hf_ping_thread.start()
    
    print("Запуск боту в режимі polling...")
    bot.infinity_polling(none_stop=True)
