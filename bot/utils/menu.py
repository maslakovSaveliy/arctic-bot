from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Получить консультацию"))

    keyboard.add(KeyboardButton("Arctic Trucks в наличии"))
    keyboard.add(KeyboardButton("Интернет-магазин"))
    keyboard.add(KeyboardButton("Конфигуратор"))

    return keyboard