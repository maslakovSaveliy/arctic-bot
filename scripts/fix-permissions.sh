#!/bin/bash

# Скрипт для исправления прав доступа к логам

set -e

echo "🔧 Исправляем права доступа к логам..."

# Создаем директорию logs если её нет
mkdir -p logs

# Устанавливаем правильные права
chmod 755 logs
chown 1000:1000 logs

# Создаем файл bot.log если его нет
touch logs/bot.log
chmod 644 logs/bot.log
chown 1000:1000 logs/bot.log

echo "✅ Права доступа исправлены"
echo "📁 Директория logs: $(ls -la logs/)" 