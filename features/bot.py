import os
import time
import threading
import json
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types
from dotenv import load_dotenv
from groq import Groq

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

# Импорт наших модулей (находятся в той же папке features)
import database
from signals import generate_signal

# Список основных монет
MAJOR_COINS = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'NOT']

def get_main_keyboard():
    """Создает основную клавиатуру бота."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("📈 Сигнал BTC"),
        types.KeyboardButton("📈 Сигнал ETH"),
        types.KeyboardButton("📈 Сигнал SOL"),
        types.KeyboardButton("📈 Сигнал TON"),
        types.KeyboardButton("📈 Сигнал DOGE"),
        types.KeyboardButton("📈 Сигнал NOT"),
        types.KeyboardButton("🔔 Подписаться на алерты"),
        types.KeyboardButton("🔕 Отписаться от алертов")
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Приветственное сообщение бота."""
    welcome_html = (
        "<h2>📊 Привет! Я твой фьючерсный ассистент</h2>"
        "<p>Моя главная цель — <b>помочь тебе сохранить депозит</b> и предоставлять взвешенные торговые рекомендации "
        "на основе технического анализа ключевых рыночных индикаторов в реальном времени.</p>"
        "<hr/>"
        "<blockquote>"
        "⚠️ <b>Правило риск-менеджмента:</b> Рекомендуется оставаться вне рынка (статус «ЖДИ») при отсутствии четких сигналов, "
        "чтобы избежать неоправданных рисков."
        "</blockquote>"
        "<hr/>"
        "<h4>Как получить сигнал?</h4>"
        "<ul>"
        "  <li>Нажми на одну из кнопок на клавиатуре.</li>"
        "  <li>Отправь мне тикер монеты текстом (например: <code>BTC</code>, <code>ETH</code>, <code>SOL</code> или <code>TON</code>).</li>"
        "  <li>🎙️ <b>Запиши голосовое сообщение</b> с именем монеты (например, скажи: «Биткоин», «Эфир», «Солана» или «Тон»).</li>"
        "</ul>"
        "<br/>"
        "<footer>Также ты можешь подписаться на автоматические алерты, и я буду присылать тебе новые сильные сигналы сам!</footer>"
    )
    send_rich_message(
        message.chat.id, 
        welcome_html, 
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🔔 Подписаться на алерты")
@bot.message_handler(commands=['subscribe'])
def handle_subscribe(message):
    """Подписка пользователя на рассылку."""
    chat_id = message.chat.id
    username = message.from_user.username
    
    if database.is_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "😊 Ты уже подписан на рыночные алерты!",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.subscribe_user(chat_id, username):
            bot.send_message(
                chat_id, 
                "🎉 **Вы успешно подписались на алерты.**\n"
                "Как только по основным монетам будет зафиксирован сильный технический сигнал (Покупка или Продажа), я сразу же вам сообщу!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Что-то пошло не так при сохранении подписки. Попробуй позже.",
                reply_markup=get_main_keyboard()
            )

@bot.message_handler(func=lambda message: message.text == "🔕 Отписаться от алертов")
@bot.message_handler(commands=['unsubscribe'])
def handle_unsubscribe(message):
    """Отписка пользователя от рассылки."""
    chat_id = message.chat.id
    if not database.is_subscribed(chat_id):
        bot.send_message(
            chat_id, 
            "🤷 Вы не подписаны на алерты.",
            reply_markup=get_main_keyboard()
        )
    else:
        if database.unsubscribe_user(chat_id):
            bot.send_message(
                chat_id, 
                "😴 Вы успешно отписались от рассылки. При необходимости вы можете возобновить ее в любое время с помощью клавиатуры.",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.send_message(
                chat_id, 
                "❌ Не удалось отписаться. Попробуй еще раз.",
                reply_markup=get_main_keyboard()
            )

def get_alternatives_text(current_ticker):
    """Проверяет альтернативные монеты и возвращает блок альтернатив."""
    other_tickers = [t for t in ['BTC', 'ETH', 'SOL', 'TON'] if t != current_ticker]
    active_alternative = None
    
    for t in other_tickers:
        res = generate_signal(t)
        if res['success'] and res['signal'] in ["✅ ПОКУПАЙ", "❌ ПРОДАВАЙ"]:
            active_alternative = res
            break
            
    if active_alternative:
        ticker_alt = active_alternative['ticker']
        sig_alt = active_alternative['signal']
        reason_alt = active_alternative['metaphor'].split('.')[0] + '.'
        price_alt = active_alternative['price']
        sl_alt = active_alternative['stop_loss']
        tp_alt = active_alternative['target1']
        
        return (
            "Альтернативы сейчас:\n"
            f"• {ticker_alt} — {sig_alt} | {reason_alt} | Вход: ${price_alt}, Стоп: ${sl_alt}, Цель: ${tp_alt}"
        )
    else:
        return (
            "Альтернативные активы:\n"
            "«В данный момент по всем основным монетам рекомендуется ожидать оптимальных точек входа.»"
        )

def format_signal_message(sig_data):
    """Форматирует сигнал строго по заданному шаблону."""
    clean_ticker = sig_data['ticker'].replace('USDT', '')
    
    msg = (
        f"Актив: {clean_ticker}\n"
        f"Текущая цена: ≈ ${sig_data['price']}\n"
        f"Рекомендация: {sig_data['signal']}\n"
        "Инструкция по шагам:\n"
        f"1. {sig_data['steps'][0]}\n"
        f"2. {sig_data['steps'][1]}\n"
        f"3. {sig_data['steps'][2]}\n"
        "Конкретные уровни:\n"
        f"• Стоп-лосс (ограничение убытков): ${sig_data['stop_loss']}\n"
        f"• Цель 1 (фиксация прибыли): ${sig_data['target1']}\n"
        f"• Цель 2 (фиксация прибыли): ${sig_data['target2']}\n"
        f"Обоснование: {sig_data['metaphor']}\n"
        "Рекомендуемый риск: 0.5–1% от депозита.\n"
        f"Уверенность: {sig_data['confidence']}%\n"
        f"Резюме: {sig_data['one_liner']}"
    )
    
    if sig_data['signal'] == "⏳ ЖДИ":
        alt_block = get_alternatives_text(clean_ticker)
        msg += f"\n\n{alt_block}"
        
    return msg

def send_rich_message(chat_id, html_content, reply_markup=None):
    """Отправляет Rich Message с поддержкой HTML форматирования (Bot API 10.1)."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendRichMessage"
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
            # Фолбэк на обычное сообщение, если API не поддерживается или вернул ошибку
            fallback_text = html_content.replace("<br>", "\n").replace("<br/>", "\n")
            import re
            fallback_text = re.sub(r'<[^>]+>', '', fallback_text)
            return bot.send_message(chat_id, fallback_text, reply_markup=reply_markup)
        return res_json
    except Exception as e:
        print(f"Ошибка при вызове sendRichMessage: {e}")
        # Фолбэк в случае сбоя сети
        fallback_text = html_content.replace("<br>", "\n").replace("<br/>", "\n")
        import re
        fallback_text = re.sub(r'<[^>]+>', '', fallback_text)
        return bot.send_message(chat_id, fallback_text, reply_markup=reply_markup)

def get_rich_alternatives_html(current_ticker):
    """Проверяет альтернативные монеты и возвращает блок альтернатив в формате Rich HTML."""
    other_tickers = [t for t in ['BTC', 'ETH', 'SOL', 'TON'] if t != current_ticker]
    active_alternative = None
    
    for t in other_tickers:
        res = generate_signal(t)
        if res['success'] and res['signal'] in ["✅ ПОКУПАЙ", "❌ ПРОДАВАЙ"]:
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
            "  <summary>💡 Доступная альтернатива</summary>"
            f"  <p>Рекомендуется рассмотреть: <b>{ticker_alt}</b> (статус: <mark>{sig_alt}</mark>)</p>"
            "  <ul>"
            f"    <li>Вход: ${price_alt}</li>"
            f"    <li>Стоп-лосс: ${sl_alt}</li>"
            f"    <li>Цель 1: ${tp_alt}</li>"
            "  </ul>"
            f"  <blockquote>{reason_alt}</blockquote>"
            "</details>"
        )
    else:
        return (
            "<hr/>"
            "<details>"
            "  <summary>💡 Альтернативные активы</summary>"
            "  <p>«В данный момент по всем остальным основным монетам также рекомендуется ожидать оптимальных точек входа.»</p>"
            "</details>"
        )

def format_rich_signal_message(sig_data):
    """Форматирует сигнал в красивый Rich HTML."""
    clean_ticker = sig_data['ticker'].replace('USDT', '')
    recommendation = sig_data['signal']
    
    alt_block = ""
    if sig_data['signal'] == "⏳ ЖДИ":
        alt_block = get_rich_alternatives_html(clean_ticker)
        
    html = (
        f"<h2>📈 Актив: {clean_ticker}</h2>"
        f"<p>Текущая рыночная цена: <b>${sig_data['price']}</b></p>"
        f"<h3>Рекомендация: <mark>{recommendation}</mark></h3>"
        "<hr/>"
        "<h4>Инструкция по шагам:</h4>"
        "<ol>"
        f"  <li>{sig_data['steps'][0]}</li>"
        f"  <li>{sig_data['steps'][1]}</li>"
        f"  <li>{sig_data['steps'][2]}</li>"
        "</ol>"
        "<hr/>"
        "<h4>Уровни сделки и риск-менеджмент:</h4>"
        "<table bordered striped>"
        "  <tr><th>Параметр</th><th>Значение</th></tr>"
        f"  <tr><td>🛡️ <b>Стоп-лосс</b> (ограничение риска)</td><td>${sig_data['stop_loss']}</td></tr>"
        f"  <tr><td>🎯 <b>Цель 1</b> (фиксация 50%)</td><td>${sig_data['target1']}</td></tr>"
        f"  <tr><td>🎯 <b>Цель 2</b> (фиксация 50%)</td><td>${sig_data['target2']}</td></tr>"
        "</table>"
        "<br/>"
        "<blockquote>"
        f"  <b>Обоснование:</b> {sig_data['metaphor']}"
        "</blockquote>"
        "<hr/>"
        "<details open>"
        "  <summary>📊 Параметры риска</summary>"
        "  <ul>"
        "    <li>Рекомендуемый риск на сделку: <b>0.5–1% от депозита</b></li>"
        f"    <li>Уверенность модели: <b>{sig_data['confidence']}%</b></li>"
        f"    <li>Резюме: <i>{sig_data['one_liner']}</i></li>"
        "  </ul>"
        "</details>"
        f"{alt_block}"
    )
    return html

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    """Принимает голосовое сообщение, переводит в текст через Groq Whisper и выдает сигнал."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        bot.reply_to(message, "🔇 Функция голосового ввода временно отключена (отсутствует ключ GROQ_API_KEY).")
        return
        
    bot.send_chat_action(message.chat.id, 'record_audio')
    
    try:
        # Скачиваем файл из Telegram
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Записываем временный файл ogg в текущей папке
        voice_filename = f"voice_{message.chat.id}_{int(time.time())}.ogg"
        with open(voice_filename, 'wb') as f:
            f.write(downloaded_file)
            
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Отправляем в Groq Whisper для транскрипции
        client = Groq(api_key=api_key)
        with open(voice_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(voice_filename, audio_file.read()),
                model="whisper-large-v3",
                language="ru",
                temperature=0.0
            )
            
        # Удаляем временный файл ogg
        if os.path.exists(voice_filename):
            os.remove(voice_filename)
            
        transcribed_text = transcription.text.strip().lower()
        print(f"Распознанный голос: {transcribed_text}")
        
        # Сопоставляем русский голос с тикерами основных монет
        ticker = None
        if any(w in transcribed_text for w in ["биткоин", "bitcoin", "бтк", "btc"]):
            ticker = "BTC"
        elif any(w in transcribed_text for w in ["эфир", "эфириум", "ethereum", "eth"]):
            ticker = "ETH"
        elif any(w in transcribed_text for w in ["солана", "солан", "solana", "sol"]):
            ticker = "SOL"
        elif any(w in transcribed_text for w in ["тонкоин", "тон", "toncoin", "ton"]):
            ticker = "TON"
        elif any(w in transcribed_text for w in ["догикоин", "доги", "дог", "doge"]):
            ticker = "DOGE"
        elif any(w in transcribed_text for w in ["ноткоин", "нот", "notcoin", "not"]):
            ticker = "NOT"
            
        if not ticker:
            bot.reply_to(
                message, 
                f"👂 Распознанный текст: «{transcribed_text}».\n"
                "К сожалению, тикер криптовалюты не определен. Пожалуйста, назовите монету четко: Биткоин, Эфир, Солана, Тон, Доги или Нот."
            )
            return
            
        # Высылаем пользователю подтверждение распознанного тикера
        bot.send_message(message.chat.id, f"🎙️ **Голосовой запрос:** {ticker}\n(Распознано: «{transcribed_text}»)", parse_mode='Markdown')
        
        # Генерируем сигнал
        sig_res = generate_signal(ticker)
        
        if not sig_res['success']:
            bot.reply_to(message, "Рыночный анализатор временно недоступен. Пожалуйста, будьте аккуратны при самостоятельной торговле.")
            return
            
        formatted_msg = format_rich_signal_message(sig_res)
        send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())
        
    except Exception as e:
        print(f"Ошибка голосового ввода: {e}")
        bot.reply_to(message, f"❌ Произошла ошибка при обработке голосового сообщения: {e}")

@bot.message_handler(func=lambda message: True)
def handle_ticker_request(message):
    """Обрабатывает текстовые запросы тикеров."""
    text = message.text.strip().upper()
    
    if text.startswith("📈 СИГНАЛ "):
        ticker = text.replace("📈 СИГНАЛ ", "")
    else:
        ticker = text
        
    ticker = ticker.replace("/", "")
    
    if not ticker or len(ticker) > 10:
        return
        
    bot.send_chat_action(message.chat.id, 'typing')
    sig_res = generate_signal(ticker)
    
    if not sig_res['success']:
        warning_msg = (
            "Рыночный анализатор временно недоступен. Проверьте подключение к сети.\n"
            "Пожалуйста, убедитесь, что тикер введен правильно (например: BTC, ETH, SOL, TON)."
        )
        bot.reply_to(message, warning_msg)
        return
        
    formatted_msg = format_rich_signal_message(sig_res)
    send_rich_message(message.chat.id, formatted_msg, reply_markup=get_main_keyboard())

# --- Фоновый планировщик алертов ---
def alert_scheduler_loop():
    """Фоновый цикл проверки рынка для подписчиков каждые 15 минут."""
    print("Запущен фоновый планировщик алертов...")
    while True:
        try:
            time.sleep(900) # 15 минут
            
            subscribers = database.get_all_subscribers()
            if not subscribers:
                continue
                
            for ticker in ['BTC', 'ETH', 'SOL', 'TON']:
                sig_res = generate_signal(ticker)
                if not sig_res['success']:
                    continue
                    
                if sig_res['signal'] in ["✅ ПОКУПАЙ", "❌ ПРОДАВАЙ"]:
                    last_sig = database.get_last_signal(ticker)
                    
                    if not last_sig or last_sig['signal_type'] != sig_res['signal']:
                        database.save_signal(ticker, sig_res['raw_price'], sig_res['signal'])
                        
                        rich_alert_html = (
                            "<h2>🚨 ВНИМАНИЕ! ТЕХНИЧЕСКИЙ АЛЕРТ ПО РЫНКУ! 🚨</h2>"
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

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Класс для обработки пингов проверки работоспособности (Render/Koyeb)."""
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
        # Подавляем логирование обычных GET-запросов, чтобы не засорять консоль бота
        return

def run_health_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Запущен веб-сервер проверки здоровья на порту {port}...")
    server.serve_forever()

if __name__ == '__main__':
    # Запуск веб-сервера для совместимости с Render/Koyeb в фоновом режиме
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    scheduler_thread = threading.Thread(target=alert_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    print("Бот успешно запущен и готов к работе...")
    bot.infinity_polling()
