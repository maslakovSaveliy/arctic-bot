"""
Обработчики команд для обычных пользователей бота
"""

import logging
from datetime import datetime
from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import CommandStart

from bot.database import add_user, update_user
from bot.handlers.join_request_handlers import pending_approvals, approve_join_request

async def start_cmd(message: types.Message):
    """
    Обработчик команды /start
    """
    user = message.from_user
    
    # Сохраняем или обновляем пользователя в базе данных
    await add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Обновляем время последнего взаимодействия
    await update_user(user.id, {"last_interaction": datetime.utcnow()})
    
    # Проверяем, есть ли ожидающий запрос на вступление
    if user.id in pending_approvals:
        # Одобряем запрос на вступление
        approved = await approve_join_request(user.id)
        
        if approved:
            await message.answer(
                f"Спасибо, {user.first_name}! Ваш запрос на вступление в канал одобрен.\n\n"
                "Теперь вы будете получать все уведомления от нашего бота."
            )
            logging.info(f"Пользователь {user.id} запустил бота, запрос на вступление одобрен")
            return
    
    # Проверяем аргументы команды
    args = message.get_args()
    if args == "join":
        await message.answer(
            f"{user.first_name}, если у вас есть ожидающий запрос на вступление в канал, "
            "он будет автоматически одобрен. Если запрос не был одобрен, "
            "возможно, вы еще не отправили его или он был обработан ранее."
        )
        return
    
    # Стандартное приветствие, если нет ожидающего запроса или не удалось его одобрить
    await message.answer(
        f"Привет, {user.first_name}! Я бот для управления приватным каналом.\n\n"
        "Для получения доступа к каналу вам необходимо перейти по пригласительной ссылке "
        "и ваша заявка будет рассмотрена."
    )

async def help_cmd(message: types.Message):
    """
    Обработчик команды /help
    """
    # Обновляем время последнего взаимодействия
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    
    text = (
        "Я бот для управления приватным каналом. Вот что я умею:\n\n"
        "- Автоматически обрабатывать запросы на вступление в канал\n"
        "- Отправлять уведомления о новых материалах\n\n"
        "Доступные команды:\n"
        "/start - Начать взаимодействие с ботом\n"
        "/help - Показать это сообщение\n"
        "/about - Информация о канале\n"
    )
    
    await message.answer(text)

async def about_cmd(message: types.Message):
    """
    Обработчик команды /about
    """
    # Обновляем время последнего взаимодействия
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    
    text = (
        "Это приватный канал с эксклюзивным контентом.\n\n"
        "Для получения доступа к каналу вам необходимо перейти по пригласительной ссылке "
        "и ваша заявка будет рассмотрена администраторами."
    )
    
    await message.answer(text)

async def any_message_handler(message: types.Message):
    """
    Обработчик любых сообщений для отслеживания активности пользователя
    """
    # Обновляем время последнего взаимодействия
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    
    # Проверяем, есть ли ожидающий запрос на вступление
    if message.from_user.id in pending_approvals:
        # Предлагаем пользователю отправить команду /start
        await message.answer(
            "Чтобы одобрить ваш запрос на вступление в канал, "
            "пожалуйста, отправьте команду /start."
        )
    
    # Не отвечаем на другие сообщения

def register_user_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков команд пользователя
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    dp.register_message_handler(start_cmd, CommandStart(), state="*")
    dp.register_message_handler(help_cmd, commands=["help"], state="*")
    dp.register_message_handler(about_cmd, commands=["about"], state="*")
    
    # Обработчик для всех текстовых сообщений (без приоритета)
    dp.register_message_handler(any_message_handler, content_types=types.ContentTypes.TEXT, state="*")