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
    waiting_for_target = State()
    waiting_for_scheduled_target = State()  # Отдельное состояние для выбора цели в запланированной рассылке
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
    
    # Добавляем выбор таргетированной аудитории
    sources = {}
    active_users = await get_all_users(status="active")
    
    # Собираем уникальные источники
    for user in active_users:
        source = user.get("source", "Неизвестно")
        if source not in sources:
            sources[source] = 0
        sources[source] += 1
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Все пользователи", callback_data="target_all"))
    
    for source, count in sources.items():
        if source:  # Игнорируем пустые источники
            keyboard.add(types.InlineKeyboardButton(
                f"{source} ({count} пользователей)", 
                callback_data=f"target_source_{source}"
            ))
    
    await message.answer(
        "Выберите целевую аудиторию для рассылки:",
        reply_markup=keyboard
    )
    await BroadcastStates.waiting_for_target.set()

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
        
        confirmation_message = (
            f"Вы собираетесь отправить следующее сообщение {target_description} "
            f"(всего {len(users)} активных пользователей):\n\n"
            f"{data['message_text']}\n\n"
            f"Подтвердите отправку (да/нет):"
        )
    
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
        
        # Отправляем уведомление о начале рассылки
        await message.answer(f"Рассылка {target_description} начата. Это может занять некоторое время...")
        
        # Выполняем рассылку
        stats = await send_broadcast(message.bot, message_text, target_filter)
        
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
    # Этот обработчик аналогичен process_broadcast_message,
    # но ведет к выбору времени отправки
    async with state.proxy() as data:
        data["message_text"] = message.text
        
    # Добавляем выбор таргетированной аудитории (аналогично обычной рассылке)
    sources = {}
    active_users = await get_all_users(status="active")
    
    # Собираем уникальные источники
    for user in active_users:
        source = user.get("source", "Неизвестно")
        if source not in sources:
            sources[source] = 0
        sources[source] += 1
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Все пользователи", callback_data="schedule_target_all"))
    
    for source, count in sources.items():
        if source:  # Игнорируем пустые источники
            keyboard.add(types.InlineKeyboardButton(
                f"{source} ({count} пользователей)", 
                callback_data=f"schedule_target_source_{source}"
            ))
    
    await message.answer(
        "Выберите целевую аудиторию для запланированной рассылки:",
        reply_markup=keyboard
    )
    await BroadcastStates.waiting_for_scheduled_target.set()

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
            
            # Получаем количество пользователей
            if data.get("target_filter"):
                users = await get_users_by_filter(data["target_filter"])
            else:
                users = await get_all_users(status="active")
            
            confirmation_message = (
                f"Вы собираетесь запланировать отправку следующего сообщения {target_description} "
                f"(всего {len(users)} пользователей) на {schedule_time.strftime('%d.%m.%Y %H:%M')} (по Московскому времени):\n\n"
                f"{data['message_text']}\n\n"
                f"Подтвердите планирование (да/нет):"
            )
        
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
        
        # Планируем рассылку
        broadcast_id = await schedule_broadcast(
            message.bot,
            message_text,
            schedule_time,
            target_filter
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
    dp.register_callback_query_handler(process_broadcast_target, admin_filter, 
                                      lambda c: c.data.startswith("target_"), 
                                      state=BroadcastStates.waiting_for_target)
    dp.register_message_handler(process_broadcast_confirmation, admin_filter, state=BroadcastStates.waiting_for_confirmation)
    
    # Обработчики для запланированных рассылок
    dp.register_message_handler(schedule_broadcast_cmd, admin_filter, Text(equals="📅 Запланировать рассылку"), state="*")
    dp.register_message_handler(process_scheduled_broadcast_message, admin_filter, 
                               state=BroadcastStates.waiting_for_scheduled_message)
    dp.register_callback_query_handler(process_scheduled_broadcast_target, admin_filter, 
                                      lambda c: c.data.startswith("schedule_target_"), 
                                      state=BroadcastStates.waiting_for_scheduled_target)
    dp.register_message_handler(process_schedule_time, admin_filter, state=BroadcastStates.waiting_for_schedule_time)
    dp.register_message_handler(process_schedule_confirmation, admin_filter, state=BroadcastStates.waiting_for_schedule_confirmation) 