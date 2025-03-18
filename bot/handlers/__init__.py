"""
Модуль обработчиков команд и событий для Telegram бота
"""

from bot.handlers.admin_handlers import register_admin_handlers
from bot.handlers.user_handlers import register_user_handlers
from bot.handlers.join_request_handlers import register_join_request_handlers
from bot.handlers.error_handlers import register_error_handlers

def register_all_handlers(dp):
    """
    Регистрация всех обработчиков
    
    Args:
        dp: Dispatcher объект
    """
    handlers = [
        register_admin_handlers,
        register_user_handlers,
        register_join_request_handlers,
        register_error_handlers
    ]
    
    for handler in handlers:
        handler(dp) 