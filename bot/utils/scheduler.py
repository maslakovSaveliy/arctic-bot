"""
Модуль для планирования отложенных задач
"""

import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pytz import utc
import pytz

from bot.database.db import get_db
from bot.config.config import BROADCASTS_COLLECTION
from bot.services.notifications import send_broadcast
from bot.handlers.join_request_handlers import clean_old_pending_approvals

# Глобальная переменная для хранения планировщика
_scheduler = None

def setup_scheduler():
    """
    Инициализация планировщика задач
    
    Returns:
        AsyncIOScheduler: Экземпляр планировщика
    """
    global _scheduler
    
    if _scheduler is None:
        # Явно устанавливаем часовой пояс UTC
        _scheduler = AsyncIOScheduler(timezone=utc)
        _scheduler.start()
        logging.info("Планировщик задач запущен с временной зоной UTC")
    
    return _scheduler

# Создаем функцию-обертку для передачи в APScheduler
def create_broadcast_check_job(bot):
    """
    Создает функцию-обертку для проверки запланированных рассылок
    
    Args:
        bot: Экземпляр бота
        
    Returns:
        callable: Функция для запуска в планировщике
    """
    async def job():
        await check_scheduled_broadcasts(bot)
    return job

async def migrate_old_broadcasts():
    """
    Миграция старых записей рассылок в формат UTC
    """
    try:
        db = get_db()
        local_tz = pytz.timezone('Europe/Moscow')  # Часовой пояс для старых записей
        
        # Находим все запланированные рассылки
        scheduled_broadcasts = await db[BROADCASTS_COLLECTION].find({
            "status": "scheduled"
        }).to_list(length=None)
        
        migrated_count = 0
        
        for broadcast in scheduled_broadcasts:
            schedule_time = broadcast.get("schedule_time")
            if schedule_time:
                # Проверяем время на наличие необычно больших значений часов (больше 14 может указывать на локальное время)
                if isinstance(schedule_time, datetime) and schedule_time.hour > 14:
                    # Предполагаем, что это локальное время
                    # Локализуем время
                    localized_time = local_tz.localize(schedule_time.replace(tzinfo=None))
                    
                    # Конвертируем в UTC
                    utc_time = localized_time.astimezone(pytz.UTC)
                    
                    # Убираем информацию о часовом поясе для совместимости
                    utc_time = utc_time.replace(tzinfo=None)
                    
                    # Обновляем запись в базе данных
                    await db[BROADCASTS_COLLECTION].update_one(
                        {"_id": broadcast["_id"]},
                        {"$set": {"schedule_time": utc_time}}
                    )
                    
                    logging.info(f"Мигрировано время рассылки ID:{broadcast['_id']} из {schedule_time} в {utc_time} (UTC)")
                    migrated_count += 1
        
        if migrated_count > 0:
            logging.info(f"Миграция времени рассылок завершена. Обработано {migrated_count} записей.")
        else:
            logging.info("Миграция времени рассылок: не найдено записей для обновления")
    
    except Exception as e:
        logging.error(f"Ошибка при миграции времени рассылок: {e}")

async def check_scheduled_broadcasts(bot):
    """
    Проверка и отправка запланированных рассылок
    
    Args:
        bot: Экземпляр бота
    """
    try:
        db = get_db()
        now = datetime.utcnow()
        
        # Также получаем московское время для информативного логгирования
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_now = now.replace(tzinfo=pytz.UTC).astimezone(moscow_tz)
        
        logging.info(f"Проверка запланированных рассылок в {now.isoformat()} UTC / {moscow_now.strftime('%d.%m.%Y %H:%M:%S')} МСК")
        
        # Находим все запланированные рассылки, время которых наступило
        scheduled_broadcasts = await db[BROADCASTS_COLLECTION].find({
            "status": "scheduled",
            "schedule_time": {"$lte": now}
        }).to_list(length=None)
        
        logging.info(f"Найдено {len(scheduled_broadcasts)} запланированных рассылок для отправки")
        
        # Выводим информацию о всех запланированных рассылках для отладки
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
            broadcast_id = str(broadcast["_id"])
            bc_time = broadcast.get('schedule_time', 'н/д')
            if isinstance(bc_time, datetime):
                # Конвертируем UTC время рассылки в московское для информативности
                bc_time_moscow = bc_time.replace(tzinfo=pytz.UTC).astimezone(moscow_tz)
                bc_time_str = f"{bc_time} UTC / {bc_time_moscow.strftime('%d.%m.%Y %H:%M:%S')} МСК"
            else:
                bc_time_str = str(bc_time)
                
            logging.info(f"Начинаем обработку рассылки ID:{broadcast_id}, запланированной на {bc_time_str}")
            
            # Проверка фильтра на наличие статуса active
            target_filter = broadcast.get("target_filter", {})
            if isinstance(target_filter, dict) and "status" not in target_filter:
                logging.info(f"Добавляем статус 'active' в фильтр рассылки ID:{broadcast_id}")
                target_filter["status"] = "active"
                # Обновляем фильтр в базе данных
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {"target_filter": target_filter}}
                )
            
            # Отмечаем, что рассылка в процессе отправки
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast["_id"]},
                {"$set": {"status": "in_progress"}}
            )
            
            try:
                # Определяем оптимальные параметры для рассылки на основе количества пользователей
                total_users = broadcast.get("total_users", 0)
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
                
                if media and media_type:
                    logging.info(f"Рассылка ID:{broadcast_id} содержит медиа-контент типа: {media_type}")
                
                # Отправляем рассылку с поддержкой медиа-контента
                logging.info(f"Отправляем рассылку ID:{broadcast_id}")
                stats = await send_broadcast(
                    bot=bot,
                    message_text=broadcast["message_text"],
                    target_filter=target_filter,  # Используем обновленный фильтр
                    save_to_db=False,
                    batch_size=batch_size,
                    batch_delay=batch_delay,
                    media=media,
                    media_type=media_type
                )
                
                # Обновляем статус рассылки
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {
                        "status": "completed", 
                        "completed_at": datetime.utcnow(),
                        "sent_count": stats.get("sent", 0),
                        "failed_count": stats.get("failed", 0)
                    }}
                )
                
                logging.info(f"Запланированная рассылка ID:{broadcast_id} выполнена. Отправлено: {stats.get('sent', 0)}, ошибок: {stats.get('failed', 0)}")
                
            except Exception as e:
                logging.error(f"Ошибка при отправке запланированной рассылки ID:{broadcast_id}: {e}")
                
                # Отмечаем, что произошла ошибка при отправке
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {"status": "error", "error": str(e)}}
                )
    
    except Exception as e:
        logging.error(f"Ошибка при проверке запланированных рассылок: {e}") 