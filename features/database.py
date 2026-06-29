import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db.sqlite3')

def get_connection():
    """Возвращает подключение к базе данных SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализирует базу данных: создает таблицы, если они не существуют."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица подписчиков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица истории сигналов (чтобы не спамить одинаковыми сигналами)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                signal_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def subscribe_user(chat_id: int, username: str = None) -> bool:
    """Подписывает пользователя на сигналы. Возвращает True, если успешно подписан впервые."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO subscriptions (chat_id, username) VALUES (?, ?)",
                (chat_id, username)
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Ошибка при подписке: {e}")
        return False

def unsubscribe_user(chat_id: int) -> bool:
    """Отписывает пользователя от сигналов. Возвращает True, если отписка прошла успешно."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"Ошибка при отписке: {e}")
        return False

def is_subscribed(chat_id: int) -> bool:
    """Проверяет, подписан ли пользователь."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM subscriptions WHERE chat_id = ?", (chat_id,))
        return cursor.fetchone() is not None

def get_all_subscribers() -> list:
    """Возвращает список всех chat_id подписчиков."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM subscriptions")
        rows = cursor.fetchall()
        return [row['chat_id'] for row in rows]

def save_signal(ticker: str, price: float, signal_type: str):
    """Сохраняет сигнал в историю."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO signal_history (ticker, price, signal_type) VALUES (?, ?, ?)",
                (ticker.upper(), price, signal_type)
            )
            conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении сигнала: {e}")

def get_last_signal(ticker: str) -> dict:
    """Возвращает последний отправленный сигнал по тикеру."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT signal_type, price, timestamp FROM signal_history WHERE ticker = ? ORDER BY id DESC LIMIT 1",
            (ticker.upper(),)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

# Инициализируем БД при первом импорте модуля
init_db()
