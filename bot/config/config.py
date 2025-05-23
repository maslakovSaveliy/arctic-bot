import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Telegram API конфигурация
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_USER_IDS = [int(user_id) for user_id in os.getenv("ADMIN_USER_IDS", "").split(",") if user_id]

# MongoDB конфигурация
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "telegram_bot")

# Настройки бота
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DEFAULT_WELCOME_MESSAGE = os.getenv(
    "DEFAULT_WELCOME_MESSAGE", 
    "Добро пожаловать в наш канал! Ваша заявка на подписку была одобрена."
)

# Коллекции в базе данных
USERS_COLLECTION = "users"
INVITE_LINKS_COLLECTION = "invite_links"
BROADCASTS_COLLECTION = "broadcasts"

# SMTP конфигурация
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_TO_EMAIL = os.getenv('SMTP_TO_EMAIL')
SMTP_SUBJECT = os.getenv('SMTP_SUBJECT', 'Новый запрос на консультацию') 