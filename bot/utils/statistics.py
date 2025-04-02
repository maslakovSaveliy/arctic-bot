"""
Модуль для сбора и экспорта статистики
"""

import logging
from datetime import datetime
import pandas as pd
import io
import asyncio
from aiogram import types
from bot.database import get_all_users, get_users_by_filter
from bot.database.db import get_db
from bot.config.config import BROADCASTS_COLLECTION

async def generate_users_statistics_excel():
    """
    Генерирует Excel файл со статистикой по пользователям
    
    Returns:
        io.BytesIO: Excel файл в виде байтового потока
    """
    logging.info("Начинаем генерацию Excel файла со статистикой")
    
    # Получаем всех пользователей с постраничной загрузкой, чтобы снизить нагрузку на базу данных
    batch_size = 1000  # Размер порции данных
    all_users = []
    skip = 0
    
    while True:
        logging.info(f"Загружаем пользователей (смещение: {skip}, лимит: {batch_size})")
        users_batch = await get_all_users(limit=batch_size, skip=skip)
        if not users_batch:
            break
            
        all_users.extend(users_batch)
        skip += batch_size
        
        if len(users_batch) < batch_size:
            # Если количество пользователей в порции меньше размера порции, значит это последняя порция
            break
    
    logging.info(f"Всего загружено {len(all_users)} пользователей")
    
    # Подготавливаем данные для Excel
    data = []
    for user in all_users:
        # Формируем запись для каждого пользователя
        row = {
            'ID пользователя': user.get('user_id'),
            'Имя': user.get('first_name', ''),
            'Фамилия': user.get('last_name', ''),
            'Юзернейм': user.get('username', ''),
            'Дата подписки': user.get('created_at', '').strftime('%d.%m.%Y %H:%M:%S') if user.get('created_at') else '',
            'Дата активации': user.get('activated_at', '').strftime('%d.%m.%Y %H:%M:%S') if user.get('activated_at') else '',
            'Дата отписки': user.get('deactivated_at', '').strftime('%d.%m.%Y %H:%M:%S') if user.get('deactivated_at') else '',
            'Источник': user.get('source', ''),
            'Статус': user.get('status', ''),
            'Город': user.get('city', ''),
        }
        
        data.append(row)
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Загружаем данные о рассылках из базы батчами
    db = get_db()
    broadcasts_collection = db[BROADCASTS_COLLECTION]
    
    # Получаем общее количество рассылок для логирования
    total_broadcasts = await broadcasts_collection.count_documents({})
    logging.info(f"Общее количество рассылок: {total_broadcasts}")
    
    # Строим словарь с подсчетом рассылок на пользователя
    user_broadcast_counts = {}
    
    for user in all_users:
        user_id = user.get('user_id')
        user_broadcast_counts[user_id] = {
            'total_broadcasts': 0
        }
    
    # Получаем рассылки порциями для снижения нагрузки на память
    broadcast_batch_size = 500
    broadcast_skip = 0
    
    while True:
        logging.info(f"Загружаем рассылки (смещение: {broadcast_skip}, лимит: {broadcast_batch_size})")
        broadcasts_batch = await broadcasts_collection.find({}).skip(broadcast_skip).limit(broadcast_batch_size).to_list(length=None)
        
        if not broadcasts_batch:
            break
            
        # Подсчет рассылок
        for broadcast in broadcasts_batch:
            # Пропускаем незавершенные рассылки
            if broadcast.get('status') not in ['completed', 'in_progress']:
                continue
                
            target_filter = broadcast.get('target_filter', {})
            if isinstance(target_filter, dict):
                # Вместо того, чтобы делать запрос для каждой рассылки, мы проверяем соответствие пользователей фильтру прямо в коде
                for user in all_users:
                    user_id = user.get('user_id')
                    if user_id in user_broadcast_counts:
                        # Проверяем соответствие пользователя фильтру
                        matches_filter = True
                        for key, value in target_filter.items():
                            if user.get(key) != value:
                                matches_filter = False
                                break
                                
                        if matches_filter:
                            user_broadcast_counts[user_id]['total_broadcasts'] += 1
            
        broadcast_skip += broadcast_batch_size
        
        if len(broadcasts_batch) < broadcast_batch_size:
            # Если количество рассылок в порции меньше размера порции, значит это последняя порция
            break
            
        # Даем системе немного отдохнуть, чтобы не перегружать память и CPU
        await asyncio.sleep(0.1)
    
    # Добавляем информацию о рассылках в DataFrame
    broadcasts_data = []
    for user_id, counts in user_broadcast_counts.items():
        broadcasts_data.append({
            'ID пользователя': user_id,
            'Количество рассылок': counts['total_broadcasts']
        })
    
    broadcasts_df = pd.DataFrame(broadcasts_data)
    
    # Объединяем DataFrame с основной таблицей
    if not broadcasts_df.empty:
        df = df.merge(broadcasts_df, on='ID пользователя', how='left')
    else:
        df['Количество рассылок'] = 0
    
    # Заполняем NA значения
    df = df.fillna('')
    
    logging.info(f"Начинаем создание Excel файла для {len(df)} пользователей")
    
    # Создаем байтовый поток для Excel файла
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Пользователи', index=False)
        
        # Настройка ширины столбцов
        worksheet = writer.sheets['Пользователи']
        for i, col in enumerate(df.columns):
            # Для оптимизации не рассчитываем максимальную длину для больших наборов данных
            # Просто устанавливаем стандартные ширины для известных столбцов
            if col == 'ID пользователя':
                worksheet.set_column(i, i, 15)
            elif col in ['Имя', 'Фамилия', 'Юзернейм', 'Источник', 'Статус', 'Город']:
                worksheet.set_column(i, i, 20)
            elif col in ['Дата подписки', 'Дата активации', 'Дата отписки']:
                worksheet.set_column(i, i, 25)
            elif col == 'Количество рассылок':
                worksheet.set_column(i, i, 20)
            else:
                worksheet.set_column(i, i, 15)
    
    # Переводим указатель на начало потока
    output.seek(0)
    
    logging.info(f"Excel файл со статистикой успешно создан")
    
    return output

async def send_statistics_excel(message: types.Message):
    """
    Отправляет Excel файл со статистикой пользователю
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        # Отправляем сообщение о процессе генерации
        status_msg = await message.answer("⏳ Генерирую Excel файл со статистикой. Это может занять некоторое время для большой базы пользователей...")
        
        # Генерируем Excel-файл
        excel_file = await generate_users_statistics_excel()
        
        # Обновляем статус
        await status_msg.edit_text("✅ Excel файл сгенерирован, отправляю...")
        
        # Формируем название файла
        filename = f"statistics_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
        
        # Отправляем файл
        await message.answer_document(
            types.InputFile(excel_file, filename=filename),
            caption="Статистика пользователей бота (всех пользователей)"
        )
        
        logging.info(f"Excel-файл со статистикой успешно отправлен администратору {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке Excel-файла: {e}")
        await message.answer(f"Произошла ошибка при формировании статистики: {e}")

async def send_active_users_statistics_excel(message: types.Message):
    """
    Отправляет Excel файл со статистикой только активных пользователей
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        # Отправляем сообщение о процессе генерации
        await message.answer("⏳ Генерирую Excel файл со статистикой активных пользователей...")
        
        # Получаем всех активных пользователей с постраничной загрузкой
        batch_size = 1000
        all_users = []
        skip = 0
        
        while True:
            users_batch = await get_all_users(status="active", limit=batch_size, skip=skip)
            if not users_batch:
                break
                
            all_users.extend(users_batch)
            skip += batch_size
            
            if len(users_batch) < batch_size:
                break
        
        # Подготавливаем данные для Excel
        data = []
        for user in all_users:
            row = {
                'ID пользователя': user.get('user_id'),
                'Имя': user.get('first_name', ''),
                'Фамилия': user.get('last_name', ''),
                'Юзернейм': user.get('username', ''),
                'Дата подписки': user.get('created_at', '').strftime('%d.%m.%Y %H:%M:%S') if user.get('created_at') else '',
                'Дата активации': user.get('activated_at', '').strftime('%d.%m.%Y %H:%M:%S') if user.get('activated_at') else '',
                'Источник': user.get('source', ''),
                'Город': user.get('city', ''),
            }
            data.append(row)
        
        # Создаем DataFrame и Excel
        df = pd.DataFrame(data)
        
        # Создаем байтовый поток для Excel файла
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Активные пользователи', index=False)
            
            # Настройка ширины столбцов
            worksheet = writer.sheets['Активные пользователи']
            for i, col in enumerate(df.columns):
                # Устанавливаем стандартные ширины для столбцов
                if col == 'ID пользователя':
                    worksheet.set_column(i, i, 15)
                elif col in ['Имя', 'Фамилия', 'Юзернейм', 'Источник', 'Город']:
                    worksheet.set_column(i, i, 20)
                elif col in ['Дата подписки', 'Дата активации']:
                    worksheet.set_column(i, i, 25)
                else:
                    worksheet.set_column(i, i, 15)
        
        # Переводим указатель на начало потока
        output.seek(0)
        
        # Формируем название файла
        filename = f"active_users_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
        
        # Отправляем файл
        await message.answer_document(
            types.InputFile(output, filename=filename),
            caption=f"Статистика активных пользователей бота ({len(all_users)} пользователей)"
        )
        
        logging.info(f"Excel-файл с активными пользователями успешно отправлен администратору {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке Excel-файла с активными пользователями: {e}")
        await message.answer(f"Произошла ошибка при формировании статистики активных пользователей: {e}") 