import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Загружаем переменные окружения
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

DB_URL = os.getenv('DATABASE_URL')

if not DB_URL:
    raise ValueError("Ошибка: Переменная окружения DATABASE_URL не найдена!")

def get_connection():
    """Возвращает подключение к базе данных PostgreSQL."""
    return psycopg2.connect(DB_URL)

def init_db():
    """Инициализирует базу данных: создает таблицы в Neon.tech, если они не существуют."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Таблица подписчиков на сигналы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id BIGINT PRIMARY KEY,
                    username VARCHAR(100),
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    arbitrage_subscribed BOOLEAN DEFAULT FALSE
                );
            ''')
            
            # Таблица истории сигналов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signal_history (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(20) NOT NULL,
                    price NUMERIC NOT NULL,
                    signal_type VARCHAR(20) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Таблица истории арбитражных связок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arbitrage_history (
                    id SERIAL PRIMARY KEY,
                    ticker VARCHAR(20) NOT NULL,
                    binance_price NUMERIC NOT NULL,
                    bybit_price NUMERIC NOT NULL,
                    spread_pct NUMERIC NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Добавляем колонку last_message_id, если она еще не создана
            cursor.execute("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_message_id INT;")
            conn.commit()

def get_last_message_id(chat_id: int) -> int:
    """Возвращает ID последнего сообщения бота в этом чате."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT last_message_id FROM subscriptions WHERE chat_id = %s", (chat_id,))
                row = cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        print(f"Ошибка получения last_message_id: {e}")
        return None

def update_last_message_id(chat_id: int, message_id: int) -> bool:
    """Обновляет или добавляет ID последнего сообщения бота."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (chat_id, last_message_id) 
                    VALUES (%s, %s) 
                    ON CONFLICT (chat_id) 
                    DO UPDATE SET last_message_id = EXCLUDED.last_message_id
                    """,
                    (chat_id, message_id)
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"Ошибка обновления last_message_id: {e}")
        return False

# --- Логика торговых сигналов ---

def subscribe_user(chat_id: int, username: str = None) -> bool:
    """Подписывает пользователя на торговые сигналы."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (chat_id, username) 
                    VALUES (%s, %s) 
                    ON CONFLICT (chat_id) 
                    DO UPDATE SET username = EXCLUDED.username
                    """,
                    (chat_id, username)
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"Ошибка при подписке на сигналы: {e}")
        return False

def unsubscribe_user(chat_id: int) -> bool:
    """Отписывает пользователя от торговых сигналов."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM subscriptions WHERE chat_id = %s", (chat_id,))
                conn.commit()
                return True
    except Exception as e:
        print(f"Ошибка при отписке от сигналов: {e}")
        return False

def is_subscribed(chat_id: int) -> bool:
    """Проверяет, подписан ли пользователь на торговые сигналы."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM subscriptions WHERE chat_id = %s", (chat_id,))
                return cursor.fetchone() is not None
    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
        return False

def get_all_subscribers() -> list:
    """Возвращает список всех chat_id подписчиков на сигналы."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT chat_id FROM subscriptions")
                return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Ошибка при получении всех подписчиков: {e}")
        return []

def save_signal(ticker: str, price: float, signal_type: str):
    """Сохраняет сгенерированный торговый сигнал в историю."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO signal_history (ticker, price, signal_type) VALUES (%s, %s, %s)",
                    (ticker.upper(), price, signal_type)
                )
                conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении сигнала: {e}")

def get_last_signal(ticker: str) -> dict:
    """Возвращает последний отправленный торговый сигнал по тикеру."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT signal_type, price, timestamp FROM signal_history WHERE ticker = %s ORDER BY id DESC LIMIT 1",
                    (ticker.upper(),)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        print(f"Ошибка получения последнего сигнала: {e}")
        return None

# --- Логика межбиржевого арбитража ---

def subscribe_arbitrage(chat_id: int, username: str = None) -> bool:
    """Подписывает пользователя на арбитражные алерты."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (chat_id, username, arbitrage_subscribed) 
                    VALUES (%s, %s, TRUE) 
                    ON CONFLICT (chat_id) 
                    DO UPDATE SET arbitrage_subscribed = TRUE, username = EXCLUDED.username
                    """,
                    (chat_id, username)
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"Ошибка при подписке на арбитраж: {e}")
        return False

def unsubscribe_arbitrage(chat_id: int) -> bool:
    """Отписывает пользователя от арбитражных алертов."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE subscriptions SET arbitrage_subscribed = FALSE WHERE chat_id = %s",
                    (chat_id,)
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"Ошибка при отписке от арбитража: {e}")
        return False

def is_arbitrage_subscribed(chat_id: int) -> bool:
    """Проверяет, подписан ли пользователь на арбитражные алерты."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT arbitrage_subscribed FROM subscriptions WHERE chat_id = %s", (chat_id,))
                row = cursor.fetchone()
                return row is not None and row[0] is True
    except Exception as e:
        print(f"Ошибка при проверке арбитражной подписки: {e}")
        return False

def get_all_arbitrage_subscribers() -> list:
    """Возвращает список всех chat_id подписчиков на арбитражные алерты."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT chat_id FROM subscriptions WHERE arbitrage_subscribed = TRUE")
                return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Ошибка при получении подписчиков арбитража: {e}")
        return []

def save_arbitrage_opportunity(ticker: str, binance_price: float, bybit_price: float, spread_pct: float):
    """Сохраняет найденную арбитражную связку в базу данных."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO arbitrage_history (ticker, binance_price, bybit_price, spread_pct) 
                    VALUES (%s, %s, %s, %s)
                    """,
                    (ticker.upper(), binance_price, bybit_price, spread_pct)
                )
                conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении арбитражной связки: {e}")

def get_last_arbitrage_opportunity(ticker: str) -> dict:
    """Возвращает последнюю зафиксированную арбитражную связку по тикеру."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT binance_price, bybit_price, spread_pct, timestamp FROM arbitrage_history WHERE ticker = %s ORDER BY id DESC LIMIT 1",
                    (ticker.upper(),)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        print(f"Ошибка получения последней арбитражной связки: {e}")
        return None

# Инициализируем БД при импорте модуля
init_db()
