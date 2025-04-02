"""
Обработчики запросов на вступление в канал
"""

import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, Bot
from aiogram.types import ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config.config import DEFAULT_WELCOME_MESSAGE
from bot.database import add_user, get_source_by_link, update_user, get_user
from bot.services.notifications import send_welcome_message
from bot.handlers.city_handlers import ask_city_by_user_id

# Словарь для хранения информации о пользователях, ожидающих одобрения
# Формат: {user_id: {"join_request": join_request, "source": source, "timestamp": datetime}}
pending_approvals = {}

async def process_join_request(join_request: ChatJoinRequest):
    """
    Обработка запроса на вступление в канал
    
    Args:
        join_request (ChatJoinRequest): Запрос на вступление
    """
    user = join_request.from_user
    invite_link = join_request.invite_link
    
    logging.info(f"Получен запрос на вступление от пользователя {user.id} ({user.full_name}) по ссылке {invite_link.invite_link if invite_link else 'неизвестная ссылка'}")
    
    try:
        # Определяем источник по ссылке (если доступна)
        source = None
        if invite_link and invite_link.invite_link:
            source = await get_source_by_link(invite_link.invite_link)
        
        # Сохраняем данные о пользователе со статусом pending
        await add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            source=source,
            status="pending"
        )
        
        # Добавляем в словарь ожидающих одобрения
        pending_approvals[user.id] = {
            "join_request": join_request,
            "source": source,
            "timestamp": datetime.utcnow()
        }
        
        # Создаем клавиатуру с кнопкой для перехода к боту
        from bot.main import bot  # Импортируем здесь, чтобы избежать цикличных импортов
        bot_username = (await bot.get_me()).username
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Перейти к боту", url=f"https://t.me/{bot_username}?start=join"))
        
        # Отправляем сообщение с просьбой запустить бота
        try:
            await bot.send_message(
                chat_id=user.id,
                text=(
                    f"Здравствуйте, {user.first_name}! Ваш запрос на вступление в канал получен.\n\n"
                    "⚠️ Для одобрения вашей заявки, пожалуйста, нажмите кнопку ниже и отправьте команду /start боту.\n"
                    "Это необходимо для обеспечения возможности отправки вам уведомлений."
                ),
                reply_markup=keyboard
            )
            logging.info(f"Отправлено сообщение с просьбой запустить бота пользователю {user.id}")
        except Exception as e:
            # Если не удалось отправить сообщение (например, пользователь не запускал бота ранее)
            # Все равно оставляем запрос в ожидании
            logging.warning(f"Не удалось отправить сообщение пользователю {user.id}: {e}")
        
    except Exception as e:
        logging.error(f"Ошибка при обработке запроса на вступление от пользователя {user.id}: {e}")

async def approve_join_request(user_id):
    """
    Одобрение запроса на вступление в канал
    
    Args:
        user_id (int): ID пользователя
        
    Returns:
        bool: True, если запрос был успешно одобрен
    """
    try:
        # Проверяем, есть ли запрос в словаре ожидающих
        if user_id in pending_approvals:
            join_request = pending_approvals[user_id]["join_request"]
            source = pending_approvals[user_id]["source"]
            
            # Одобряем запрос на вступление
            await join_request.approve()
            logging.info(f"Запрос на вступление пользователя {user_id} одобрен")
            
            # Получаем данные пользователя
            user_data = await get_user(user_id)
            if user_data:
                # Обновляем статус пользователя на "active"
                await update_user(
                    user_id,
                    {
                        "status": "active",
                        "activated_at": datetime.utcnow(),
                        "last_interaction": datetime.utcnow()
                    }
                )
                
                # Удаляем из словаря ожидающих
                del pending_approvals[user_id]
                
                return True
        else:
            logging.warning(f"Не найдена информация о запросе на вступление для пользователя {user_id}")
        
        return False
    except Exception as e:
        logging.error(f"Ошибка при одобрении запроса на вступление от пользователя {user_id}: {e}")
        return False

async def clean_old_pending_approvals():
    """
    Очистка старых ожидающих запросов на вступление
    Удаляет запросы, которые были созданы более 7 дней назад
    """
    now = datetime.utcnow()
    expired_time = timedelta(days=7)  # Запросы устаревают через 7 дней
    
    # Находим устаревшие запросы
    expired_user_ids = []
    for user_id, data in pending_approvals.items():
        if now - data["timestamp"] > expired_time:
            expired_user_ids.append(user_id)
    
    # Удаляем устаревшие запросы
    for user_id in expired_user_ids:
        del pending_approvals[user_id]
        logging.info(f"Удален устаревший запрос на вступление от пользователя {user_id}")
    
    if expired_user_ids:
        logging.info(f"Очищено {len(expired_user_ids)} устаревших запросов на вступление")
    
    # Возвращаем статистику
    return {
        "total_pending": len(pending_approvals),
        "cleaned": len(expired_user_ids)
    }

def register_join_request_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков запросов на вступление
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    dp.register_chat_join_request_handler(process_join_request) 