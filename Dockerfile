FROM python:3.11-slim

# Установка рабочей директории
WORKDIR /app

# Копирование списка зависимостей
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов проекта
COPY . .

# Команда для запуска бота
CMD ["python", "features/bot.py"]
