from copy import deepcopy

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


_BASE_MAIN_KEYBOARD_LAYOUT = [
    [KeyboardButton(text="Информация об НКО")],
    [KeyboardButton(text="Создание текста ✍️"),
     KeyboardButton(text="Создание картинки 🎨")],
    [KeyboardButton(text="Создать контент-план 📅"),
     KeyboardButton(text="Редактор текста 🔍")],
    [KeyboardButton(text="История 📜"),
     KeyboardButton(text="Настройки")],
]

ACCESS_BUTTON = KeyboardButton(text="Управление доступом 🔐")


def build_main_keyboard(show_access_button: bool = False) -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру с опциональной кнопкой управления доступом."""
    keyboard_layout = deepcopy(_BASE_MAIN_KEYBOARD_LAYOUT)
    if show_access_button:
        keyboard_layout.append([ACCESS_BUTTON])
    return ReplyKeyboardMarkup(keyboard=keyboard_layout, resize_keyboard=True)


# Клавиатура по умолчанию без кнопки доступа
main_keyboard = build_main_keyboard()

skip_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Пропустить")]
], resize_keyboard=True, one_time_keyboard=True) # Клавиатура для пропуска шага