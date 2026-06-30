import os
import time
import threading
import json
import requests
import datetime
import telebot
from telebot import types
from dotenv import load_dotenv
from groq import Groq

# IPv4 hack
import socket
import urllib3.util.connection as connection
def allowed_gai_family():
    return socket.AF_INET
connection.allowed_gai_family = allowed_gai_family

# Загрузка .env
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
    raise ValueError("Токен TELEGRAM_BOT_TOKEN не найден!")

bot = telebot.TeleBot(TOKEN)

# Команды меню
try:
    bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("help", "Помощь"),
        types.BotCommand("subscribe", "Подписаться на сигналы"),
        types.BotCommand("unsubscribe", "Отписаться"),
        types.BotCommand("subscribe_arbitrage", "Арбитраж"),
        types.BotCommand("unsubscribe_arbitrage", "Отписаться от арбитража")
    ])
    print("Команды меню настроены.")
except Exception as e:
    print(f"Ошибка меню: {e}")

# Диагностика
def run_network_diagnostics():
    print("=== ДИАГНОСТИКА МЕРЕЖИ ===")
    # ... (оставь как было)
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
        types.KeyboardButton("🔔 Сигналы / Алерты"),
        types.KeyboardButton("🔕 Отписаться"),
        types.KeyboardButton("🚨 Арбитраж"),
        types.KeyboardButton("🔕 Отписаться от арбитража")
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Привет! Нажми кнопку для сигнала.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text.strip().upper()
    ticker = None
    if "BTC" in text: ticker = "BTC"
    elif "ETH" in text: ticker = "ETH"
    elif "SOL" in text: ticker = "SOL"
    elif "TON" in text: ticker = "TON"
    
    if ticker:
        bot.send_chat_action(message.chat.id, 'typing')
        sig = generate_signal(ticker)
        if sig['success']:
            bot.send_message(message.chat.id, f"Сигнал для {ticker}: {sig['signal']}\nЦена: {sig['price']}")
        else:
            bot.send_message(message.chat.id, "Ошибка получения сигнала.")
    else:
        bot.send_message(message.chat.id, "Не понял. Нажми кнопку.")

# Планировщики (оставь как было)
def alert_scheduler_loop():
    while True:
        time.sleep(900)  # 15 мин
        print("Проверка сигналов...")

if __name__ == '__main__':
    print("Бот запущен в режиме polling...")
    scheduler = threading.Thread(target=alert_scheduler_loop, daemon=True)
    scheduler.start()
    bot.infinity_polling()
