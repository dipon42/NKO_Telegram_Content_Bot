import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from keyboards.inline_keyboards import get_regenerate_keyboard


onmsg_router = Router()
logger = logging.getLogger(__name__)

@onmsg_router.message(F.text.len() > 10, StateFilter(None), ~F.text.startswith("/"))
async def handle_non_command_messages(message: Message, nko_repo,
                                      content_history_repo, ai_api_repo,
                                      gigachat_service):
    """генерация текста без контекста (игнорирует команды, начинающиеся с /)"""
    
    # Пропускаем пересланные сообщения - они обрабатываются в examples_gen_router
    if message.forward_date is not None:
        logger.debug(f"Пропущено пересланное сообщение: {message.text[:50]}")
        return
    
    logger.info(f"Обработка обычного сообщения для генерации: {message.text[:50]}...")
    # Получаем данные НКО пользователя
    nko_data = await nko_repo.get_nko_data(message.from_user.id)
    
    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Проверяем размер очереди перед генерацией
    from utils.generation_queue import get_generation_queue
    queue = get_generation_queue()
    queue_size = queue._queue.qsize()
    
    # Создаем сообщение о статусе
    if queue_size > 0:
        msg = await message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {queue_size + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        msg = await message.answer("Создаю текст... Пожалуйста, подождите 🔄")
    
    # Callback для обновления сообщения при начале обработки
    async def update_message():
        try:
            await msg.edit_text("Создаю текст... Пожалуйста, подождите 🔄")
        except:
            pass

    # Генерируем текст
    result, position = await gigachat_service.generate_free_text(
        user_idea=message.text,
        nko_data=nko_data,
        user_api_key=user_api_key,
        on_start_callback=update_message
    )


    # Сохраняем в историю
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="free_text",
        prompt=message.text,
        result=result,
        model="gigachat"
    )

    # Создаем инлайн-кнопку для перегенерации с ID записи
    regenerate_keyboard = get_regenerate_keyboard(history_entry.id)

    # Отправляем результат с кнопкой перегенерации
    try:
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=regenerate_keyboard)
    except:
        if result:
            await msg.edit_text(result, reply_markup=regenerate_keyboard)
        else:
            await msg.edit_text("Не удалось создать текст. Попробуйте пересоздать!",reply_markup=regenerate_keyboard)