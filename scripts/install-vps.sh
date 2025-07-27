#!/bin/bash

# Скрипт автоматической установки Arctic Bot на VPS сервер

set -e

echo "🚀 Начинаем установку Arctic Bot на VPS сервер..."

# Проверяем, что мы root или используем sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Этот скрипт должен быть запущен с правами root или через sudo"
    exit 1
fi

# Обновляем систему
echo "📦 Обновляем систему..."
apt update && apt upgrade -y

# Устанавливаем необходимые пакеты
echo "🔧 Устанавливаем необходимые пакеты..."
apt install -y curl wget git nano htop ufw

# Устанавливаем Docker
echo "🐳 Устанавливаем Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "✅ Docker уже установлен"
fi

# Устанавливаем Docker Compose
echo "📋 Устанавливаем Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "✅ Docker Compose уже установлен"
fi

# Создаем пользователя для бота
echo "👤 Создаем пользователя для бота..."
if ! id "arcticbot" &>/dev/null; then
    useradd -m -s /bin/bash arcticbot
    usermod -aG docker arcticbot
    echo "✅ Пользователь arcticbot создан"
else
    echo "✅ Пользователь arcticbot уже существует"
fi

# Настраиваем файрвол
echo "🔥 Настраиваем файрвол..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
echo "✅ Файрвол настроен"

# Создаем директории
echo "📁 Создаем необходимые директории..."
mkdir -p /opt/arctic-bot
mkdir -p /opt/arctic-bot/logs
mkdir -p /opt/arctic-bot/backups
chown -R arcticbot:arcticbot /opt/arctic-bot

# Копируем файлы проекта (если они есть в текущей директории)
if [ -f "docker-compose.yml" ]; then
    echo "📋 Копируем файлы проекта..."
    cp -r . /opt/arctic-bot/
    chown -R arcticbot:arcticbot /opt/arctic-bot
else
    echo "⚠️  Файлы проекта не найдены в текущей директории"
    echo "📝 Пожалуйста, скопируйте файлы проекта в /opt/arctic-bot/"
fi

# Настраиваем systemd сервис
echo "⚙️ Настраиваем systemd сервис..."
if [ -f "arctic-bot-docker.service" ]; then
    cp arctic-bot-docker.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable arctic-bot-docker.service
    echo "✅ Systemd сервис настроен"
else
    echo "⚠️  Файл arctic-bot-docker.service не найден"
fi

# Настраиваем логирование
echo "📝 Настраиваем логирование..."
cat > /etc/logrotate.d/arctic-bot << EOF
/opt/arctic-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 arcticbot arcticbot
    postrotate
        systemctl reload arctic-bot-docker.service
    endscript
}
EOF

# Настраиваем cron для резервного копирования
echo "💾 Настраиваем автоматическое резервное копирование..."
(crontab -u arcticbot -l 2>/dev/null; echo "0 2 * * * /opt/arctic-bot/scripts/backup.sh") | crontab -u arcticbot -

# Настраиваем мониторинг
echo "📊 Настраиваем базовый мониторинг..."
cat > /opt/arctic-bot/scripts/health-check.sh << 'EOF'
#!/bin/bash
# Проверка здоровья сервисов

if ! docker-compose -f /opt/arctic-bot/docker-compose.yml ps | grep -q "Up"; then
    echo "❌ Arctic Bot не запущен, перезапускаем..."
    docker-compose -f /opt/arctic-bot/docker-compose.yml up -d
    echo "✅ Arctic Bot перезапущен"
fi
EOF

chmod +x /opt/arctic-bot/scripts/health-check.sh
chown arcticbot:arcticbot /opt/arctic-bot/scripts/health-check.sh

# Добавляем проверку здоровья в cron
(crontab -u arcticbot -l 2>/dev/null; echo "*/5 * * * * /opt/arctic-bot/scripts/health-check.sh") | crontab -u arcticbot -

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Переключитесь на пользователя arcticbot: su - arcticbot"
echo "2. Перейдите в директорию: cd /opt/arctic-bot"
echo "3. Создайте файл .env: cp env.example .env"
echo "4. Отредактируйте .env файл с вашими настройками"
echo "5. Запустите бота: ./scripts/deploy.sh"
echo ""
echo "🔧 Полезные команды:"
echo "- Просмотр логов: docker-compose logs -f arctic-bot"
echo "- Статус сервисов: docker-compose ps"
echo "- Остановка: docker-compose down"
echo "- Перезапуск: systemctl restart arctic-bot-docker.service"
echo ""
echo "📞 Для получения помощи обратитесь к DOCKER_README.md" 