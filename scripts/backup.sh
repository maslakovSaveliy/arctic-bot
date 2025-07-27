#!/bin/bash

# Скрипт для резервного копирования MongoDB

set -e

# Настройки
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="arctic_bot_backup_$DATE"

# Создаем директорию для бэкапов если её нет
mkdir -p $BACKUP_DIR

echo "💾 Начинаем резервное копирование MongoDB..."

# Проверяем, что контейнер MongoDB запущен
if ! docker-compose ps mongodb | grep -q "Up"; then
    echo "❌ Контейнер MongoDB не запущен"
    exit 1
fi

# Создаем бэкап
echo "📦 Создаем бэкап: $BACKUP_NAME"
docker-compose exec -T mongodb mongodump \
    --username $MONGO_ROOT_USERNAME \
    --password $MONGO_ROOT_PASSWORD \
    --authenticationDatabase admin \
    --db $MONGODB_DB_NAME \
    --archive > "$BACKUP_DIR/$BACKUP_NAME.archive"

# Сжимаем бэкап
echo "🗜️ Сжимаем бэкап..."
gzip "$BACKUP_DIR/$BACKUP_NAME.archive"

# Удаляем старые бэкапы (оставляем последние 7)
echo "🧹 Удаляем старые бэкапы (оставляем последние 7)..."
ls -t $BACKUP_DIR/*.archive.gz | tail -n +8 | xargs -r rm

echo "✅ Резервное копирование завершено!"
echo "📁 Бэкап сохранен: $BACKUP_DIR/$BACKUP_NAME.archive.gz"

# Показываем размер бэкапа
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.archive.gz" | cut -f1)
echo "📏 Размер бэкапа: $BACKUP_SIZE" 