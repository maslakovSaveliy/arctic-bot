#!/bin/bash

# Скрипт для развертывания Arctic Bot на VPS сервере

set -e

echo "🚀 Начинаем развертывание Arctic Bot..."

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker сначала."
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose сначала."
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден. Создайте его на основе env.example"
    echo "cp env.example .env"
    echo "Затем отредактируйте .env файл с вашими настройками"
    exit 1
fi

# Останавливаем существующие контейнеры
echo "🛑 Останавливаем существующие контейнеры..."
docker-compose down

# Исправляем права доступа к логам
if [ -f "scripts/fix-permissions.sh" ]; then
    echo "🔧 Исправляем права доступа..."
    chmod +x scripts/fix-permissions.sh
    ./scripts/fix-permissions.sh
fi

# Удаляем старые образы (опционально)
if [ "$1" = "--clean" ]; then
    echo "🧹 Удаляем старые образы..."
    docker-compose down --rmi all
fi

# Собираем и запускаем контейнеры
echo "🔨 Собираем и запускаем контейнеры..."
docker-compose up -d --build

# Ждем запуска MongoDB
echo "⏳ Ждем запуска MongoDB..."
sleep 10

# Проверяем статус контейнеров
echo "📊 Статус контейнеров:"
docker-compose ps

# Проверяем логи бота
echo "📋 Логи бота (последние 20 строк):"
docker-compose logs --tail=20 arctic-bot

echo "✅ Развертывание завершено!"
echo "📝 Для просмотра логов: docker-compose logs -f arctic-bot"
echo "🛑 Для остановки: docker-compose down" 