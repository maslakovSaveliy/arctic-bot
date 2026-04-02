"""
Основные функции для работы с MongoDB
"""

import logging
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure

from bot.config.config import (
    MONGODB_URI,
    MONGODB_DB_NAME,
    USERS_COLLECTION,
    BROADCASTS_COLLECTION,
    CONTESTS_COLLECTION,
    CONTEST_PARTICIPANTS_COLLECTION,
    INVITE_LINKS_COLLECTION,
)

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

        await _ensure_indexes(_db)
        
        return _db
    except ConnectionFailure as e:
        logging.error(f"Не удалось подключиться к MongoDB: {e}")
        raise

async def _ensure_indexes(db) -> None:
    """Создание индексов для всех коллекций (idempotent)."""
    await db[USERS_COLLECTION].create_index("user_id", unique=True)
    await db[USERS_COLLECTION].create_index("status")
    await db[USERS_COLLECTION].create_index([("status", 1), ("source", 1)])
    await db[USERS_COLLECTION].create_index([("status", 1), ("city", 1)])

    await db[BROADCASTS_COLLECTION].create_index([("status", 1), ("schedule_time", 1)])

    await db[CONTEST_PARTICIPANTS_COLLECTION].create_index(
        [("contest_id", 1), ("user_id", 1)], unique=True
    )
    await db[CONTESTS_COLLECTION].create_index("contest_id", unique=True)

    await db[INVITE_LINKS_COLLECTION].create_index("link_id", unique=True)

    logging.info("Индексы MongoDB созданы/проверены")


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