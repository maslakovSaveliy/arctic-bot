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
    # Проверяем, что бот правильно передан
    logging.info(f"Экземпляр бота для рассылки: {bot}")
    
    # Получаем всех пользователей, независимо от статуса
    if target_filter:
        # Всегда добавляем фильтр по статусу "active", если он не указан явно
        combined_filter = target_filter.copy() if isinstance(target_filter, dict) else {}
        if "status" not in combined_filter:
            combined_filter["status"] = "active"
        
        users = await get_users_by_filter(combined_filter)
        logging.info(f"Получены пользователи по фильтру: {combined_filter}, найдено {len(users)} пользователей")
    else:
        # По умолчанию получаем только активных пользователей
        users = await get_all_users(status="active")
        logging.info(f"Получены все активные пользователи, найдено {len(users)} пользователей")
    
    if not users:
        logging.warning("Не найдено пользователей для рассылки!")
        return {"total": 0, "sent": 0, "failed": 0}
    
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
        logging.info(f"Создана запись о рассылке в базе данных, ID: {broadcast_id}")
    
    # Счетчики для статистики
    sent_count = 0
    failed_count = 0
    errors_by_type = {}
    
    # Отправляем сообщения пользователям
    for user in users:
        user_id = user.get("user_id")
        if not user_id:
            logging.warning(f"Пользователь без ID: {user}")
            failed_count += 1
            continue
            
        try:
            logging.info(f"Отправка сообщения пользователю {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            sent_count += 1
            logging.info(f"Сообщение успешно отправлено пользователю {user_id}")
            
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
            logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
            
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
            logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
            
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
        "failed": failed_count,
        "errors": errors_by_type if errors_by_type else None
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
    
    # Проверяем, имеет ли время часовой пояс
    if schedule_time.tzinfo is None:
        # Если время без часового пояса, предполагаем, что это локальное время
        # и приводим его к UTC для хранения в базе данных
        import pytz
        
        # Получаем локальный часовой пояс
        local_tz = pytz.timezone('Europe/Moscow')  # Можно заменить на нужный часовой пояс
        
        # Локализуем время
        localized_time = local_tz.localize(schedule_time)
        
        # Конвертируем в UTC
        utc_time = localized_time.astimezone(pytz.UTC)
        
        # Используем UTC время для сохранения (без информации о часовом поясе)
        schedule_time = utc_time.replace(tzinfo=None)
        
        logging.info(f"Время рассылки преобразовано из локального {localized_time.isoformat()} в UTC {schedule_time.isoformat()}")
    
    # Получаем количество потенциальных получателей
    combined_filter = target_filter.copy() if isinstance(target_filter, dict) else {}
    if "status" not in combined_filter:
        combined_filter["status"] = "active"
        
    users = await get_users_by_filter(combined_filter)
    total_users = len(users)
    
    logging.info(f"Запланированная рассылка будет отправлена {total_users} пользователям с фильтром {combined_filter}")
    
    # Создаем запись о рассылке в базе данных
    broadcast_data = {
        "message_text": message_text,
        "target_filter": combined_filter,  # Сохраняем комбинированный фильтр
        "created_at": datetime.utcnow(),
        "schedule_time": schedule_time,
        "status": "scheduled",
        "sent_count": 0,
        "failed_count": 0,
        "total_users": total_users
    }
    
    result = await db[BROADCASTS_COLLECTION].insert_one(broadcast_data)
    broadcast_id = result.inserted_id
    
    logging.info(f"Рассылка запланирована на {schedule_time.isoformat()} UTC, ID: {broadcast_id}")
    return str(broadcast_id)

async def check_scheduled_broadcasts(bot: Bot):
    """
    Проверка и запуск запланированных рассылок
    
    Args:
        bot (Bot): Экземпляр бота
    """
    db = get_db()
    
    # Ищем все запланированные рассылки, время которых уже наступило
    current_time = datetime.utcnow()
    query = {
        "status": "scheduled",
        "schedule_time": {"$lte": current_time}
    }
    
    scheduled_broadcasts = await db[BROADCASTS_COLLECTION].find(query).to_list(length=None)
    
    for broadcast in scheduled_broadcasts:
        logging.info(f"Запуск запланированной рассылки ID: {broadcast['_id']}")
        
        # Обновляем статус рассылки
        await db[BROADCASTS_COLLECTION].update_one(
            {"_id": broadcast["_id"]},
            {"$set": {"status": "in_progress"}}
        )
        
        # Запускаем рассылку
        try:
            stats = await send_broadcast(
                bot=bot,
                message_text=broadcast["message_text"],
                target_filter=broadcast.get("target_filter"),
                save_to_db=False  # Не создаем новую запись, так как она уже существует
            )
            
            # Обновляем статистику и статус
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast["_id"]},
                {"$set": {
                    "status": "completed",
                    "sent_count": stats["sent"],
                    "failed_count": stats["failed"],
                    "completed_at": datetime.utcnow()
                }}
            )
            logging.info(f"Запланированная рассылка выполнена, ID: {broadcast['_id']}")
        
        except Exception as e:
            # В случае ошибки помечаем рассылку как неудачную
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast["_id"]},
                {"$set": {
                    "status": "failed",
                    "error": str(e)
                }}
            )
            logging.error(f"Ошибка при выполнении запланированной рассылки {broadcast['_id']}: {e}")

async def start_broadcast_scheduler(bot: Bot):
    """
    Запуск планировщика рассылок
    
    Args:
        bot (Bot): Экземпляр бота
    """
    while True:
        try:
            await check_scheduled_broadcasts(bot)
        except Exception as e:
            logging.error(f"Ошибка в планировщике рассылок: {e}")
        
        # Проверяем каждую минуту
        await asyncio.sleep(60) 