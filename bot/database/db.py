"""
Основные функции для работы с MongoDB
"""

import logging
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure

from bot.config.config import MONGODB_URI, MONGODB_DB_NAME

# Глобальная переменная для хранения подключения к базе данных
_db_client = None
_db = None

async def init_db():
    """
    Инициализация подключения к базе данных MongoDB
    """
    global _db_client, _db
    try:
        _db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        _db = _db_client[MONGODB_DB_NAME]
        
        # Проверка соединения
        await _db_client.admin.command('ping')
        logging.info(f"Подключение к MongoDB успешно установлено (БД: {MONGODB_DB_NAME})")
        
        return _db
    except ConnectionFailure as e:
        logging.error(f"Не удалось подключиться к MongoDB: {e}")
        raise

def get_db():
    """
    Получение экземпляра базы данных
    """
    global _db
    if _db is None:
        raise ConnectionError("База данных не инициализирована. Вызовите init_db() перед использованием.")
    return _db

async def close_db_connection():
    """
    Закрытие соединения с базой данных
    """
    global _db_client
    if _db_client:
        _db_client.close()
        logging.info("Соединение с MongoDB закрыто") 