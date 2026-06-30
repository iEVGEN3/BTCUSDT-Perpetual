FROM python:3.11-slim

# Создаём пользователя
RUN useradd -m -u 1000 user

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

USER user

# Используем переменную PORT
EXPOSE $PORT

# Запуск бота
CMD ["python", "features/bot.py"]
