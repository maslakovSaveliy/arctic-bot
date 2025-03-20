"""
Сервис для отправки уведомлений и рассылок
"""

import logging
import asyncio
import math
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import InputFile, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from aiogram.utils.exceptions import BotBlocked, UserDeactivated, ChatNotFound, Unauthorized, CantInitiateConversation, RetryAfter, TelegramAPIError

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

async def send_broadcast(bot: Bot, message_text, target_filter=None, save_to_db=True, batch_size=None, batch_delay=None, media=None, media_type=None):
    """
    Отправка рассылки пользователям
    
    Args:
        bot (Bot): Экземпляр бота
        message_text (str): Текст сообщения
        target_filter (dict, optional): Фильтр для выбора целевых пользователей
        save_to_db (bool, optional): Сохранять ли рассылку в базу данных
        batch_size (int, optional): Размер пакета сообщений для отправки (по умолчанию 25)
        batch_delay (int, optional): Задержка между пакетами в секундах (по умолчанию 3)
        media (str, optional): Путь или file_id медиа-файла для отправки вместе с сообщением
        media_type (str, optional): Тип медиа: "photo", "video", "animation" (gif)
        
    Returns:
        dict: Статистика по отправке сообщений
    """
    # Настройки для безопасной отправки сообщений
    SAFE_MESSAGE_DELAY = 0.4  # 400 мс между сообщениями (макс. 30 сообщений в сек. по лимитам TG)
    DEFAULT_BATCH_SIZE = 25   # Количество сообщений в одном пакете
    DEFAULT_BATCH_DELAY = 3   # Задержка между пакетами в секундах

    # Используем значения по умолчанию, если не указаны
    batch_size = batch_size or DEFAULT_BATCH_SIZE
    batch_delay = batch_delay or DEFAULT_BATCH_DELAY
    
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
    db = get_db()
    if save_to_db:
        broadcast_data = {
            "message_text": message_text,
            "target_filter": target_filter,
            "total_users": len(users),
            "created_at": datetime.utcnow(),
            "status": "in_progress",
            "sent_count": 0,
            "failed_count": 0
        }
        
        # Если есть медиа, сохраняем информацию о нем
        if media and media_type:
            broadcast_data["media"] = media
            broadcast_data["media_type"] = media_type
            
        result = await db[BROADCASTS_COLLECTION].insert_one(broadcast_data)
        broadcast_id = result.inserted_id
        logging.info(f"Создана запись о рассылке в базе данных, ID: {broadcast_id}")
    
    # Счетчики для статистики
    sent_count = 0
    failed_count = 0
    errors_by_type = {}
    
    # Разделяем пользователей на пакеты для отправки
    total_users = len(users)
    total_batches = math.ceil(total_users / batch_size)
    logging.info(f"Рассылка будет отправлена в {total_batches} пакетах по {batch_size} сообщений")
    
    # Расчет примерного времени завершения
    estimated_time_seconds = total_batches * batch_delay + total_users * SAFE_MESSAGE_DELAY
    estimated_completion_time = datetime.utcnow() + timedelta(seconds=estimated_time_seconds)
    logging.info(f"Примерное время завершения рассылки: {estimated_completion_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Информация о медиа-контенте
    has_media = media is not None and media_type is not None
    if has_media:
        logging.info(f"Рассылка содержит медиа-контент типа: {media_type}, значение: {media}")
    
    for batch_index in range(total_batches):
        start_idx = batch_index * batch_size
        end_idx = min(start_idx + batch_size, total_users)
        current_batch = users[start_idx:end_idx]
        
        logging.info(f"Отправка пакета {batch_index + 1}/{total_batches} ({len(current_batch)} пользователей)")
        
        for user in current_batch:
            user_id = user.get("user_id")
            if not user_id:
                logging.warning(f"Пользователь без ID: {user}")
                failed_count += 1
                continue
                
            try:
                logging.info(f"Отправка сообщения пользователю {user_id}")
                
                # В зависимости от наличия и типа медиа-контента выбираем метод отправки
                if not has_media:
                    # Отправка только текста
                    await bot.send_message(
                        chat_id=user_id,
                        text=message_text
                    )
                else:
                    # Отправка сообщения с медиа-контентом
                    if media_type == "photo":
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=media,
                            caption=message_text
                        )
                    elif media_type == "video":
                        await bot.send_video(
                            chat_id=user_id,
                            video=media,
                            caption=message_text
                        )
                    elif media_type == "animation":
                        await bot.send_animation(
                            chat_id=user_id,
                            animation=media,
                            caption=message_text
                        )
                    else:
                        # Если неизвестный тип медиа, отправляем только текст
                        logging.warning(f"Неизвестный тип медиа: {media_type}, отправляем только текст")
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
                
                # Увеличенная задержка между отправками для соблюдения лимитов API
                await asyncio.sleep(SAFE_MESSAGE_DELAY)
            
            except RetryAfter as e:
                # Обработка ошибки превышения лимитов
                retry_after = e.timeout
                logging.warning(f"Превышен лимит запросов к API, ожидание {retry_after} секунд")
                
                # Увеличиваем задержку на будущее
                SAFE_MESSAGE_DELAY = max(SAFE_MESSAGE_DELAY, retry_after / batch_size + 0.1)
                
                # Ожидаем указанное время и повторяем попытку
                await asyncio.sleep(retry_after)
                try:
                    # Повторяем отправку
                    if not has_media:
                        await bot.send_message(chat_id=user_id, text=message_text)
                    else:
                        if media_type == "photo":
                            await bot.send_photo(chat_id=user_id, photo=media, caption=message_text)
                        elif media_type == "video":
                            await bot.send_video(chat_id=user_id, video=media, caption=message_text)
                        elif media_type == "animation":
                            await bot.send_animation(chat_id=user_id, animation=media, caption=message_text)
                        else:
                            await bot.send_message(chat_id=user_id, text=message_text)
                            
                    sent_count += 1
                    
                    if save_to_db and broadcast_id:
                        await db[BROADCASTS_COLLECTION].update_one(
                            {"_id": broadcast_id},
                            {"$inc": {"sent_count": 1}}
                        )
                except Exception as e2:
                    failed_count += 1
                    logging.error(f"Повторная ошибка при отправке сообщения пользователю {user_id}: {e2}")
                    
                    if save_to_db and broadcast_id:
                        await db[BROADCASTS_COLLECTION].update_one(
                            {"_id": broadcast_id},
                            {"$inc": {"failed_count": 1}}
                        )
            
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
            
            except TelegramAPIError as e:
                # Другие ошибки API Telegram
                error_type = "TelegramAPIError"
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = 0
                errors_by_type[error_type] += 1
                
                failed_count += 1
                logging.error(f"Ошибка API Telegram при отправке пользователю {user_id}: {e}")
                
                if save_to_db and broadcast_id:
                    await db[BROADCASTS_COLLECTION].update_one(
                        {"_id": broadcast_id},
                        {"$inc": {"failed_count": 1}}
                    )
                
                # Делаем небольшую паузу при ошибках API
                await asyncio.sleep(1)
            
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
        
        # Задержка между пакетами отправки
        if batch_index < total_batches - 1:  # Не делаем задержку после последнего пакета
            logging.info(f"Завершен пакет {batch_index + 1}/{total_batches}. Ожидание {batch_delay} секунд перед следующим пакетом")
            await asyncio.sleep(batch_delay)
    
    # Обновляем статус рассылки в базе данных
    if save_to_db and broadcast_id:
        await db[BROADCASTS_COLLECTION].update_one(
            {"_id": broadcast_id},
            {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
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

async def schedule_broadcast(bot: Bot, message_text, schedule_time, target_filter=None, media=None, media_type=None):
    """
    Планирование отложенной рассылки
    
    Args:
        bot (Bot): Экземпляр бота
        message_text (str): Текст сообщения
        schedule_time (datetime): Время отправки
        target_filter (dict, optional): Фильтр для выбора целевых пользователей
        media (str, optional): Путь или file_id медиа-файла для отправки вместе с сообщением
        media_type (str, optional): Тип медиа: "photo", "video", "animation" (gif)
        
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
    
    # Если есть медиа, сохраняем информацию о нем
    if media and media_type:
        broadcast_data["media"] = media
        broadcast_data["media_type"] = media_type
        logging.info(f"Запланирована рассылка с медиа-контентом типа: {media_type}")
    
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
    
    # Логируем все запланированные рассылки для отладки
    import pytz
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.utcnow()
    
    # Получаем все запланированные рассылки для информации
    all_scheduled = await db[BROADCASTS_COLLECTION].find({"status": "scheduled"}).to_list(length=None)
    
    if all_scheduled:
        logging.info(f"Всего запланированных рассылок в базе: {len(all_scheduled)}")
        for bc in all_scheduled:
            bc_time = bc.get('schedule_time', 'не указано')
            if isinstance(bc_time, datetime):
                # Конвертируем UTC время рассылки в московское для информативности
                bc_time_moscow = bc_time.replace(tzinfo=pytz.UTC).astimezone(moscow_tz)
                bc_time_str = f"{bc_time} UTC / {bc_time_moscow.strftime('%d.%m.%Y %H:%M:%S')} МСК"
            else:
                bc_time_str = str(bc_time)
                
            target_filter = bc.get('target_filter', {})
            logging.info(f"Запланированная рассылка ID:{bc['_id']}, время: {bc_time_str}, фильтр: {target_filter}, текущее время: {now} UTC")
    
    if not scheduled_broadcasts:
        return
        
    logging.info(f"Bot instance для отправки рассылок: {bot}")
    
    for broadcast in scheduled_broadcasts:
        broadcast_id = broadcast["_id"]
        message_text = broadcast["message_text"]
        target_filter = broadcast.get("target_filter")
        total_users = broadcast.get("total_users", 0)
        
        logging.info(f"Запуск запланированной рассылки ID: {broadcast_id}")
        
        # Обновляем статус рассылки
        await db[BROADCASTS_COLLECTION].update_one(
            {"_id": broadcast_id},
            {"$set": {"status": "in_progress", "started_at": datetime.utcnow()}}
        )
        
        try:
            # Определяем оптимальные параметры для рассылки на основе количества пользователей
            batch_size = 25
            batch_delay = 3
            
            # Для больших рассылок увеличиваем размер пакета и задержку
            if total_users > 1000:
                batch_size = 50
                batch_delay = 5
            elif total_users > 5000:
                batch_size = 100
                batch_delay = 10
            
            # Получаем данные о медиа, если они есть
            media = broadcast.get("media")
            media_type = broadcast.get("media_type")
            
            # Запускаем рассылку с использованием новой функциональности
            stats = await send_broadcast(
                bot=bot, 
                message_text=message_text, 
                target_filter=target_filter,
                save_to_db=False,  # Не создавать новую запись, используем существующую
                batch_size=batch_size,
                batch_delay=batch_delay,
                media=media,
                media_type=media_type
            )
            
            # Обновляем статистику в базе данных
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "sent_count": stats["sent"],
                        "failed_count": stats["failed"],
                        "errors": stats["errors"]
                    }
                }
            )
            
            logging.info(f"Запланированная рассылка ID: {broadcast_id} завершена. Статистика: {stats}")
            
        except Exception as e:
            # В случае ошибки, обновляем статус рассылки
            logging.error(f"Ошибка при запуске запланированной рассылки ID: {broadcast_id}: {e}")
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast_id},
                {"$set": {"status": "error", "error_message": str(e)}}
            )

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