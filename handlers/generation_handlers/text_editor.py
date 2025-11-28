import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from fsm import TextEditorState


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

    # Редактируем текст
    result, _ = await gigachat_service.edit_text(
        text=message.text,
        user_api_key=user_api_key
    )

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
        await message.answer(result, parse_mode="Markdown")
    except:
        if result:
            await message.answer(result)
        else:
            await message.answer("Не удалось отредактировать текст. Попробуйте еще раз.")
    
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

    # Редактируем текст
    try:
        result, _ = await gigachat_service.edit_text(
            text=original_text,
            user_api_key=user_api_key
        )
    except Exception:
        await message.answer("Не удалось отредактировать текст. Попробуйте еще раз.")
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
        await message.reply(result, parse_mode="Markdown")
    except:
        await message.reply(result)