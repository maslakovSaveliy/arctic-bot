"""
Основной файл для запуска Telegram-бота
"""

import logging
import asyncio
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime

from bot.config.config import TELEGRAM_BOT_TOKEN, DEBUG
from bot.handlers import register_all_handlers
from bot.database import init_db, close_db_connection
from bot.utils.logging_setup import setup_logging, clean_old_logs
from bot.utils.scheduler import setup_scheduler, check_scheduled_broadcasts, migrate_old_broadcasts, create_broadcast_check_job
from bot.handlers.join_request_handlers import clean_old_pending_approvals

# Настройка логирования
setup_logging(log_level=logging.DEBUG if DEBUG else logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Планировщик задач
scheduler = setup_scheduler()

async def on_startup(dispatcher):
    """
    Действия при запуске бота
    
    Args:
        dispatcher: Dispatcher объект
    """
    # Инициализация базы данных
    await init_db()
    
    # Регистрация обработчиков
    register_all_handlers(dispatcher)
    
    # Проверка экземпляра бота для диагностики
    logging.info(f"Экземпляр бота при запуске: {bot}")
    
    # Запускаем миграцию старых запланированных рассылок
    logging.info("Запуск миграции старых запланированных рассылок...")
    await migrate_old_broadcasts()
    
    # Первая проверка сразу при запуске
    await check_scheduled_broadcasts(bot)
    
    # Создаем функцию-обертку для передачи бота
    check_broadcasts_job = create_broadcast_check_job(bot)
    
    # Добавляем задачу для проверки запланированных рассылок
    scheduler.add_job(
        check_broadcasts_job,
        'interval',
        minutes=1,
        id='check_broadcasts',
        replace_existing=True,
        next_run_time=datetime.utcnow()  # Запускаем немедленно после старта
    )
    logging.info("Планировщик рассылок добавлен с интервалом 1 минута")
    
    # Добавляем задачу для очистки старых ожидающих запросов на вступление
    scheduler.add_job(
        clean_old_pending_approvals,
        'interval',
        hours=24,  # Запускаем раз в сутки
        id='clean_approvals',
        replace_existing=True
    )
    
    # Добавляем задачу для очистки старых файлов логов
    scheduler.add_job(
        clean_old_logs,
        'interval',
        hours=24,  # Запускаем раз в сутки
        id='clean_old_logs',
        replace_existing=True,
        kwargs={'days_to_keep': 30}  # Хранить логи 30 дней
    )
    logging.info("Планировщик очистки логов добавлен (интервал: 24 часа)")
    
    logging.info("Бот запущен")

async def on_shutdown(dispatcher):
    """
    Действия при остановке бота
    
    Args:
        dispatcher: Dispatcher объект
    """
    # Закрываем соединение с базой данных
    await close_db_connection()
    
    # Отменяем все задачи
    scheduler.shutdown()
    
    # Закрываем сессию бота (исправлено устаревшее использование)
    session = await bot.get_session()
    await session.close()
    
    logging.info("Бот остановлен")

if __name__ == "__main__":
    try:
        # В aiogram 2.20 используется executor для запуска бота с обработчиками
        executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
    except Exception as e:
        logging.exception(f"Критическая ошибка: {e}") 