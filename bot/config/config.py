import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Telegram API конфигурация
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # @username канала для открытого канала
ADMIN_USER_IDS = [int(user_id) for user_id in os.getenv("ADMIN_USER_IDS", "").split(",") if user_id]

# MongoDB конфигурация
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "telegram_bot")

# Настройки бота
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DEFAULT_WELCOME_MESSAGE = os.getenv(
    "DEFAULT_WELCOME_MESSAGE", 
    "Добро пожаловать в наш канал! Вы успешно подписались."
)

# Коллекции в базе данных
USERS_COLLECTION = "users"
INVITE_LINKS_COLLECTION = "invite_links"
BROADCASTS_COLLECTION = "broadcasts"
CONTESTS_COLLECTION = "contests"
CONTEST_PARTICIPANTS_COLLECTION = "contest_participants"

# Антифрод
MIN_ACCOUNT_AGE_DAYS = 0
MAX_USER_ID = 7_000_000_000

# SMTP конфигурация
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_TO_EMAIL = os.getenv('SMTP_TO_EMAIL', 'feedback@arctictrucks.ru')
SMTP_SUBJECT = os.getenv('SMTP_SUBJECT', 'Заявки квиз') 