"""
Модуль для планирования отложенных задач
"""

import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logging.info("Планировщик задач запущен")
    
    return _scheduler

async def check_scheduled_broadcasts(bot):
    """
    Проверка и отправка запланированных рассылок
    
    Args:
        bot: Экземпляр бота
    """
    try:
        db = get_db()
        now = datetime.utcnow()
        
        # Находим все запланированные рассылки, время которых наступило
        scheduled_broadcasts = await db[BROADCASTS_COLLECTION].find({
            "status": "scheduled",
            "schedule_time": {"$lte": now}
        }).to_list(length=None)
        
        for broadcast in scheduled_broadcasts:
            # Отмечаем, что рассылка в процессе отправки
            await db[BROADCASTS_COLLECTION].update_one(
                {"_id": broadcast["_id"]},
                {"$set": {"status": "in_progress"}}
            )
            
            try:
                # Отправляем рассылку
                await send_broadcast(
                    bot,
                    broadcast["message_text"],
                    target_filter=broadcast.get("target_filter"),
                    save_to_db=False
                )
                
                # Обновляем статус рассылки
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
                )
                
                logging.info(f"Запланированная рассылка ID:{broadcast['_id']} выполнена")
                
            except Exception as e:
                logging.error(f"Ошибка при отправке запланированной рассылки ID:{broadcast['_id']}: {e}")
                
                # Отмечаем, что произошла ошибка при отправке
                await db[BROADCASTS_COLLECTION].update_one(
                    {"_id": broadcast["_id"]},
                    {"$set": {"status": "error", "error": str(e)}}
                )
    
    except Exception as e:
        logging.error(f"Ошибка при проверке запланированных рассылок: {e}") 