import time
import urllib.request
import os

# Скрипт периодически отправляет GET-запрос на указанный URL, 
# чтобы предотвратить переход контейнера хостинга (например, Render) в спящий режим.

URL = os.getenv("BOT_URL", "https://your-bot-name.onrender.com/ping")
INTERVAL = 600  # Интервал в секундах (10 минут)

print(f"=== Запуск скрипта поддержания активности (keep-alive) ===")
print(f"Целевой URL: {URL}")
print(f"Интервал пинга: каждые {INTERVAL // 60} минут")

while True:
    try:
        req = urllib.request.Request(
            URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) KeepAliveScript/1.0'}
        )
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Пинг: {status} | Ответ: {body}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ошибка пинга: {e}")
    
    time.sleep(INTERVAL)
