"""
Настройка логирования для бота
"""

import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir="logs", log_level=logging.INFO):
    """
    Настройка логирования
    
    Args:
        log_dir (str): Директория для хранения логов
        log_level: Уровень логирования
    """
    # Создаем директорию для логов, если она не существует
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем формат логов
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Основной файл лога
    file_handler = RotatingFileHandler(
        f"{log_dir}/bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(log_level)
    
    # Файл для ошибок
    error_file_handler = RotatingFileHandler(
        f"{log_dir}/errors.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    error_file_handler.setFormatter(log_format)
    error_file_handler.setLevel(logging.ERROR)
    
    # Вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
    root_logger.addHandler(console_handler)
    
    # Отключаем ненужные логи от внешних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    logging.info("Логирование настроено") 