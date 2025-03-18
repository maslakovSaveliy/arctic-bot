"""
Сервис для отправки уведомлений и рассылок
"""

import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.utils.exceptions import BotBlocked, UserDeactivated, ChatNotFound, Unauthorized, CantInitiateConversation

from bot.database import get_all_users, get_users_by_filter
from bot.config.config import BROADCASTS_COLLECTION
from bot.database.db import get_db

async def send_welcome_message(user_id, message_text):
    """
    Отправка приветственного сообщения пользователю
    
    Args:
        user_id (int): ID пользователя
        message_text (str): Текст сообщения
        
    Returns:
        bool: True если сообщение отправлено успешно, иначе False
    """
    from bot.main import bot  # Импортируем здесь, чтобы избежать цикличного импорта
    
    try:
        await bot.send_message(chat_id=user_id, text=message_text)
        logging.info(f"Приветственное сообщение отправлено пользователю {user_id}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного сообщения пользователю {user_id}: {e}")
        return False

async def send_broadcast(bot: Bot, message_text, target_filter=None, save_to_db=True):
    """
    Отправка рассылки пользователям
    
    Args:
        bot (Bot): Экземпляр бота
        message_text (str): Текст сообщения
        target_filter (dict, optional): Фильтр для выбора целевых пользователей
        save_to_db (bool, optional): Сохранять ли рассылку в базу данных
        
    Returns:
        dict: Статистика по отправке сообщений
    """
    # Получаем всех пользователей, независимо от статуса
    if target_filter:
        users = await get_users_by_filter(target_filter)
    else:
        users = await get_all_users()
    
    logging.info(f"Начинаем рассылку: найдено {len(users)} пользователей для отправки")
    
    # Создаем запись о рассылке в базе данных
    broadcast_id = None
    if save_to_db:
        db = get_db()
        broadcast_data = {
            "message_text": message_text,
            "target_filter": target_filter,
            "total_users": len(users),
            "created_at": datetime.utcnow(),
            "status": "in_progress",
            "sent_count": 0,
            "failed_count": 0
        }
        result = await db[BROADCASTS_COLLECTION].insert_one(broadcast_data)
        broadcast_id = result.inserted_id
    
    # Счетчики для статистики
    sent_count = 0
    failed_count = 0
    errors_by_type = {}
    
    # Отправляем сообщения пользователям
    for user in users:
        try:
            await bot.send_message(
                chat_id=user["user_id"],
                text=message_text
            )
            sent_count += 1
            logging.info(f"Сообщение успешно отправлено пользователю {user['user_id']}")
            
            # Обновляем статистику в базе данных
            if save_to_db and broadcast_id:
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast_id},
                    {"$inc": {"sent_count": 1}}
                )
            
            # Небольшая задержка между отправками, чтобы не превысить лимиты API
            await asyncio.sleep(0.05)
        
        except (BotBlocked, UserDeactivated, ChatNotFound, Unauthorized, CantInitiateConversation) as e:
            # Специфические ошибки Telegram API
            error_type = type(e).__name__
            if error_type not in errors_by_type:
                errors_by_type[error_type] = 0
            errors_by_type[error_type] += 1
            
            failed_count += 1
            logging.error(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
            
            # Обновляем статистику в базе данных
            if save_to_db and broadcast_id:
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast_id},
                    {"$inc": {"failed_count": 1}}
                )
        
        except Exception as e:
            # Общие ошибки
            error_type = type(e).__name__
            if error_type not in errors_by_type:
                errors_by_type[error_type] = 0
            errors_by_type[error_type] += 1
            
            failed_count += 1
            logging.error(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
            
            # Обновляем статистику в базе данных
            if save_to_db and broadcast_id:
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast_id},
                    {"$inc": {"failed_count": 1}}
                )
    
    # Обновляем статус рассылки в базе данных
    if save_to_db and broadcast_id:
        await db[BROADCASTS_COLLECTION].update_one(
            {"_id": broadcast_id},
            {"$set": {"status": "completed"}}
        )
    
    # Возвращаем статистику
    stats = {
        "total": len(users),
        "sent": sent_count,
        "failed": failed_count
    }
    
    logging.info(f"Рассылка завершена. Статистика: {stats}")
    return stats

async def schedule_broadcast(bot: Bot, message_text, schedule_time, target_filter=None):
    """
    Планирование отложенной рассылки
    
    Args:
        bot (Bot): Экземпляр бота
        message_text (str): Текст сообщения
        schedule_time (datetime): Время отправки
        target_filter (dict, optional): Фильтр для выбора целевых пользователей
        
    Returns:
        str: ID запланированной рассылки
    """
    db = get_db()
    
    # Создаем запись о рассылке в базе данных
    broadcast_data = {
        "message_text": message_text,
        "target_filter": target_filter,
        "created_at": datetime.utcnow(),
        "schedule_time": schedule_time,
        "status": "scheduled",
        "sent_count": 0,
        "failed_count": 0
    }
    
    result = await db[BROADCASTS_COLLECTION].insert_one(broadcast_data)
    broadcast_id = result.inserted_id
    
    logging.info(f"Рассылка запланирована на {schedule_time.isoformat()}, ID: {broadcast_id}")
    return str(broadcast_id) 