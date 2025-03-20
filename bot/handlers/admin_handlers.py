"""
Обработчики команд для администраторов бота
"""

import logging
import json
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text, IDFilter
import pytz

from bot.config.config import ADMIN_USER_IDS
from bot.database import (
    get_all_users, 
    get_users_by_filter, 
    get_all_invite_links
)
from bot.services.invite_links import generate_invite_link
from bot.services.notifications import send_broadcast, schedule_broadcast

class BroadcastStates(StatesGroup):
    """
    Состояния для FSM при создании рассылки
    """
    waiting_for_message = State()
    waiting_for_scheduled_message = State()  # Отдельное состояние для запланированной рассылки
    waiting_for_media = State()              # Ожидание медиа-контента
    waiting_for_scheduled_media = State()    # Ожидание медиа для запланированной рассылки
    waiting_for_target = State()
    waiting_for_scheduled_target = State()   # Отдельное состояние для выбора цели в запланированной рассылке
    waiting_for_confirmation = State()
    waiting_for_schedule_time = State()
    waiting_for_schedule_confirmation = State()

class InviteLinkStates(StatesGroup):
    """
    Состояния для FSM при создании пригласительной ссылки
    """
    waiting_for_source = State()
    waiting_for_description = State()
    waiting_for_expire_date = State()

async def admin_start(message: types.Message):
    """
    Обработчик команды /admin
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        "📊 Статистика",
        "🔗 Создать ссылку",
        "📨 Создать рассылку",
        "📅 Запланировать рассылку"
    ]
    keyboard.add(*buttons)
    
    await message.answer(
        "Панель управления администратора. Выберите действие:",
        reply_markup=keyboard
    )

async def show_statistics(message: types.Message):
    """
    Показывает статистику по пользователям и источникам
    """
    # Получаем всех пользователей
    all_users = await get_all_users()
    active_users = await get_all_users(status="active")
    
    # Группируем пользователей по источникам
    sources = {}
    for user in active_users:
        source = user.get("source", "Неизвестно")
        if source not in sources:
            sources[source] = 0
        sources[source] += 1
    
    # Формируем текст сообщения
    text = "📊 *Статистика*\n\n"
    text += f"Всего пользователей: {len(all_users)}\n"
    text += f"Активных пользователей: {len(active_users)}\n\n"
    
    text += "*По источникам:*\n"
    for source, count in sources.items():
        text += f"- {source}: {count}\n"
    
    # Получаем все пригласительные ссылки
    invite_links = await get_all_invite_links()
    
    text += f"\n*Всего активных ссылок:* {len(invite_links)}\n"
    
    await message.answer(text, parse_mode=types.ParseMode.MARKDOWN)

async def create_invite_link_cmd(message: types.Message):
    """
    Начинает процесс создания пригласительной ссылки
    """
    await message.answer("Введите источник для новой пригласительной ссылки (например, 'Instagram', 'Facebook', 'Сайт' и т.д.):")
    await InviteLinkStates.waiting_for_source.set()

async def process_invite_link_source(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод источника для пригласительной ссылки
    """
    async with state.proxy() as data:
        data["source"] = message.text
    
    await message.answer("Введите описание для ссылки (или отправьте 'нет', если описание не требуется):")
    await InviteLinkStates.waiting_for_description.set()

async def process_invite_link_description(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод описания для пригласительной ссылки
    """
    async with state.proxy() as data:
        if message.text.lower() not in ["нет", "no", "-", "n"]:
            data["description"] = message.text
        else:
            data["description"] = None
    
    await message.answer(
        "Введите срок действия ссылки в днях (или отправьте '0', если ссылка не должна истекать):"
    )
    await InviteLinkStates.waiting_for_expire_date.set()

async def process_invite_link_expire_date(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод срока действия для пригласительной ссылки и генерирует ссылку
    """
    try:
        days = int(message.text)
        
        async with state.proxy() as data:
            if days > 0:
                data["expire_date"] = datetime.now() + timedelta(days=days)
            else:
                data["expire_date"] = None
        
        # Генерируем ссылку без ограничения по количеству использований
        link_data = await generate_invite_link(
            bot=message.bot,
            source=data["source"],
            created_by=message.from_user.id,
            expire_date=data.get("expire_date"),
            member_limit=None,
            description=data.get("description")
        )
        
        # Формируем сообщение
        text = "🔗 *Новая пригласительная ссылка создана:*\n\n"
        text += f"Ссылка: {link_data['invite_link']}\n"
        text += f"Источник: {link_data['source']}\n"
        
        if link_data.get("description"):
            text += f"Описание: {link_data['description']}\n"
        
        if link_data.get("expires_at"):
            text += f"Истекает: {link_data['expires_at']}\n"
        
        await message.answer(text, parse_mode=types.ParseMode.MARKDOWN)
        await state.finish()
    
    except ValueError:
        await message.answer("Пожалуйста, введите число. Попробуйте еще раз:")
    except Exception as e:
        logging.error(f"Ошибка при создании пригласительной ссылки: {e}")
        await message.answer(f"Произошла ошибка при создании ссылки: {str(e)}")
        await state.finish()  # Завершаем состояние в случае ошибки

async def create_broadcast_cmd(message: types.Message):
    """
    Начинает процесс создания рассылки
    """
    await message.answer("Введите текст сообщения для рассылки:")
    await BroadcastStates.waiting_for_message.set()

async def process_broadcast_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод текста сообщения для рассылки
    """
    async with state.proxy() as data:
        data["message_text"] = message.text
    
    # Предлагаем добавить медиа
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Без медиа", callback_data="media_none"))
    keyboard.add(types.InlineKeyboardButton("Добавить фото", callback_data="media_photo"))
    keyboard.add(types.InlineKeyboardButton("Добавить видео", callback_data="media_video"))
    keyboard.add(types.InlineKeyboardButton("Добавить GIF", callback_data="media_animation"))
    
    await message.answer(
        "Хотите добавить медиа-контент к рассылке?", 
        reply_markup=keyboard
    )
    await BroadcastStates.waiting_for_media.set()

async def process_broadcast_media_choice(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор типа медиа-контента
    """
    await callback_query.answer()
    
    choice = callback_query.data
    
    if choice == "media_none":
        # Пользователь выбрал не добавлять медиа, переходим к выбору целевой аудитории
        await show_target_selection(callback_query.message, state)
    else:
        # Сохраняем выбранный тип медиа
        media_type = choice.split("_")[1]  # Получаем photo, video или animation
        async with state.proxy() as data:
            data["media_type"] = media_type
        
        # Просим отправить медиа-файл
        media_type_text = {
            "photo": "фотографию",
            "video": "видео",
            "animation": "GIF-анимацию"
        }.get(media_type, "медиа-файл")
        
        await callback_query.message.answer(f"Отправьте {media_type_text} для рассылки:")

async def process_broadcast_media(message: types.Message, state: FSMContext):
    """
    Обрабатывает полученный медиа-файл для рассылки
    """
    async with state.proxy() as data:
        media_type = data.get("media_type")
        
        if media_type == "photo" and message.photo:
            # Берем последнее фото (максимальное разрешение)
            data["media"] = message.photo[-1].file_id
            logging.info(f"Получено фото для рассылки: {data['media']}")
        elif media_type == "video" and message.video:
            data["media"] = message.video.file_id
            logging.info(f"Получено видео для рассылки: {data['media']}")
        elif media_type == "animation" and message.animation:
            data["media"] = message.animation.file_id
            logging.info(f"Получена GIF-анимация для рассылки: {data['media']}")
        else:
            await message.answer("Отправленный файл не соответствует выбранному типу медиа. Пожалуйста, отправьте корректный файл или выберите другой тип.")
            return
    
    # Переходим к выбору целевой аудитории
    await show_target_selection(message, state)

async def show_target_selection(message, state: FSMContext, page=0):
    """
    Показывает выбор целевой аудитории с пагинацией
    
    Args:
        message: Сообщение или коллбэк
        state: Состояние FSM
        page (int): Номер страницы для пагинации (начиная с 0)
    """
    # Получаем активных пользователей и их источники
    sources = {}
    active_users = await get_all_users(status="active")
    
    # Собираем уникальные источники и количество пользователей
    for user in active_users:
        source = user.get("source", "Неизвестно")
        if source not in sources:
            sources[source] = 0
        sources[source] += 1
    
    # Сортируем источники по количеству пользователей (от большего к меньшему)
    sorted_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)
    
    # Конфигурация пагинации
    SOURCES_PER_PAGE = 5  # Количество источников на одной странице
    total_pages = max(1, (len(sorted_sources) + SOURCES_PER_PAGE - 1) // SOURCES_PER_PAGE)
    
    # Проверяем, нужна ли пагинация
    pagination_needed = len(sorted_sources) > SOURCES_PER_PAGE
    
    # Ограничиваем страницы доступным диапазоном
    page = max(0, min(page, total_pages - 1))
    
    # Выбираем источники для текущей страницы
    start_idx = page * SOURCES_PER_PAGE
    end_idx = min(start_idx + SOURCES_PER_PAGE, len(sorted_sources))
    current_page_sources = sorted_sources[start_idx:end_idx]
    
    # Создаем клавиатуру
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем кнопку "Все пользователи" только на первой странице
    if page == 0:
        keyboard.add(types.InlineKeyboardButton("Все пользователи", callback_data="target_all"))
    
    # Добавляем кнопки источников
    for source, count in current_page_sources:
        if source:  # Игнорируем пустые источники
            keyboard.add(types.InlineKeyboardButton(
                f"{source} ({count} пользователей)", 
                callback_data=f"target_source_{source}"
            ))
    
    # Добавляем кнопки навигации, если нужна пагинация
    if pagination_needed:
        nav_buttons = []
        
        # Кнопка "Назад"
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f"target_page_{page-1}"))
        
        # Информация о текущей странице
        page_info = f"{page+1}/{total_pages}"
        nav_buttons.append(types.InlineKeyboardButton(page_info, callback_data="target_page_info"))
        
        # Кнопка "Вперед"
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Вперед ▶️", callback_data=f"target_page_{page+1}"))
            
        keyboard.row(*nav_buttons)
    
    # Отправляем сообщение с клавиатурой
    message_text = "Выберите целевую аудиторию для рассылки:"
    
    # Проверяем, это новое сообщение или обновление существующего
    if isinstance(message, types.Message):
        await message.answer(message_text, reply_markup=keyboard)
    else:
        await message.edit_text(message_text, reply_markup=keyboard)
    
    await BroadcastStates.waiting_for_target.set()

async def process_target_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает пагинацию при выборе целевой аудитории
    """
    await callback_query.answer()
    
    # Извлекаем номер страницы из данных колбэка
    page_data = callback_query.data
    if page_data == "target_page_info":
        # Это нажатие на номер страницы, игнорируем
        return
    
    # Формат: "target_page_X"
    page = int(page_data.split("_")[2])
    
    # Показываем выбранную страницу
    await show_target_selection(callback_query.message, state, page)

async def process_broadcast_target(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор целевой аудитории для рассылки
    """
    await callback_query.answer()
    
    target_data = callback_query.data
    target_filter = None
    target_description = "всем пользователям"
    
    if target_data.startswith("target_source_"):
        source = target_data[14:]  # Вырезаем префикс "target_source_"
        target_filter = {"source": source}
        target_description = f"пользователям из источника '{source}'"
        logging.info(f"Выбрана целевая аудитория: пользователи из источника '{source}'")
    else:
        logging.info("Выбрана целевая аудитория: все пользователи")
    
    async with state.proxy() as data:
        data["target_filter"] = target_filter
        data["target_description"] = target_description
        
        # Получаем количество активных пользователей для рассылки
        if target_filter:
            # Всегда добавляем статус "active"
            combined_filter = target_filter.copy()
            combined_filter["status"] = "active"
            users = await get_users_by_filter(combined_filter)
        else:
            users = await get_all_users(status="active")
        
        logging.info(f"Найдено {len(users)} активных пользователей для рассылки с фильтром: {target_filter}")
        
        # Формируем сообщение для подтверждения
        confirmation_message = (
            f"Вы собираетесь отправить следующее сообщение {target_description} "
            f"(всего {len(users)} активных пользователей):\n\n"
            f"{data['message_text']}"
        )
        
        # Добавляем информацию о медиа, если есть
        if "media" in data and "media_type" in data:
            media_type_text = {
                "photo": "фотографией",
                "video": "видео",
                "animation": "GIF-анимацией"
            }.get(data["media_type"], "медиа")
            
            confirmation_message += f"\n\nСообщение будет отправлено с {media_type_text}."
        
        confirmation_message += "\n\nПодтвердите отправку (да/нет):"
    
    await callback_query.message.answer(confirmation_message)
    await BroadcastStates.waiting_for_confirmation.set()

async def process_broadcast_confirmation(message: types.Message, state: FSMContext):
    """
    Обрабатывает подтверждение отправки рассылки
    """
    if message.text.lower() in ["да", "yes", "y", "д"]:
        async with state.proxy() as data:
            message_text = data["message_text"]
            target_filter = data.get("target_filter")
            target_description = data.get("target_description", "всем пользователям")
            media = data.get("media")
            media_type = data.get("media_type")
        
        # Отправляем уведомление о начале рассылки
        await message.answer(f"Рассылка {target_description} начата. Это может занять некоторое время...")
        
        # Выполняем рассылку с медиа (если есть)
        stats = await send_broadcast(
            bot=message.bot, 
            message_text=message_text, 
            target_filter=target_filter,
            media=media,
            media_type=media_type
        )
        
        # Отправляем отчет о результатах
        result_message = (
            f"✅ Рассылка завершена.\n\n"
            f"Всего пользователей: {stats['total']}\n"
            f"Успешно отправлено: {stats['sent']}\n"
            f"Не удалось отправить: {stats['failed']}"
        )
        
        await message.answer(result_message)
    else:
        await message.answer("Рассылка отменена.")
    
    await state.finish()

async def schedule_broadcast_cmd(message: types.Message):
    """
    Начинает процесс планирования отложенной рассылки
    """
    await message.answer("Введите текст сообщения для запланированной рассылки:")
    await BroadcastStates.waiting_for_scheduled_message.set()

async def process_scheduled_broadcast_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод текста сообщения для запланированной рассылки
    """
    async with state.proxy() as data:
        data["message_text"] = message.text
    
    # Предлагаем добавить медиа (аналогично обычной рассылке)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Без медиа", callback_data="schedule_media_none"))
    keyboard.add(types.InlineKeyboardButton("Добавить фото", callback_data="schedule_media_photo"))
    keyboard.add(types.InlineKeyboardButton("Добавить видео", callback_data="schedule_media_video"))
    keyboard.add(types.InlineKeyboardButton("Добавить GIF", callback_data="schedule_media_animation"))
    
    await message.answer(
        "Хотите добавить медиа-контент к запланированной рассылке?", 
        reply_markup=keyboard
    )
    await BroadcastStates.waiting_for_scheduled_media.set()

async def process_scheduled_broadcast_media_choice(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор типа медиа-контента для запланированной рассылки
    """
    await callback_query.answer()
    
    choice = callback_query.data
    
    if choice == "schedule_media_none":
        # Пользователь выбрал не добавлять медиа, переходим к выбору целевой аудитории
        await show_scheduled_target_selection(callback_query.message, state)
    else:
        # Сохраняем выбранный тип медиа
        media_type = choice.split("_")[2]  # Получаем photo, video или animation
        async with state.proxy() as data:
            data["media_type"] = media_type
        
        # Просим отправить медиа-файл
        media_type_text = {
            "photo": "фотографию",
            "video": "видео",
            "animation": "GIF-анимацию"
        }.get(media_type, "медиа-файл")
        
        await callback_query.message.answer(f"Отправьте {media_type_text} для запланированной рассылки:")

async def process_scheduled_broadcast_media(message: types.Message, state: FSMContext):
    """
    Обрабатывает полученный медиа-файл для запланированной рассылки
    """
    async with state.proxy() as data:
        media_type = data.get("media_type")
        
        if media_type == "photo" and message.photo:
            # Берем последнее фото (максимальное разрешение)
            data["media"] = message.photo[-1].file_id
            logging.info(f"Получено фото для запланированной рассылки: {data['media']}")
        elif media_type == "video" and message.video:
            data["media"] = message.video.file_id
            logging.info(f"Получено видео для запланированной рассылки: {data['media']}")
        elif media_type == "animation" and message.animation:
            data["media"] = message.animation.file_id
            logging.info(f"Получена GIF-анимация для запланированной рассылки: {data['media']}")
        else:
            await message.answer("Отправленный файл не соответствует выбранному типу медиа. Пожалуйста, отправьте корректный файл или выберите другой тип.")
            return
    
    # Переходим к выбору целевой аудитории
    await show_scheduled_target_selection(message, state)

async def show_scheduled_target_selection(message, state: FSMContext, page=0):
    """
    Показывает выбор целевой аудитории для запланированной рассылки с пагинацией
    
    Args:
        message: Сообщение или коллбэк
        state: Состояние FSM
        page (int): Номер страницы для пагинации (начиная с 0)
    """
    # Получаем активных пользователей и их источники
    sources = {}
    active_users = await get_all_users(status="active")
    
    # Собираем уникальные источники и количество пользователей
    for user in active_users:
        source = user.get("source", "Неизвестно")
        if source not in sources:
            sources[source] = 0
        sources[source] += 1
    
    # Сортируем источники по количеству пользователей (от большего к меньшему)
    sorted_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)
    
    # Конфигурация пагинации
    SOURCES_PER_PAGE = 5  # Количество источников на одной странице
    total_pages = max(1, (len(sorted_sources) + SOURCES_PER_PAGE - 1) // SOURCES_PER_PAGE)
    
    # Проверяем, нужна ли пагинация
    pagination_needed = len(sorted_sources) > SOURCES_PER_PAGE
    
    # Ограничиваем страницы доступным диапазоном
    page = max(0, min(page, total_pages - 1))
    
    # Выбираем источники для текущей страницы
    start_idx = page * SOURCES_PER_PAGE
    end_idx = min(start_idx + SOURCES_PER_PAGE, len(sorted_sources))
    current_page_sources = sorted_sources[start_idx:end_idx]
    
    # Создаем клавиатуру
    keyboard = types.InlineKeyboardMarkup()
    
    # Добавляем кнопку "Все пользователи" только на первой странице
    if page == 0:
        keyboard.add(types.InlineKeyboardButton("Все пользователи", callback_data="schedule_target_all"))
    
    # Добавляем кнопки источников
    for source, count in current_page_sources:
        if source:  # Игнорируем пустые источники
            keyboard.add(types.InlineKeyboardButton(
                f"{source} ({count} пользователей)", 
                callback_data=f"schedule_target_source_{source}"
            ))
    
    # Добавляем кнопки навигации, если нужна пагинация
    if pagination_needed:
        nav_buttons = []
        
        # Кнопка "Назад"
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("◀️ Назад", callback_data=f"schedule_target_page_{page-1}"))
        
        # Информация о текущей странице
        page_info = f"{page+1}/{total_pages}"
        nav_buttons.append(types.InlineKeyboardButton(page_info, callback_data="schedule_target_page_info"))
        
        # Кнопка "Вперед"
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Вперед ▶️", callback_data=f"schedule_target_page_{page+1}"))
            
        keyboard.row(*nav_buttons)
    
    # Отправляем сообщение с клавиатурой
    message_text = "Выберите целевую аудиторию для запланированной рассылки:"
    
    # Проверяем, это новое сообщение или обновление существующего
    if isinstance(message, types.Message):
        await message.answer(message_text, reply_markup=keyboard)
    else:
        await message.edit_text(message_text, reply_markup=keyboard)
    
    await BroadcastStates.waiting_for_scheduled_target.set()

async def process_scheduled_target_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает пагинацию при выборе целевой аудитории для запланированной рассылки
    """
    await callback_query.answer()
    
    # Извлекаем номер страницы из данных колбэка
    page_data = callback_query.data
    if page_data == "schedule_target_page_info":
        # Это нажатие на номер страницы, игнорируем
        return
    
    # Формат: "schedule_target_page_X"
    page = int(page_data.split("_")[3])
    
    # Показываем выбранную страницу
    await show_scheduled_target_selection(callback_query.message, state, page)

async def process_scheduled_broadcast_target(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор целевой аудитории для запланированной рассылки
    """
    await callback_query.answer()
    
    target_data = callback_query.data
    target_filter = None
    target_description = "всем пользователям"
    
    if target_data.startswith("schedule_target_source_"):
        source = target_data[23:]  # Вырезаем префикс "schedule_target_source_"
        target_filter = {"source": source}
        target_description = f"пользователям из источника '{source}'"
        logging.info(f"Выбрана целевая аудитория для запланированной рассылки: пользователи из источника '{source}'")
    else:
        logging.info("Выбрана целевая аудитория для запланированной рассылки: все пользователи")
    
    async with state.proxy() as data:
        data["target_filter"] = target_filter
        data["target_description"] = target_description
        
        # Для логирования количества пользователей
        if target_filter:
            # Всегда добавляем статус "active"
            combined_filter = target_filter.copy()
            combined_filter["status"] = "active"
            users = await get_users_by_filter(combined_filter)
        else:
            users = await get_all_users(status="active")
        
        logging.info(f"Найдено {len(users)} активных пользователей для запланированной рассылки с фильтром: {target_filter}")
    
    # Переходим к вводу времени отправки
    await callback_query.message.answer(
        "Введите время отправки рассылки в формате 'ДД.ММ.ГГГГ ЧЧ:ММ' (по Московскому времени), например: 31.12.2023 15:30.\n\n"
        "Внимание: время должно быть указано именно в московском часовом поясе (МСК, UTC+3)."
    )
    await BroadcastStates.waiting_for_schedule_time.set()

async def process_schedule_time(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод времени для запланированной рассылки
    """
    try:
        # Парсим дату и время из сообщения
        schedule_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        
        # Получаем текущее время в московском часовом поясе для корректного сравнения
        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time_moscow = datetime.now(pytz.UTC).astimezone(moscow_tz).replace(tzinfo=None)
        
        # Проверяем, что дата в будущем (сравниваем московское время с московским)
        if schedule_time <= current_time_moscow:
            await message.answer("Пожалуйста, укажите дату и время в будущем (московское время). Текущее московское время: " + 
                                current_time_moscow.strftime('%d.%m.%Y %H:%M') + ". Попробуйте еще раз:")
            return
        
        async with state.proxy() as data:
            data["schedule_time"] = schedule_time
            target_description = data.get("target_description", "всем пользователям")
            
            # Получаем количество активных пользователей для рассылки
            target_filter = data.get("target_filter")
            if target_filter:
                # Всегда добавляем статус "active"
                combined_filter = target_filter.copy()
                combined_filter["status"] = "active"
                users = await get_users_by_filter(combined_filter)
            else:
                users = await get_all_users(status="active")
            
            # Формируем сообщение для подтверждения
            confirmation_message = (
                f"Вы собираетесь запланировать отправку следующего сообщения {target_description} "
                f"(всего {len(users)} пользователей) на {schedule_time.strftime('%d.%m.%Y в %H:%M')} (по Московскому времени):\n\n"
                f"{data['message_text']}"
            )
            
            # Добавляем информацию о медиа, если есть
            if "media" in data and "media_type" in data:
                media_type_text = {
                    "photo": "фотографией",
                    "video": "видео",
                    "animation": "GIF-анимацией"
                }.get(data["media_type"], "медиа")
                
                confirmation_message += f"\n\nСообщение будет отправлено с {media_type_text}."
            
            confirmation_message += "\n\nПодтвердите планирование (да/нет):"
        
        await message.answer(confirmation_message)
        await BroadcastStates.waiting_for_schedule_confirmation.set()
    
    except ValueError:
        await message.answer(
            "Неверный формат даты и времени. Пожалуйста, используйте формат 'ДД.ММ.ГГГГ ЧЧ:ММ' (по Московскому времени), например: 31.12.2023 15:30"
        )

async def process_schedule_confirmation(message: types.Message, state: FSMContext):
    """
    Обрабатывает подтверждение планирования рассылки
    """
    if message.text.lower() in ["да", "yes", "y", "д"]:
        async with state.proxy() as data:
            message_text = data["message_text"]
            schedule_time = data["schedule_time"]
            target_filter = data.get("target_filter")
            target_description = data.get("target_description", "всем пользователям")
            media = data.get("media")
            media_type = data.get("media_type")
        
        # Планируем рассылку
        broadcast_id = await schedule_broadcast(
            bot=message.bot,
            message_text=message_text,
            schedule_time=schedule_time,
            target_filter=target_filter,
            media=media,
            media_type=media_type
        )
        
        # Отправляем подтверждение
        result_message = (
            f"✅ Рассылка успешно запланирована.\n\n"
            f"Сообщение будет отправлено {target_description} "
            f"{schedule_time.strftime('%d.%m.%Y в %H:%M')} (по Московскому времени)\n\n"
            f"ID рассылки: {broadcast_id}"
        )
        
        await message.answer(result_message)
    else:
        await message.answer("Планирование рассылки отменено.")
    
    await state.finish()

def register_admin_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков команд администратора
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    # Фильтр для проверки, является ли пользователь администратором
    admin_filter = IDFilter(user_id=ADMIN_USER_IDS)
    
    # Команды и обработчики
    dp.register_message_handler(admin_start, admin_filter, commands=["admin"], state="*")
    dp.register_message_handler(show_statistics, admin_filter, Text(equals="📊 Статистика"), state="*")
    
    # Обработчики для создания пригласительных ссылок
    dp.register_message_handler(create_invite_link_cmd, admin_filter, Text(equals="🔗 Создать ссылку"), state="*")
    dp.register_message_handler(process_invite_link_source, admin_filter, state=InviteLinkStates.waiting_for_source)
    dp.register_message_handler(process_invite_link_description, admin_filter, state=InviteLinkStates.waiting_for_description)
    dp.register_message_handler(process_invite_link_expire_date, admin_filter, state=InviteLinkStates.waiting_for_expire_date)
    
    # Обработчики для создания рассылок
    dp.register_message_handler(create_broadcast_cmd, admin_filter, Text(equals="📨 Создать рассылку"), state="*")
    dp.register_message_handler(process_broadcast_message, admin_filter, state=BroadcastStates.waiting_for_message)
    dp.register_callback_query_handler(process_broadcast_media_choice, admin_filter, 
                                      lambda c: c.data.startswith("media_"), 
                                      state=BroadcastStates.waiting_for_media)
    dp.register_message_handler(process_broadcast_media, admin_filter, 
                              content_types=types.ContentTypes.ANY,
                              state=BroadcastStates.waiting_for_media)
    # Обработчик пагинации для целевой аудитории
    dp.register_callback_query_handler(process_target_pagination, admin_filter, 
                                      lambda c: c.data.startswith("target_page_"), 
                                      state=BroadcastStates.waiting_for_target)
    dp.register_callback_query_handler(process_broadcast_target, admin_filter, 
                                      lambda c: c.data.startswith("target_") and not c.data.startswith("target_page_"), 
                                      state=BroadcastStates.waiting_for_target)
    dp.register_message_handler(process_broadcast_confirmation, admin_filter, state=BroadcastStates.waiting_for_confirmation)
    
    # Обработчики для запланированных рассылок
    dp.register_message_handler(schedule_broadcast_cmd, admin_filter, Text(equals="📅 Запланировать рассылку"), state="*")
    dp.register_message_handler(process_scheduled_broadcast_message, admin_filter, 
                               state=BroadcastStates.waiting_for_scheduled_message)
    dp.register_callback_query_handler(process_scheduled_broadcast_media_choice, admin_filter, 
                                      lambda c: c.data.startswith("schedule_media_"), 
                                      state=BroadcastStates.waiting_for_scheduled_media)
    dp.register_message_handler(process_scheduled_broadcast_media, admin_filter, 
                              content_types=types.ContentTypes.ANY,
                              state=BroadcastStates.waiting_for_scheduled_media)
    # Обработчик пагинации для целевой аудитории запланированной рассылки
    dp.register_callback_query_handler(process_scheduled_target_pagination, admin_filter, 
                                      lambda c: c.data.startswith("schedule_target_page_"), 
                                      state=BroadcastStates.waiting_for_scheduled_target)
    dp.register_callback_query_handler(process_scheduled_broadcast_target, admin_filter, 
                                      lambda c: c.data.startswith("schedule_target_") and not c.data.startswith("schedule_target_page_"), 
                                      state=BroadcastStates.waiting_for_scheduled_target)
    dp.register_message_handler(process_schedule_time, admin_filter, state=BroadcastStates.waiting_for_schedule_time)
    dp.register_message_handler(process_schedule_confirmation, admin_filter, state=BroadcastStates.waiting_for_schedule_confirmation) 