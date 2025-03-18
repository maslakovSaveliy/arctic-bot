"""
Обработчики ошибок для бота
"""

import logging
from aiogram import Dispatcher
from aiogram.utils.exceptions import (
    TelegramAPIError,
    MessageNotModified,
    BotBlocked,
    CantTalkWithBots,
    ChatNotFound,
    UserDeactivated,
    BadRequest
)

async def errors_handler(update, exception):
    """
    Обработчик всех исключений в боте
    
    Args:
        update: Telegram объект, который вызвал исключение
        exception: Исключение
    
    Returns:
        bool: True, если исключение было обработано
    """
    # Ошибки, которые можно игнорировать
    if isinstance(exception, MessageNotModified):
        logging.warning(f'Сообщение не изменено: {exception}')
        return True
        
    if isinstance(exception, BotBlocked):
        # Пользователь заблокировал бота
        logging.warning(f'Бот заблокирован пользователем: {update.message.from_user.id}')
        return True
        
    if isinstance(exception, CantTalkWithBots):
        # Попытка написать боту
        logging.warning(f'Попытка написать боту: {exception}')
        return True
        
    if isinstance(exception, ChatNotFound):
        # Чат не найден
        logging.warning(f'Чат не найден: {exception}')
        return True
        
    if isinstance(exception, UserDeactivated):
        # Пользователь деактивирован
        logging.warning(f'Пользователь деактивирован: {exception}')
        return True
        
    if isinstance(exception, BadRequest):
        # Ошибка запроса к Telegram API
        logging.warning(f'Ошибка запроса: {exception}')
        return True
    
    # Общая обработка ошибок Telegram API
    if isinstance(exception, TelegramAPIError):
        logging.exception(f'Ошибка Telegram API: {exception}')
        return True
    
    # Для всех остальных исключений - логируем их
    logging.exception(f'Необработанное исключение: {exception}')
    return True

def register_error_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков ошибок
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    dp.register_errors_handler(errors_handler) 