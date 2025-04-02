"""
Обработчики для запроса и обработки города пользователя
"""

import logging
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from bot.database import update_user

# Определяем состояния для FSM
class CityForm(StatesGroup):
    waiting_for_city = State()  # Ожидание ввода города

async def ask_city(message: types.Message, state: FSMContext):
    """
    Запрашивает у пользователя город проживания
    
    Args:
        message (types.Message): Сообщение пользователя
        state (FSMContext): Состояние FSM
    """
    # Переводим пользователя в состояние ожидания ввода города
    await state.set_state(CityForm.waiting_for_city.state)
    
    await message.answer(
        "Укажите ваш город:\n\n"
        "Эта информация поможет нам предоставлять вам более релевантную информацию."
    )
    logging.info(f"Запрошен город у пользователя {message.from_user.id}")

async def ask_city_by_user_id(user_id: int, bot):
    """
    Запрашивает у пользователя город проживания по его ID
    
    Args:
        user_id (int): ID пользователя
        bot: Экземпляр бота для отправки сообщения
    """
    # Получаем доступ к Dispatcher через бота
    dp = Dispatcher.get_current()
    
    # Получаем FSM контекст для пользователя
    state = dp.current_state(user=user_id)
    
    # Сначала сбрасываем все предыдущие состояния
    await state.reset_state()
    logging.info(f"Сброшены предыдущие состояния для пользователя {user_id}")
    
    # Переводим пользователя в состояние ожидания ввода города
    await state.set_state(CityForm.waiting_for_city.state)
    
    # Проверяем, что состояние установлено
    current_state = await state.get_state()
    logging.info(f"Установлено состояние: {current_state} для пользователя {user_id}")
    
    await bot.send_message(
        chat_id=user_id,
        text="Укажите ваш город:\n\n"
             "Эта информация поможет нам предоставлять вам более релевантную информацию."
    )
    logging.info(f"Запрошен город у пользователя {user_id}")

async def process_city(message: types.Message, state: FSMContext):
    """
    Обрабатывает полученный от пользователя город
    
    Args:
        message (types.Message): Сообщение пользователя с названием города
        state (FSMContext): Состояние FSM
    """
    user_id = message.from_user.id
    city = message.text.strip()
    
    # Сохраняем город в базе данных
    await update_user(user_id, {"city": city})
    
    # Завершаем состояние
    await state.finish()
    
    # Благодарим пользователя и сообщаем о получении уведомлений
    await message.answer(
        f"Спасибо! Мы сохранили информацию о вашем городе ({city}).\n\n"
        "Теперь вы будете получать все уведомления от нашего бота.",
        reply_markup=ReplyKeyboardRemove()
    )
    logging.info(f"Пользователь {user_id} указал город: {city}")

async def process_any_message_in_city_state(message: types.Message, state: FSMContext):
    """
    Обрабатывает любое текстовое сообщение в состоянии ожидания города
    (запасной вариант, если основной обработчик не сработает)
    
    Args:
        message (types.Message): Сообщение пользователя
        state (FSMContext): Состояние FSM
    """
    user_id = message.from_user.id
    city = message.text.strip()
    
    logging.info(f"[Запасной обработчик] Получен город '{city}' от пользователя {user_id}")
    
    # Сохраняем город в базе данных
    await update_user(user_id, {"city": city})
    
    # Завершаем состояние
    await state.finish()
    
    # Благодарим пользователя и сообщаем о получении уведомлений
    await message.answer(
        f"Спасибо! Мы сохранили информацию о вашем городе ({city}).\n\n"
        "Теперь вы будете получать все уведомления от нашего бота.",
        reply_markup=ReplyKeyboardRemove()
    )
    logging.info(f"[Запасной обработчик] Пользователь {user_id} указал город: {city}")

def register_city_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков для работы с городом
    
    Args:
        dp (Dispatcher): Dispatcher объект
    """
    logging.info("Регистрация обработчиков состояния ожидания города (CityForm.waiting_for_city)")
    # Регистрируем только один обработчик с более низким приоритетом
    dp.register_message_handler(process_city, state=CityForm.waiting_for_city, content_types=types.ContentTypes.TEXT)
    logging.info("Обработчик состояния ожидания города зарегистрирован")