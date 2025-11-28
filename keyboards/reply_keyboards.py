from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# Файл содержит объявление reply-клавиатур
main_keyboard = ReplyKeyboardMarkup(keyboard=[
                                    [KeyboardButton(text="Информация об НКО"),],
                                    [KeyboardButton(text="Создание текста ✍️"),
                                     KeyboardButton(text="Создание картинки 🎨"),],
                                    [KeyboardButton(text="Создать контент-план 📅"),
                                     KeyboardButton(text="Редактор текста 🔍"),],
                                    [KeyboardButton(text="История 📜"),
                                     KeyboardButton(text="Настройки")]],
                                    resize_keyboard=True) # Основная клавиатура

skip_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Пропустить")]
], resize_keyboard=True, one_time_keyboard=True) # Клавиатура для пропуска шага