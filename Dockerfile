# Используем Python 3.10 для совместимости с зависимостями
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot/ ./bot/
COPY .env .

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash botuser && \
    chown -R botuser:botuser /app
USER botuser

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт (если понадобится для мониторинга)
EXPOSE 8000

# Команда запуска
CMD ["python", "-m", "bot.main"] 