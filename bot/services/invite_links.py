"""
Сервис для работы с открытым каналом
"""

import logging
from bot.config.config import CHANNEL_USERNAME

def get_channel_link():
    """
    Получение ссылки на открытый канал
    
    Returns:
        str: Ссылка на канал или None, если не настроен
    """
    if CHANNEL_USERNAME:
        # Убираем @ если есть
        username = CHANNEL_USERNAME.lstrip('@')
        return f"https://t.me/{username}"
    return None

def get_channel_username():
    """
    Получение username канала
    
    Returns:
        str: Username канала или None, если не настроен
    """
    return CHANNEL_USERNAME 