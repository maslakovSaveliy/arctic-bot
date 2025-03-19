"""
Модуль для работы с пользователями в базе данных
"""

import logging
from datetime import datetime
from bot.database.db import get_db
from bot.config.config import USERS_COLLECTION

async def add_user(user_id, username=None, first_name=None, last_name=None, source=None, status="pending"):
    """
    Добавление нового пользователя в базу данных или обновление существующего
    
    Args:
        user_id (int): Telegram ID пользователя
        username (str, optional): Имя пользователя в Telegram
        first_name (str, optional): Имя пользователя
        last_name (str, optional): Фамилия пользователя
        source (str, optional): Источник, откуда пришел пользователь
        status (str, optional): Статус пользователя (pending, active, blocked)
        
    Returns:
        dict: Данные добавленного/обновленного пользователя
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    
    now = datetime.utcnow()
    
    # Проверяем, существует ли пользователь
    existing_user = await collection.find_one({"user_id": user_id})
    
    if existing_user:
        # Обновляем существующего пользователя
        update_data = {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "updated_at": now
            }
        }
        
        # Обновляем статус только если он не был активным
        if existing_user.get("status") != "active" and status == "active":
            update_data["$set"]["status"] = status
            update_data["$set"]["activated_at"] = now
            
        # Если источник не был указан ранее и указан сейчас
        if not existing_user.get("source") and source:
            update_data["$set"]["source"] = source
            
        await collection.update_one({"user_id": user_id}, update_data)
        updated_user = await collection.find_one({"user_id": user_id})
        logging.info(f"Пользователь обновлен: {user_id}")
        return updated_user
    else:
        # Добавляем нового пользователя
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "source": source,
            "status": status,
            "created_at": now,
            "updated_at": now
        }
        
        if status == "active":
            user_data["activated_at"] = now
            
        result = await collection.insert_one(user_data)
        logging.info(f"Новый пользователь добавлен: {user_id}")
        return user_data

async def get_user(user_id):
    """
    Получение данных пользователя по его Telegram ID
    
    Args:
        user_id (int): Telegram ID пользователя
        
    Returns:
        dict: Данные пользователя или None, если пользователь не найден
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    return await collection.find_one({"user_id": user_id})

async def update_user(user_id, update_data):
    """
    Обновление данных пользователя
    
    Args:
        user_id (int): Telegram ID пользователя
        update_data (dict): Данные для обновления
        
    Returns:
        bool: True если обновление выполнено успешно, иначе False
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    
    # Добавляем дату обновления
    update_data["updated_at"] = datetime.utcnow()
    
    # Если устанавливается статус active, добавляем дату активации
    if update_data.get("status") == "active":
        update_data["activated_at"] = datetime.utcnow()
    
    result = await collection.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    return result.modified_count > 0

async def get_all_users(status=None, limit=None, skip=0):
    """
    Получение списка всех пользователей с возможностью фильтрации по статусу
    
    Args:
        status (str, optional): Статус пользователей для фильтрации
        limit (int, optional): Ограничение количества результатов
        skip (int, optional): Сколько пользователей пропустить (для пагинации)
        
    Returns:
        list: Список пользователей
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    
    query = {}
    if status:
        query["status"] = status
    
    cursor = collection.find(query).skip(skip)
    
    if limit:
        cursor = cursor.limit(limit)
    
    users = await cursor.to_list(length=None)
    logging.info(f"Получено {len(users)} пользователей из базы данных. Фильтр по статусу: {status}")
    
    # Подробное логирование нескольких первых пользователей для диагностики
    if users:
        sample_size = min(3, len(users))
        for i in range(sample_size):
            user = users[i]
            user_id = user.get('user_id', 'не указан')
            status = user.get('status', 'не указан')
            logging.info(f"Пользователь [{i+1}/{sample_size}]: ID={user_id}, статус={status}")
    
    return users

async def get_users_by_filter(filter_query, limit=None, skip=0):
    """
    Получение пользователей по произвольному фильтру
    
    Args:
        filter_query (dict): Фильтр для поиска пользователей
        limit (int, optional): Ограничение количества результатов
        skip (int, optional): Сколько пользователей пропустить (для пагинации)
        
    Returns:
        list: Список пользователей, соответствующих фильтру
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    
    logging.info(f"Поиск пользователей по фильтру: {filter_query}")
    
    cursor = collection.find(filter_query).skip(skip)
    
    if limit:
        cursor = cursor.limit(limit)
    
    result = await cursor.to_list(length=None)
    logging.info(f"Найдено {len(result)} пользователей по фильтру")
    
    return result

async def update_user_status(user_id, status, reason=None):
    """
    Обновление статуса пользователя с указанием причины
    
    Args:
        user_id (int): Telegram ID пользователя
        status (str): Новый статус пользователя (active, inactive, blocked)
        reason (str, optional): Причина изменения статуса
        
    Returns:
        bool: True если обновление выполнено успешно, иначе False
    """
    db = get_db()
    collection = db[USERS_COLLECTION]
    
    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }
    
    # Добавляем причину изменения статуса, если она указана
    if reason:
        update_data["status_reason"] = reason
    
    # Если устанавливается статус active, добавляем дату активации
    if status == "active":
        update_data["activated_at"] = datetime.utcnow()
    
    # Если устанавливается статус inactive, добавляем дату деактивации
    if status == "inactive":
        update_data["deactivated_at"] = datetime.utcnow()
    
    result = await collection.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    logging.info(f"Статус пользователя {user_id} изменен на {status}" + (f" (Причина: {reason})" if reason else ""))
    return result.modified_count > 0 