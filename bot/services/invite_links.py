"""
Сервис для управления пригласительными ссылками
"""

import logging
from datetime import datetime, timedelta

from bot.database import create_invite_link
from bot.config.config import CHANNEL_ID

async def generate_invite_link(bot, source, created_by, expire_date=None, member_limit=None, description=None):
    """
    Генерация новой пригласительной ссылки
    
    Args:
        bot: Экземпляр бота
        source (str): Источник ссылки (название рекламного канала, соцсети и т.д.)
        created_by (int): ID пользователя, создавшего ссылку
        expire_date (datetime, optional): Дата истечения срока действия
        member_limit (int, optional): Максимальное количество использований
        description (str, optional): Описание ссылки
        
    Returns:
        dict: Данные созданной ссылки
    """
    try:
        # Для ссылок, требующих одобрения администратора (creates_join_request=True),
        # нельзя устанавливать ограничение на количество участников (member_limit)
        creates_join_request = True
        
        # Создаем пригласительную ссылку через Telegram API
        chat_invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            expire_date=expire_date,
            # Если creates_join_request=True, не передаем member_limit
            member_limit=None if creates_join_request else member_limit,
            creates_join_request=creates_join_request,  # Создаем ссылку, которая требует одобрения
            name=source if source else None  # Название ссылки (работает только в Bot API 6.0+)
        )
        
        logging.info(f"Сгенерирована новая пригласительная ссылка: {chat_invite_link.invite_link} (источник: {source})")
        
        # Сохраняем ссылку в базу данных
        link_data = await create_invite_link(
            link=chat_invite_link.invite_link,
            source=source,
            created_by=created_by,
            description=description,
            max_uses=member_limit,
            expires_at=expire_date
        )
        
        return {
            "invite_link": chat_invite_link.invite_link,
            "source": source,
            "expires_at": expire_date.isoformat() if expire_date else None,
            "member_limit": member_limit,
            "description": description
        }
        
    except Exception as e:
        logging.error(f"Ошибка при генерации пригласительной ссылки: {e}")
        raise 