from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Файл содержит объявление инлайн-клавиатур
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Заполнить данные об НКО",
                                              callback_data="add_info_nko"),
                         InlineKeyboardButton(text="Заполнить позже",
                                              callback_data="pass_add_info")],
                        ])

models_select_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="GigaChat", callback_data="model_gigachat")]
])

text_style_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Официальный", callback_data="style_official")],
    [InlineKeyboardButton(text="Дружелюбный", callback_data="style_friendly")],
    [InlineKeyboardButton(text="Креативный", callback_data="style_creative")],
    [InlineKeyboardButton(text="Пропустить", callback_data="style_skip")]
])

image_style_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Реалистичный", callback_data="image_realistic")],
    [InlineKeyboardButton(text="Мультяшный", callback_data="image_anime")],
    [InlineKeyboardButton(text="Акварель", callback_data="image_acvariel")],
    [InlineKeyboardButton(text="Футуристичный", callback_data="image_futuristic")],
    [InlineKeyboardButton(text="Случайный", callback_data="image_skip")]
])

text_generation_type_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Свободная форма", callback_data="free_text")],
    [InlineKeyboardButton(text="Структурированная форма", callback_data="structured_text")],
    [InlineKeyboardButton(text="По примерам", callback_data="examples_text")]
])

add_gigachat_api_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Добавить API ключ GigaChat", callback_data="add_api_gigachat")],
    [InlineKeyboardButton(text="Инструкция", callback_data="api_instruction")]
])

api_key_management_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Просмотреть оставшиеся токены", callback_data="view_tokens_gigachat")],
    [InlineKeyboardButton(text="Изменить API ключ", callback_data="change_api_gigachat")],
    [InlineKeyboardButton(text="Инструкция", callback_data="api_instruction")]

])

confirm_replace_api_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да, заменить", callback_data="confirm_replace_api")],
    [InlineKeyboardButton(text="Нет, оставить старый", callback_data="cancel_replace_api")]
])

nko_add_info_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Заполнить данные", callback_data="add_info_nko")],
                        ])

nko_edit_info_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Редактировать данные", callback_data="add_info_nko")],
                        ])


def get_regenerate_keyboard(history_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопкой пересоздания контента"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Пересоздать контент", 
                callback_data=f"regenerate_{history_id}"
            )]
        ]
    )