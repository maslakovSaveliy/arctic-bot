from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    # Пользователь инициирует сценарий консультации, отвечая на вопросы,
    # номер телефона вводит вручную, поэтому request_contact не используется
    keyboard.add(KeyboardButton('Получить консультацию'))
    return keyboard