"""
Модуль для работы с пригласительными ссылками в базе данных
"""

import logging
from datetime import datetime
from bot.database.db import get_db
from bot.config.config import INVITE_LINKS_COLLECTION

async def create_invite_link(link, source, created_by, description=None, max_uses=None, expires_at=None):
    """
    Создание новой пригласительной ссылки
    
    Args:
        link (str): Пригласительная ссылка
        source (str): Источник ссылки (название рекламного канала, соцсети и т.д.)
        created_by (int): ID пользователя, создавшего ссылку
        description (str, optional): Описание ссылки
        max_uses (int, optional): Максимальное количество использований
        expires_at (datetime, optional): Дата истечения срока действия
        
    Returns:
        dict: Данные созданной ссылки
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    
    now = datetime.utcnow()
    
    link_data = {
        "link": link,
        "source": source,
        "created_by": created_by,
        "description": description,
        "max_uses": max_uses,
        "expires_at": expires_at,
        "created_at": now,
        "updated_at": now,
        "uses_count": 0,
        "is_active": True
    }
    
    result = await collection.insert_one(link_data)
    logging.info(f"Создана новая пригласительная ссылка: {link} (источник: {source})")
    return link_data

async def get_invite_link(link):
    """
    Получение данных о пригласительной ссылке
    
    Args:
        link (str): Пригласительная ссылка
        
    Returns:
        dict: Данные о ссылке или None, если ссылка не найдена
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    return await collection.find_one({"link": link})

async def get_source_by_link(link):
    """
    Получение источника по пригласительной ссылке
    
    Args:
        link (str): Пригласительная ссылка
        
    Returns:
        str: Источник ссылки или None, если ссылка не найдена
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    link_data = await collection.find_one({"link": link})
    
    if link_data:
        # Увеличиваем счетчик использований
        await collection.update_one(
            {"_id": link_data["_id"]},
            {"$inc": {"uses_count": 1}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return link_data.get("source")
    
    return None

async def update_invite_link(link, update_data):
    """
    Обновление данных о пригласительной ссылке
    
    Args:
        link (str): Пригласительная ссылка
        update_data (dict): Данные для обновления
        
    Returns:
        bool: True если обновление выполнено успешно, иначе False
    """
    db = get_db()
    collection = db[INVITE_LINKS_COLLECTION]
    
    # Добавляем дату обновления
    update_data["updated_at"] = datetime.utcnow()
    
    result = await collection.update_one(
        {"link": link},
        {"$set": update_data}
    )
    
    return result.modified_count > 0

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