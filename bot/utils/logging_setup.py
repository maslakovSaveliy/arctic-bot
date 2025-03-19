"""
Настройка логирования для бота
"""

import os
import logging
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime

def setup_logging(log_dir="logs", log_level=logging.INFO, 
                 max_size_mb=5, backup_count=5, 
                 enable_time_rotation=True, rotation_interval='midnight'):
    """
    Настройка логирования
    
    Args:
        log_dir (str): Директория для хранения логов
        log_level: Уровень логирования
        max_size_mb (int): Максимальный размер файла лога в МБ
        backup_count (int): Количество резервных копий для хранения
        enable_time_rotation (bool): Использовать временную ротацию вместо ротации по размеру
        rotation_interval (str): Интервал ротации ('midnight', 'h', 'd', 'w0')
    """
    # Создаем директорию для логов, если она не существует
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем формат логов
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Настраиваем обработчики логов с учетом выбранного типа ротации
    if enable_time_rotation:
        # Основной файл лога с ротацией по времени
        file_handler = TimedRotatingFileHandler(
            f"{log_dir}/bot.log",
            when=rotation_interval,
            interval=1,  # Интервал в единицах, указанных в when
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Файл для ошибок с ротацией по времени
        error_file_handler = TimedRotatingFileHandler(
            f"{log_dir}/errors.log",
            when=rotation_interval,
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
    else:
        # Основной файл лога с ротацией по размеру
        file_handler = RotatingFileHandler(
            f"{log_dir}/bot.log",
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Файл для ошибок с ротацией по размеру
        error_file_handler = RotatingFileHandler(
            f"{log_dir}/errors.log",
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
    
    file_handler.setFormatter(log_format)
    file_handler.setLevel(log_level)
    
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
    
    # Добавляем информацию о настройках ротации
    rotation_type = "времени" if enable_time_rotation else "размеру"
    rotation_settings = f"интервал={rotation_interval}" if enable_time_rotation else f"макс. размер={max_size_mb}MB"
    logging.info(f"Настроена ротация логов по {rotation_type} ({rotation_settings}), хранение {backup_count} копий")


def clean_old_logs(log_dir="logs", days_to_keep=30):
    """
    Очистка старых файлов логов
    
    Args:
        log_dir (str): Директория с логами
        days_to_keep (int): Количество дней хранения логов
    """
    if not os.path.exists(log_dir):
        return
        
    current_time = time.time()
    seconds_in_day = 86400  # 60 * 60 * 24
    max_age = days_to_keep * seconds_in_day
    
    count_removed = 0
    
    for filename in os.listdir(log_dir):
        # Пропускаем файл keep
        if filename == 'keep':
            continue
            
        # Пропускаем текущие файлы логов без даты
        if filename in ['bot.log', 'errors.log']:
            continue
            
        file_path = os.path.join(log_dir, filename)
        
        # Проверяем, что это файл (не директория)
        if os.path.isfile(file_path):
            file_age = current_time - os.path.getmtime(file_path)
            
            # Если файл старше максимального возраста, удаляем его
            if file_age > max_age:
                try:
                    os.remove(file_path)
                    count_removed += 1
                except Exception as e:
                    logging.error(f"Ошибка при удалении старого лога {file_path}: {e}")
    
    if count_removed > 0:
        logging.info(f"Удалено {count_removed} устаревших файлов логов (старше {days_to_keep} дней)") 