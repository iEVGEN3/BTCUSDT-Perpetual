FROM python:3.11-slim

# Создаем пользователя с UID 1000 для совместимости с Hugging Face Spaces
RUN useradd -m -u 1000 user

# Установка рабочей директории
WORKDIR /app

# Копирование списка зависимостей
COPY --chown=user:user requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов проекта
COPY --chown=user:user . .

# Переключение на созданного пользователя
USER user

# Открываем порт 7860
EXPOSE 7860

# Команда для запуска бота
CMD ["python", "features/bot.py"]
