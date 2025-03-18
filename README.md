# Telegram-бот для управления приватным каналом

Бот для автоматизации процессов одобрения подписчиков, сбора данных о них и проведения рассылок в приватном Telegram-канале.

## Функциональность

- Автоматическое одобрение заявок на подписку
- Отслеживание источников пользователей
- Создание и управление пригласительными ссылками
- Отправка рассылок и уведомлений
- Сбор статистики по подписчикам

## Установка и настройка

### Предварительные требования

- Python 3.10 или 3.11 (рекомендуется, есть проблемы совместимости с Python 3.13)
- MongoDB
- Зарегистрированный Telegram-бот (через BotFather)
- Приватный канал с ботом-администратором

### Установка

1. Клонируйте репозиторий:
```
git clone https://github.com/your-username/telegram-channel-bot.git
cd telegram-channel-bot
```

2. Создайте виртуальное окружение с Python 3.10 или 3.11 и активируйте его:

**Для macOS:**
```bash
# Установка Python 3.10 через Homebrew (если не установлен)
brew install python@3.10

# Создание виртуального окружения
/opt/homebrew/bin/python3.10 -m venv venv
source venv/bin/activate
```

**Для Linux:**
```bash
# Установка Python 3.10 (если не установлен)
sudo apt update
sudo apt install python3.10 python3.10-venv

# Создание виртуального окружения
python3.10 -m venv venv
source venv/bin/activate
```

**Для Windows:**
```
# Создание виртуального окружения (предполагается, что Python 3.10 установлен)
python -m venv venv
venv\Scripts\activate
```

3. Установите зависимости:
```
pip install -r requirements.txt
```

4. Создайте файл .env на основе .env.example и заполните его своими данными:
```
cp .env.example .env
```

### Настройка MongoDB

Рекомендуется использовать MongoDB Atlas:

1. Зарегистрируйтесь на [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. Создайте бесплатный кластер M0
3. Настройте пользователя и пароль для доступа
4. Получите строку подключения и обновите MONGODB_URI в файле .env

### Настройка бота

1. Получите токен бота через [@BotFather](https://t.me/BotFather)
2. Создайте приватный канал и добавьте бота в качестве администратора
3. Узнайте ID канала (добавьте в канал бота @username_to_id_bot или @getidsbot)
4. Укажите ID канала в файле .env
5. Укажите ID администраторов в файле .env (получить ID можно через [@userinfobot](https://t.me/userinfobot))

## Запуск

Запустите бота:
```
python -m bot.main
```

## Использование

### Команды для администраторов

- `/admin` - доступ к панели управления
- `📊 Статистика` - показать статистику по пользователям и источникам
- `🔗 Создать ссылку` - создать новую пригласительную ссылку
- `📨 Создать рассылку` - отправить сообщение всем пользователям

### Команды для пользователей

- `/start` - начать взаимодействие с ботом
- `/help` - показать справку
- `/about` - информация о канале

## Структура проекта

```
/bot
  /config         # Конфигурационные файлы
  /database       # Модули для работы с базой данных
  /handlers       # Обработчики команд и событий
  /services       # Бизнес-логика
  /utils          # Вспомогательные функции
  main.py         # Основной файл для запуска
```

## Возможные проблемы и их решения

### Проблемы с установкой aiohttp на Python 3.13

Если у вас возникают ошибки при установке зависимостей на Python 3.13, рекомендуется использовать Python 3.10 или 3.11:

```bash
# Создайте виртуальное окружение с Python 3.10
python3.10 -m venv venv_py310
source venv_py310/bin/activate
pip install -r requirements.txt
```

### Проблемы с подключением к MongoDB Atlas

Убедитесь, что:
1. IP вашего сервера добавлен в список разрешенных в MongoDB Atlas
2. Учетные данные (логин/пароль) указаны правильно
3. Строка подключения содержит правильное имя кластера

## Лицензия

MIT

## Авторы

Ваше имя / контакты