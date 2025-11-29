import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from fsm import TextEditorState
from utils.generation_queue import get_generation_queue


editor_router = Router(name="AI Text Editor")
logger = logging.getLogger(__name__)

@editor_router.message(F.text == "Редактор текста 🔍")
async def text_editor_start(message: Message, state: FSMContext):
    """Начало процесса редактирования текста"""
    await message.answer("Введите текст, который вы хотите отредактировать:")
    await state.set_state(TextEditorState.entering_text)

@editor_router.message(TextEditorState.entering_text)
async def text_to_edit_entered(message: Message, state: FSMContext, content_history_repo, ai_api_repo, gigachat_service):
    """Обработка текста для редактирования"""

    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Информируем пользователя о статусе очереди
    queue = get_generation_queue(user_api_key)
    queue_load = queue.get_pending_tasks_count()
    if queue_load > 0:
        status_msg = await message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {queue_load + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        status_msg = await message.answer("✏️ Редактирую текст... Пожалуйста, подождите🔄️")

    # Callback для обновления сообщения при старте
    async def update_message():
        try:
            await status_msg.edit_text("✏️ Редактирую текст... Пожалуйста, подождите🔄️")
        except:
            pass

    # Редактируем текст
    try:
        result, _ = await gigachat_service.edit_text(
            text=message.text,
            user_api_key=user_api_key,
            on_start_callback=update_message
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании текста: {e}", exc_info=True)
        await status_msg.edit_text("❌ Не удалось отредактировать текст. Попробуйте еще раз.")
        return

    # Сохраняем в историю с дополнительными параметрами
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="text_edit",
        prompt=message.text,
        result=result,
        model="gigachat",
        additional_params={
            "original_text": message.text
        }
    )

    try:
        await status_msg.edit_text(result, parse_mode="Markdown")
    except:
        if result:
            await status_msg.edit_text(result)
        else:
            await status_msg.edit_text("Не удалось отредактировать текст. Попробуйте еще раз.")
    
    await state.clear()

@editor_router.message(Command("проверить","check","fix"))
async def handle_edit_command(message: Message, state: FSMContext, content_history_repo, ai_api_repo, gigachat_service):
    """Обработка команды /проверить для исправления ошибок"""

    # Проверяем, что сообщение является ответом и содержит текст
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.answer("Ответьте на текст сообщением с командой /проверить, чтобы проверить и исправить ошибки.")
        return

    original_text = message.reply_to_message.text

    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Информируем пользователя о статусе очереди
    queue = get_generation_queue(user_api_key)
    queue_load = queue.get_pending_tasks_count()
    if queue_load > 0:
        status_msg = await message.reply(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {queue_load + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        status_msg = await message.reply("✏️ Проверяю текст... Пожалуйста, подождите🔄️")

    async def update_message():
        try:
            await status_msg.edit_text("✏️ Проверяю текст... Пожалуйста, подождите🔄️")
        except:
            pass

    # Редактируем текст
    try:
        result, _ = await gigachat_service.edit_text(
            text=original_text,
            user_api_key=user_api_key,
            on_start_callback=update_message
        )
    except Exception:
        await status_msg.edit_text("❌ Не удалось отредактировать текст. Попробуйте еще раз.")
        return

    # Сохраняем в историю
    await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="text_edit",
        prompt=original_text,
        result=result,
        model="gigachat",
        additional_params={
            "original_text": original_text
        }
    )

    # Отправляем результат
    try:
        await status_msg.edit_text(result, parse_mode="Markdown")
    except:
        await status_msg.edit_text(result)