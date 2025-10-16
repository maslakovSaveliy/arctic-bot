"""
Модуль для работы с пригласительными ссылками в базе данных
"""

import logging
import uuid
from datetime import datetime
from bot.database.db import get_db
from bot.config.config import INVITE_LINKS_COLLECTION, CHANNEL_USERNAME

async def create_invite_link(source, created_by, description=None, expire_date=None):
    """
    Создание новой пригласительной ссылки для открытого канала
    
    Args:
        source (str): Источник ссылки (название рекламного канала, соцсети и т.д.)
        created_by (int): ID пользователя, создавшего ссылку
        description (str, optional): Описание ссылки
        expire_date (datetime, optional): Дата истечения срока действия
        
    Returns:
        dict: Данные созданной ссылки
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    
    now = datetime.utcnow()
    
    # Генерируем уникальный ID для ссылки
    link_id = str(uuid.uuid4())[:8]  # Короткий уникальный ID
    
    # Формируем ссылку с параметром start
    if CHANNEL_USERNAME:
        username = CHANNEL_USERNAME.lstrip('@')
        invite_link = f"https://t.me/{username}?start=link_{link_id}"
    else:
        invite_link = f"https://t.me/your_channel?start=link_{link_id}"
    
    link_data = {
        "link_id": link_id,
        "invite_link": invite_link,
        "source": source,
        "created_by": created_by,
        "description": description,
        "expire_date": expire_date,
        "created_at": now,
        "updated_at": now,
        "uses_count": 0,
        "is_active": True
    }
    
    result = await collection.insert_one(link_data)
    logging.info(f"Создана новая пригласительная ссылка: {invite_link} (источник: {source})")
    return link_data

async def get_invite_link(link_id):
    """
    Получение данных о пригласительной ссылке по ID
    
    Args:
        link_id (str): ID ссылки
        
    Returns:
        dict: Данные о ссылке или None, если ссылка не найдена
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    return await collection.find_one({"link_id": link_id})

async def get_source_by_link(link_id):
    """
    Получение источника по ID ссылки и увеличение счетчика использований
    
    Args:
        link_id (str): ID ссылки
        
    Returns:
        str: Источник ссылки или None, если ссылка не найдена
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    link_data = await collection.find_one({"link_id": link_id})
    
    if link_data:
        # Увеличиваем счетчик использований
        await collection.update_one(
            {"_id": link_data["_id"]},
            {"$inc": {"uses_count": 1}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return link_data.get("source")
    
    return None

async def get_all_invite_links(is_active=None, source=None, limit=None, skip=0):
    """
    Получение списка всех пригласительных ссылок с возможностью фильтрации
    
    Args:
        is_active (bool, optional): Фильтр по активности ссылки
        source (str, optional): Фильтр по источнику
        limit (int, optional): Ограничение количества результатов
        skip (int, optional): Сколько ссылок пропустить (для пагинации)
        
    Returns:
        list: Список пригласительных ссылок
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    if source:
        query["source"] = source
    
    cursor = collection.find(query).skip(skip)
    
    if limit:
        cursor = cursor.limit(limit)
    
    return await cursor.to_list(length=None)