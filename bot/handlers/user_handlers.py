"""
Обработчики команд для обычных пользователей бота
"""

import logging
from datetime import datetime
from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import CommandStart, Command
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ContentType,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.database import add_user, update_user
from bot.utils.send_email import send_consultation_email
from bot.utils.menu import get_main_menu


class ConsultationForm(StatesGroup):
    """
    Состояния для сценария консультации (заявка менеджеру).
    """

    waiting_for_question = State()
    waiting_for_phone = State()
    waiting_for_call_time = State()

async def start_cmd(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start
    
    Args:
        message (types.Message): Сообщение пользователя
        state (FSMContext): Состояние FSM
    """
    user = message.from_user
    
    # Сохраняем или обновляем пользователя в базе данных
    await add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        status="active"  # Пользователи открытого канала сразу активны
    )
    
    # Обновляем время последнего взаимодействия
    await update_user(user.id, {"last_interaction": datetime.utcnow()})
    
    # Проверяем аргументы команды для определения источника
    args = message.get_args()
    logging.info(f"Пользователь {user.id} запустил бота с аргументами: '{args}'")
    source = None
    if args and args.startswith('link_'):
        link_id = args.replace('link_', '')
        logging.info(f"Определен link_id: {link_id}")
        from bot.database import get_source_by_link
        source = await get_source_by_link(link_id)
        logging.info(f"Получен источник: {source}")
        if source:
            # Обновляем источник пользователя
            await update_user(user.id, {"source": source})
            logging.info(f"Пользователь {user.id} пришел по ссылке с источником: {source}")
        else:
            logging.warning(f"Источник не найден для link_id: {link_id}")
    else:
        logging.info(f"Пользователь {user.id} запустил бота без параметра link_")
    
    # Отправляем приветственное сообщение
    from bot.config.config import CHANNEL_USERNAME
    
    welcome_text = f"""👋 Добро пожаловать в официальный Telegram-бот Arctic Trucks Россия.

📢 Подписывайтесь на наш канал: https://t.me/arctictrucksru

Здесь мы рассказываем обо всём, что связано с автомобилями Arctic Trucks — техникой, которая создана для самых сложных дорог и условий."""

    await message.answer(welcome_text, reply_markup=get_main_menu())
    
    # Предложение указать город
    city_keyboard = InlineKeyboardMarkup()
    city_keyboard.add(InlineKeyboardButton('🏙️ Указать город', callback_data='set_city'))
    
    await message.answer(
        "💡 Из какого города Вы с нами? Нам важно знать, из каких уголков России и мира наши подписчики",
        reply_markup=city_keyboard
    )

async def help_cmd(message: types.Message):
    """
    Обработчик команды /help
    """
    # Обновляем время последнего взаимодействия
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    
    text = (
        "Я бот для управления открытым каналом. Вот что я умею:\n\n"
        "- Отправлять уведомления о новых материалах\n"
        "- Предоставлять консультации\n\n"
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
        "Это открытый канал с эксклюзивным контентом.\n\n"
        "Вы можете подписаться на канал и получать уведомления о новых материалах."
    )
    
    await message.answer(text)

async def available_cmd(message: types.Message) -> None:
    """
    Обработчик команды /available
    """
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    await message.answer(
        "👉 Хотите узнать больше о моделях в наличии? Переходите на сайт https://arctictrucks.ru/auto-in-stock/"
    )

async def shop_cmd(message: types.Message) -> None:
    """
    Обработчик команды /shop
    """
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    await message.answer(
        "👉 Полезное внедорожное оборудование и запчасти! Подробности https://arctictrucks.ru/equip/"
    )

async def configurator_cmd(message: types.Message) -> None:
    """
    Обработчик команды /configurator
    """
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    await message.answer(
        "👉 Хотите собрать свой Arctic Trucks под индивидуальные задачи? Переходите на сайт https://arctictrucks.ru/configurator/"
    )


async def start_consultation_flow(
    message: types.Message,
    state: FSMContext,
) -> None:
    """
    Запускает сценарий консультации: задает первый вопрос и переводит
    пользователя в состояние ожидания текста вопроса.
    """
    # Сбрасываем предыдущие состояния (например, выбор города)
    await state.finish()
    await ConsultationForm.waiting_for_question.set()

    await message.answer(
        "Привет! Если у вас есть вопросы или нужна помощь — напишите их здесь, мы обязательно ответим!"
    )


async def manager_cmd(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /manager
    Переводит пользователя в сценарий оставления заявки на консультацию.
    """
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})
    await start_consultation_flow(message, state)


async def any_message_handler(message: types.Message, state: FSMContext):
    """
    Обработчик любых сообщений для отслеживания активности пользователя
    """
    await update_user(message.from_user.id, {"last_interaction": datetime.utcnow()})

    # Убрана логика проверки заявок на вступление для открытого канала
    
    # Обрабатываем текстовые сообщения
    if message.text == "Получить консультацию":
        await start_consultation_flow(message, state)
    else:
        await message.answer(
            "Извините, я не понимаю эту команду. Используйте кнопки меню для навигации.",
            reply_markup=get_main_menu()
        )


async def consultation_question_handler(
    message: types.Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает ответ на первый вопрос (текст вопроса пользователя)
    и задает второй вопрос о номере телефона.
    """
    async with state.proxy() as data:
        data["question_text"] = message.text.strip()

    await message.answer(
        "Чтобы команда Арктик Тракс могла связаться с вами для консультации, вы можете оставить свой номер телефона"
    )
    await ConsultationForm.waiting_for_phone.set()


async def consultation_phone_handler(
    message: types.Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает номер телефона (второй вопрос) и задает третий вопрос
    про удобное время для звонка.
    """
    async with state.proxy() as data:
        data["phone"] = message.text.strip()

    await message.answer(
        "Спасибо за ваш вопрос! Когда лучше позвонить? Можем прямо сейчас или в удобное время (укажите время)"
    )
    await ConsultationForm.waiting_for_call_time.set()


async def consultation_call_time_handler(
    message: types.Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает удобное время для звонка (третий вопрос), формирует
    и отправляет заявку на консультацию по email.
    """
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if message.from_user.last_name:
        user_name += f" {message.from_user.last_name}"

    async with state.proxy() as data:
        question_text = data.get("question_text", "")
        phone = data.get("phone", "")
        call_time = message.text.strip()

    # Получаем город пользователя из базы
    from bot.database import get_user

    user_data = await get_user(user_id)
    city = user_data.get("city") if user_data else None

    # Сохраняем номер телефона в базе
    if phone:
        await update_user(user_id, {"phone": phone})

    # Отправляем письмо с учетом всех ответов
    try:
        result = send_consultation_email(
            phone_number=phone,
            user_name=user_name,
            city=city,
            question=question_text,
            call_time=call_time,
        )
        if result:
            await message.answer(
                "Спасибо! Ваша заявка отправлена. Мы свяжемся с вами по указанному номеру.",
                reply_markup=get_main_menu(),
            )
        else:
            await message.answer(
                "Произошла ошибка при отправке заявки. Попробуйте позже или свяжитесь с нами другим способом.",
                reply_markup=get_main_menu(),
            )
    except Exception as exc:
        logging.error(
            f"Ошибка при отправке email с заявкой (user_id={user_id}, phone={phone}): {exc}"
        )
        await message.answer(
            "Произошла ошибка при отправке заявки. Попробуйте позже или свяжитесь с нами другим способом.",
            reply_markup=get_main_menu(),
        )
    finally:
        await state.finish()

async def contact_handler(message: types.Message):
    """
    Обработчик получения контакта пользователя (номер телефона)
    """
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        if message.from_user.last_name:
            user_name += f" {message.from_user.last_name}"
        
        # Получаем город пользователя из базы данных
        from bot.database import get_user
        user_data = await get_user(user_id)
        city = user_data.get("city") if user_data else None
        
        # Сохраняем номер телефона в базе
        await update_user(user_id, {"phone": phone})
        # Отправляем email (синхронная функция)
        try:
            result = send_consultation_email(phone, user_name, city)
            if result:
                # Уведомляем пользователя
                await message.answer(
                    "Спасибо! Ваш номер телефона отправлен консультанту. Скоро с вами свяжутся.",
                    reply_markup=get_main_menu()
                )
            else:
                await message.answer(
                    "Произошла ошибка при отправке заявки. Попробуйте позже или свяжитесь с нами другим способом.",
                    reply_markup=get_main_menu()
                )
        except Exception as e:
            logging.error(f"Ошибка при отправке email с номером {phone}: {e}")
            await message.answer(
                "Произошла ошибка при отправке заявки. Попробуйте позже или свяжитесь с нами другим способом.",
                reply_markup=get_main_menu()
            )
    else:
        await message.answer(
            "Не удалось получить номер телефона. Пожалуйста, попробуйте ещё раз.",
            reply_markup=get_main_menu()
        )

async def set_city_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    from bot.handlers.city_handlers import ask_city
    await callback_query.answer()
    await ask_city(callback_query.message, state)

def register_user_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков команд пользователя
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    dp.register_message_handler(start_cmd, CommandStart(), state="*")
    dp.register_message_handler(help_cmd, Command("help"), state="*")
    dp.register_message_handler(about_cmd, Command("about"), state="*")
    dp.register_message_handler(available_cmd, Command("available"), state="*")
    dp.register_message_handler(shop_cmd, Command("shop"), state="*")
    dp.register_message_handler(configurator_cmd, Command("configurator"), state="*")
    dp.register_message_handler(manager_cmd, Command("manager"), state="*")

    # Обработчик для сценария консультации (FSM)
    dp.register_message_handler(
        consultation_question_handler,
        state=ConsultationForm.waiting_for_question,
        content_types=types.ContentTypes.TEXT,
    )
    dp.register_message_handler(
        consultation_phone_handler,
        state=ConsultationForm.waiting_for_phone,
        content_types=types.ContentTypes.TEXT,
    )
    dp.register_message_handler(
        consultation_call_time_handler,
        state=ConsultationForm.waiting_for_call_time,
        content_types=types.ContentTypes.TEXT,
    )

    # Обработчик для всех текстовых сообщений (fallback, только вне состояний FSM)
    dp.register_message_handler(
        any_message_handler,
        content_types=types.ContentTypes.TEXT,
        state=None,
    )
    dp.register_message_handler(contact_handler, content_types=ContentType.CONTACT, state="*")
    dp.register_callback_query_handler(set_city_callback_handler, lambda c: c.data == 'set_city', state="*")
    