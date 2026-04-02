"""
Хендлеры конкурсов: админский флоу (создание/управление) и пользовательский (участие)
"""

import logging
import uuid
from datetime import datetime

import pytz
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text, IDFilter
from aiogram.dispatcher.filters.state import State, StatesGroup

from bot.config.config import ADMIN_USER_IDS
from bot.database.contests import (
    add_participant,
    create_contest,
    delete_contest,
    delete_contest_participants,
    get_active_contests,
    get_contest,
    get_contest_participants,
)
from bot.database.users import get_user, update_user
from bot.services.contests import (
    delete_contest_channel_message,
    notify_winner,
    pick_winner,
    publish_contest_to_channel,
    publish_winner_to_channel,
    validate_participation,
)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def _utc_to_msk_str(dt: datetime) -> str:
    utc_aware = pytz.UTC.localize(dt)
    return utc_aware.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")


# ---------------------------------------------------------------------------
# FSM-состояния
# ---------------------------------------------------------------------------

class ContestCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_end_time = State()
    waiting_for_photo = State()
    waiting_for_confirmation = State()


class ContestParticipation(StatesGroup):
    waiting_for_city = State()
    waiting_for_car_model = State()


CONTEST_CAR_MODEL = "Tank 300"


# ---------------------------------------------------------------------------
# Админ: меню конкурсов
# ---------------------------------------------------------------------------

async def contests_menu(message: types.Message, state: FSMContext) -> None:
    await state.finish()
    contests = await get_active_contests()

    text = "🎉 Активные конкурсы:\n\n"
    if not contests:
        text += "Нет активных конкурсов.\n"
    else:
        for c in contests:
            end_str = _utc_to_msk_str(c["end_time"])
            text += (
                f"• {c['title']}\n"
                f"  Участников: {c.get('participants_count', 0)} | Приём заявок до: {end_str} МСК\n\n"
            )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("➕ Создать конкурс", callback_data="contest_create"))

    for c in contests:
        keyboard.add(
            types.InlineKeyboardButton(
                f"🏆 {c['title']}", callback_data=f"contest_manage_{c['contest_id']}"
            )
        )

    await message.answer(text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Админ: создание конкурса
# ---------------------------------------------------------------------------

async def contest_create_start(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    await callback_query.message.answer("Введите название конкурса:")
    await ContestCreation.waiting_for_title.set()


async def contest_create_title(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["title"] = message.text.strip()
    await message.answer("Введите описание конкурса (приз, условия и т.д.):")
    await ContestCreation.waiting_for_description.set()


async def contest_create_description(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["description"] = message.text.strip()
    await message.answer(
        "Введите дату и время окончания приёма заявок в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "*Время указывается по московскому времени (МСК).*\n\n"
        "После этого времени участие будет закрыто. Итоги подводятся вручную через кнопку «Выбрать победителя».",
        parse_mode=types.ParseMode.MARKDOWN,
    )
    await ContestCreation.waiting_for_end_time.set()


async def contest_create_end_time(message: types.Message, state: FSMContext) -> None:
    try:
        naive_msk = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ ЧЧ:ММ, например: 31.12.2026 18:00")
        return

    now_msk = datetime.now(pytz.UTC).astimezone(MOSCOW_TZ).replace(tzinfo=None)
    if naive_msk <= now_msk:
        await message.answer(
            f"Дата должна быть в будущем. Сейчас по МСК: {now_msk.strftime('%d.%m.%Y %H:%M')}. Попробуйте ещё раз:"
        )
        return

    # Конвертируем МСК → UTC для хранения
    msk_aware = MOSCOW_TZ.localize(naive_msk)
    end_time_utc = msk_aware.astimezone(pytz.UTC).replace(tzinfo=None)

    async with state.proxy() as data:
        data["end_time_utc"] = end_time_utc
        data["end_time_display"] = naive_msk.strftime("%d.%m.%Y %H:%M")

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Без картинки", callback_data="contest_photo_skip"))

    await message.answer(
        "🖼 Отправьте картинку для поста конкурса или нажмите кнопку ниже:",
        reply_markup=keyboard,
    )
    await ContestCreation.waiting_for_photo.set()


async def _show_contest_confirmation(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        photo_info = "Да ✅" if data.get("photo_file_id") else "Нет"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="contest_confirm_create"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="contest_cancel_create"),
        )
        await message.answer(
            f"Подтверждение создания конкурса:\n\n"
            f"Название: {data['title']}\n"
            f"Описание: {data['description']}\n"
            f"Приём заявок до: {data['end_time_display']} МСК\n"
            f"Картинка: {photo_info}\n\n"
            "Всё верно?",
            reply_markup=keyboard,
        )
    await ContestCreation.waiting_for_confirmation.set()


async def contest_photo_received(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["photo_file_id"] = message.photo[-1].file_id
    await message.answer("Картинка сохранена ✅")
    await _show_contest_confirmation(message, state)


async def contest_photo_skip(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    async with state.proxy() as data:
        data["photo_file_id"] = None
    await _show_contest_confirmation(callback_query.message, state)


async def contest_confirm_create(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()

    async with state.proxy() as data:
        title = data["title"]
        description = data["description"]
        end_time_utc = data["end_time_utc"]
        end_time_display = data["end_time_display"]
        photo_file_id = data.get("photo_file_id")

    contest_id = str(uuid.uuid4())[:8]
    contest = await create_contest(
        contest_id=contest_id,
        title=title,
        description=description,
        end_time=end_time_utc,
        created_by=callback_query.from_user.id,
        photo_file_id=photo_file_id,
    )

    await state.finish()

    bot_me = await callback_query.bot.get_me()
    deep_link = f"https://t.me/{bot_me.username}?start=contest_{contest_id}"

    await callback_query.message.answer(
        f"✅ Конкурс «{title}» создан!\n\n"
        f"ID: {contest_id}\n"
        f"Приём заявок до: {end_time_display} МСК\n\n"
        f"Ссылка для участия:\n{deep_link}\n\n"
        "Используйте эту ссылку на любых ресурсах. "
        "Для публикации в Telegram-канал нажмите кнопку в карточке конкурса.",
    )


async def contest_cancel_create(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.finish()
    await callback_query.message.answer("Создание конкурса отменено.")


# ---------------------------------------------------------------------------
# Админ: управление конкурсом
# ---------------------------------------------------------------------------

async def contest_manage(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_manage_", "")
    contest = await get_contest(contest_id)
    if not contest:
        await callback_query.message.answer("Конкурс не найден.")
        return

    participants = await get_contest_participants(contest_id)
    end_str = _utc_to_msk_str(contest["end_time"])

    text = (
        f"🎉 {contest['title']}\n\n"
        f"Описание: {contest['description']}\n"
        f"Приём заявок до: {end_str} МСК\n"
        f"Статус: {contest['status']}\n"
        f"Участников: {len(participants)}\n\n"
        f"ℹ️ Итоги подводятся вручную кнопкой «Выбрать победителя».\n"
    )

    if contest.get("winner_user_id"):
        text += f"\n🏆 Победитель: {contest['winner_user_id']}"

    keyboard = types.InlineKeyboardMarkup()
    if contest["status"] == "active":
        if not contest.get("channel_message_id"):
            keyboard.add(
                types.InlineKeyboardButton(
                    "📢 Опубликовать в канал", callback_data=f"contest_publish_{contest_id}"
                )
            )
        keyboard.add(
            types.InlineKeyboardButton(
                "🎲 Выбрать победителя", callback_data=f"contest_pick_{contest_id}"
            )
        )

    keyboard.add(
        types.InlineKeyboardButton("🗑 Удалить конкурс", callback_data=f"contest_delete_{contest_id}")
    )
    keyboard.add(
        types.InlineKeyboardButton("◀️ Назад к списку", callback_data="contest_back_to_list")
    )

    await callback_query.message.edit_text(text, reply_markup=keyboard)


async def contest_back_to_list(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await contests_menu(callback_query.message, state)


async def contest_publish_to_channel(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_publish_", "")
    contest = await get_contest(contest_id)
    if not contest:
        await callback_query.message.answer("Конкурс не найден.")
        return

    bot_me = await callback_query.bot.get_me()
    msg_id = await publish_contest_to_channel(callback_query.bot, contest, bot_me.username)

    if msg_id:
        await callback_query.message.answer(f"✅ Конкурс «{contest['title']}» опубликован в канале!")
    else:
        await callback_query.message.answer("Не удалось опубликовать в канал.")


async def contest_pick_winner_prompt(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_pick_", "")

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Да, выбрать", callback_data=f"contest_pick_confirm_{contest_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"contest_manage_{contest_id}"),
    )
    await callback_query.message.edit_text(
        "Вы уверены, что хотите выбрать победителя? Конкурс будет завершён.",
        reply_markup=keyboard,
    )


async def contest_pick_winner_confirm(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_pick_confirm_", "")
    contest = await get_contest(contest_id)
    if not contest:
        await callback_query.message.answer("Конкурс не найден.")
        return

    winner = await pick_winner(contest_id)
    if not winner:
        await callback_query.message.answer("В конкурсе нет участников, невозможно выбрать победителя.")
        return

    updated_contest = await get_contest(contest_id)

    winner_name = winner.get("first_name") or winner.get("username") or str(winner["user_id"])

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("📢 Опубликовать результат в канал", callback_data=f"contest_publish_result_{contest_id}")
    )
    keyboard.add(
        types.InlineKeyboardButton("◀️ Назад к списку", callback_data="contest_back_to_list")
    )

    await callback_query.message.answer(
        f"🏆 Победитель конкурса «{contest['title']}»:\n\n"
        f"Имя: {winner_name}\n"
        f"Username: @{winner.get('username', 'нет')}\n"
        f"Город: {winner.get('city', '—')}\n"
        f"Машина: {winner.get('car_model', '—')}\n"
        f"User ID: {winner['user_id']}\n\n"
        "Победитель уведомлён личным сообщением.",
        reply_markup=keyboard,
    )

    await notify_winner(callback_query.bot, winner, updated_contest)


async def contest_publish_result(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_publish_result_", "")
    contest = await get_contest(contest_id)
    if not contest or not contest.get("winner_user_id"):
        await callback_query.message.answer("Конкурс или победитель не найдены.")
        return

    from bot.database.contests import get_participant
    winner = await get_participant(contest_id, contest["winner_user_id"])
    if not winner:
        await callback_query.message.answer("Данные победителя не найдены.")
        return

    result = await publish_winner_to_channel(callback_query.bot, contest, winner)
    if result:
        await callback_query.message.answer(f"✅ Результат конкурса «{contest['title']}» опубликован в канале!")
    else:
        await callback_query.message.answer("Не удалось опубликовать результат в канал.")


# ---------------------------------------------------------------------------
# Админ: удаление конкурса
# ---------------------------------------------------------------------------

async def contest_delete_prompt(callback_query: types.CallbackQuery) -> None:
    """Показывает диалог подтверждения удаления конкурса."""
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_delete_", "")
    contest = await get_contest(contest_id)
    if not contest:
        await callback_query.message.answer("Конкурс не найден.")
        return

    participants = await get_contest_participants(contest_id)
    channel_info = ""
    if contest.get("channel_message_id"):
        channel_info = "\nПост конкурса в канале будет удалён."

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"contest_delete_confirm_{contest_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"contest_manage_{contest_id}"),
    )
    await callback_query.message.edit_text(
        f"Вы уверены, что хотите удалить конкурс «{contest['title']}»?\n"
        f"Участников: {len(participants)}{channel_info}\n\n"
        "Это действие необратимо.",
        reply_markup=keyboard,
    )


async def contest_delete_confirm(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Выполняет удаление конкурса, его участников и поста в канале."""
    await callback_query.answer()
    contest_id = callback_query.data.replace("contest_delete_confirm_", "")
    contest = await get_contest(contest_id)
    if not contest:
        await callback_query.message.answer("Конкурс не найден.")
        return

    title = contest["title"]

    await delete_contest_channel_message(callback_query.bot, contest)
    deleted_participants = await delete_contest_participants(contest_id)
    await delete_contest(contest_id)

    logging.info(f"Конкурс «{title}» ({contest_id}) удалён админом {callback_query.from_user.id}")

    await callback_query.message.edit_text(
        f"🗑 Конкурс «{title}» удалён.\n"
        f"Удалено участников: {deleted_participants}",
    )
    await contests_menu(callback_query.message, state)


# ---------------------------------------------------------------------------
# Юзер: участие в конкурсе — запуск из deep link
# ---------------------------------------------------------------------------

async def start_contest_participation(
    message: types.Message,
    state: FSMContext,
    contest_id: str,
) -> None:
    """Точка входа для участия: вызывается из start_cmd при deep link contest_*"""
    validation = await validate_participation(message.from_user.id, contest_id, message.bot)
    if not validation.is_valid:
        await message.answer(validation.error_message)
        return

    user_data = await get_user(message.from_user.id)
    user_city = user_data.get("city") if user_data else None

    async with state.proxy() as data:
        data["contest_id"] = contest_id

    if not user_city:
        await state.set_state(ContestParticipation.waiting_for_city.state)

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        cities = [
            "Москва", "Красноярск", "Санкт-Петербург", "Калининград",
            "Сочи", "Астрахань", "Казань", "Екатеринбург",
        ]
        for city in cities:
            keyboard.add(types.InlineKeyboardButton(city, callback_data=f"contest_city_{city}"))
        keyboard.add(types.InlineKeyboardButton("Другой", callback_data="contest_city_other"))

        await message.answer(
            "📍 Для участия в конкурсе укажите ваш город:",
            reply_markup=keyboard,
        )
        return

    async with state.proxy() as data:
        data["city"] = user_city
    await ContestParticipation.waiting_for_car_model.set()
    await _ask_car_model(message)


# ---------------------------------------------------------------------------
# Юзер: обработка города (для участия в конкурсе)
# ---------------------------------------------------------------------------

async def contest_city_button(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    current_state = await state.get_state()
    if current_state != ContestParticipation.waiting_for_city.state:
        return

    city_data = callback_query.data.replace("contest_city_", "")
    if city_data == "other":
        await callback_query.message.edit_text("✍️ Введите ваш город текстом:")
        return

    user_id = callback_query.from_user.id
    await update_user(user_id, {"city": city_data})

    async with state.proxy() as data:
        data["city"] = city_data

    await ContestParticipation.waiting_for_car_model.set()
    await callback_query.message.edit_text(f"Город: {city_data} ✅")
    await _ask_car_model(callback_query.message)


async def contest_city_text(message: types.Message, state: FSMContext) -> None:
    city = message.text.strip()
    user_id = message.from_user.id
    await update_user(user_id, {"city": city})

    async with state.proxy() as data:
        data["city"] = city

    await ContestParticipation.waiting_for_car_model.set()
    await message.answer(f"Город: {city} ✅")
    await _ask_car_model(message)


# ---------------------------------------------------------------------------
# Юзер: выбор модели машины → сохранение участника
# ---------------------------------------------------------------------------

async def _ask_car_model(message: types.Message) -> None:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(f"🚗 {CONTEST_CAR_MODEL}", callback_data="contest_car_tank300"))
    keyboard.add(types.InlineKeyboardButton("Другой автомобиль", callback_data="contest_car_other"))
    await message.answer("🚗 Выберите ваш автомобиль:", reply_markup=keyboard)


async def contest_car_model_selected(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()

    if callback_query.data == "contest_car_other":
        await state.finish()
        await callback_query.message.edit_text(
            "К сожалению, в данном конкурсе могут участвовать только владельцы Tank 300."
        )
        return

    user = callback_query.from_user
    car_model = CONTEST_CAR_MODEL

    async with state.proxy() as data:
        contest_id = data["contest_id"]
        city = data.get("city", "")

    validation = await validate_participation(user.id, contest_id, callback_query.bot)
    if not validation.is_valid:
        await state.finish()
        await callback_query.message.edit_text(validation.error_message)
        return

    await add_participant(
        contest_id=contest_id,
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        car_model=car_model,
        city=city,
    )

    await state.finish()

    contest = await get_contest(contest_id)
    title = contest["title"] if contest else "конкурс"
    await callback_query.message.edit_text(
        f"🎉 Отлично! Вы участвуете в конкурсе «{title}»!\n\n"
        f"Город: {city}\nАвтомобиль: {car_model}\n\n"
        "Ожидайте результатов розыгрыша. Удачи!",
    )
    logging.info(f"Пользователь {user.id} зарегистрирован в конкурсе {contest_id}")


# ---------------------------------------------------------------------------
# Регистрация хендлеров
# ---------------------------------------------------------------------------

def register_contest_handlers(dp: Dispatcher) -> None:
    admin_filter = IDFilter(user_id=ADMIN_USER_IDS)

    # --- Админ: меню конкурсов ---
    dp.register_message_handler(
        contests_menu, admin_filter, Text(equals="🎯 Конкурсы"), state="*"
    )

    # --- Админ: создание конкурса ---
    dp.register_callback_query_handler(
        contest_create_start, admin_filter,
        lambda c: c.data == "contest_create", state="*",
    )
    dp.register_message_handler(
        contest_create_title, admin_filter,
        state=ContestCreation.waiting_for_title,
    )
    dp.register_message_handler(
        contest_create_description, admin_filter,
        state=ContestCreation.waiting_for_description,
    )
    dp.register_message_handler(
        contest_create_end_time, admin_filter,
        state=ContestCreation.waiting_for_end_time,
    )
    dp.register_message_handler(
        contest_photo_received, admin_filter,
        content_types=types.ContentTypes.PHOTO,
        state=ContestCreation.waiting_for_photo,
    )
    dp.register_callback_query_handler(
        contest_photo_skip, admin_filter,
        lambda c: c.data == "contest_photo_skip",
        state=ContestCreation.waiting_for_photo,
    )
    dp.register_callback_query_handler(
        contest_confirm_create, admin_filter,
        lambda c: c.data == "contest_confirm_create",
        state=ContestCreation.waiting_for_confirmation,
    )
    dp.register_callback_query_handler(
        contest_cancel_create, admin_filter,
        lambda c: c.data == "contest_cancel_create",
        state=ContestCreation.waiting_for_confirmation,
    )

    # --- Админ: удаление конкурса ---
    dp.register_callback_query_handler(
        contest_delete_confirm, admin_filter,
        lambda c: c.data.startswith("contest_delete_confirm_"), state="*",
    )
    dp.register_callback_query_handler(
        contest_delete_prompt, admin_filter,
        lambda c: c.data.startswith("contest_delete_") and not c.data.startswith("contest_delete_confirm_"),
        state="*",
    )

    # --- Админ: управление конкурсом ---
    dp.register_callback_query_handler(
        contest_manage, admin_filter,
        lambda c: c.data.startswith("contest_manage_"), state="*",
    )
    dp.register_callback_query_handler(
        contest_back_to_list, admin_filter,
        lambda c: c.data == "contest_back_to_list", state="*",
    )
    dp.register_callback_query_handler(
        contest_publish_result, admin_filter,
        lambda c: c.data.startswith("contest_publish_result_"), state="*",
    )
    dp.register_callback_query_handler(
        contest_publish_to_channel, admin_filter,
        lambda c: c.data.startswith("contest_publish_") and not c.data.startswith("contest_publish_result_"),
        state="*",
    )
    dp.register_callback_query_handler(
        contest_pick_winner_prompt, admin_filter,
        lambda c: c.data.startswith("contest_pick_") and not c.data.startswith("contest_pick_confirm_"),
        state="*",
    )
    dp.register_callback_query_handler(
        contest_pick_winner_confirm, admin_filter,
        lambda c: c.data.startswith("contest_pick_confirm_"), state="*",
    )

    # --- Юзер: участие в конкурсе (FSM) ---
    dp.register_callback_query_handler(
        contest_city_button,
        lambda c: c.data.startswith("contest_city_"),
        state=ContestParticipation.waiting_for_city,
    )
    dp.register_message_handler(
        contest_city_text,
        state=ContestParticipation.waiting_for_city,
        content_types=types.ContentTypes.TEXT,
    )
    dp.register_callback_query_handler(
        contest_car_model_selected,
        lambda c: c.data.startswith("contest_car_"),
        state=ContestParticipation.waiting_for_car_model,
    )
