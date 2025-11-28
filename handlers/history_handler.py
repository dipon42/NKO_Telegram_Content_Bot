import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.repositories import ContentHistoryRepository


history_router = Router(name="History Router")


def create_item_navigation_keyboard(current_index: int, total_items: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации по элементам истории"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации

    builder.button(text=f"{current_index + 1}/{total_items}", callback_data="history_current")


    if current_index > 0:
        builder.button(text="◀️ Предыдущее", callback_data=f"history_item_prev_{current_index - 1}")
    if current_index < total_items - 1:
        builder.button(text="Следующее ▶️", callback_data=f"history_item_next_{current_index + 1}")
    
    builder.adjust(1, 2)
    return builder.as_markup()


def get_content_display(history_entry) -> tuple:
    """Возвращает тип действия и содержимое для отображения"""
    action_types = {
        "free_text": "Создание текста",
        "structured_text": "Создание структурированного текста",
        "examples_text": "Создание текста по примерам",
        "image_generation": "Создание изображения",
        "content_plan": "Создание контент-плана",
        "text_edit": "Редактирование текста"
    }
    
    action_type = action_types.get(history_entry.content_type, "Создание контента")
    
    return action_type, history_entry.result

@history_router.message(F.text == "История 📜")
async def show_history(message: Message, content_history_repo: ContentHistoryRepository):
    """Показать историю генерации контента с пагинацией"""
    
    # Получаем историю пользователя
    history_entries = await content_history_repo.get_user_content_history(message.from_user.id,limit=100)
    
    if not history_entries:
        await message.answer("Ваша история пуста. Сначала создайте немного контента! 🎯")
        return
    
    # Отправляем первый элемент с общей информацией
    await show_history_item(message, 0, len(history_entries), history_entries)

async def show_history_item(message: Message, index: int, total_items: int, history_entries: list):
    """Показывает один элемент истории с динамическим содержимым"""
    
    if not history_entries:
        await message.answer("История пуста.")
        return
    
    entry = history_entries[index]
    action_type, content_result = get_content_display(entry)
    
    # Создаем клавиатуру пагинации
    keyboard = create_item_navigation_keyboard(index, total_items)
    
    # Отправляем сообщение с типом действия и содержимым
    if entry.content_type == "image_generation" and entry.result:
        try:
            await message.answer_photo(
                photo=entry.result,
                caption=f"{action_type}\n\n{entry.prompt}",
                reply_markup=keyboard
            )
        except Exception as e:
            await message.answer(
                f"{action_type}\n\nНе удалось загрузить изображение",
                reply_markup=keyboard
            )
    else:
        # Для текстового контента
        if content_result:
            try:
                await message.answer(
                    f"{action_type}\n\n{content_result}",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except:
                await message.answer(
                    f"{action_type}\n\n{content_result}",
                    reply_markup=keyboard
                )
        else:
            await message.answer(
                f"{action_type}\n\nКонтент не доступен",
                reply_markup=keyboard
            )

@history_router.callback_query(F.data.startswith("history_item_prev_") | F.data.startswith("history_item_next_"))
async def handle_history_item_navigation(callback: CallbackQuery, content_history_repo: ContentHistoryRepository):
    """Обработка навигации по элементам истории"""
    try:
        # Определяем направление и индекс
        try:
            if callback.data.startswith("history_item_prev_"):
                new_index = int(callback.data.split("_")[3])
            else:  # history_item_next_
                new_index = int(callback.data.split("_")[3])
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка при парсинге индекса из callback.data: {callback.data}, ошибка: {e}")
            await callback.answer("❌ Ошибка при навигации. Попробуйте еще раз.", show_alert=True)
            return
        
        # Получаем всю историю пользователя
        history_entries = await content_history_repo.get_user_content_history(callback.from_user.id,limit=100)
        
        if not history_entries:
            await callback.message.edit_text("История пуста.")
            await callback.answer()
            return
        
        # Проверяем корректность индекса
        if new_index < 0 or new_index >= len(history_entries):
            await callback.answer("Недопустимый элемент.", show_alert=True)
            return
        
        # Удаляем старое сообщение и показываем новый элемент
        await callback.message.delete()
        await show_history_item(callback.message, new_index, len(history_entries), history_entries)
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error in history item navigation: {e}")
        await callback.answer("Произошла ошибка при навигации.", show_alert=True)

@history_router.callback_query(F.data == "history_current")
async def handle_current_item(callback: CallbackQuery):
    """Обработка нажатия на кнопку текущего элемента"""
    await callback.answer()
