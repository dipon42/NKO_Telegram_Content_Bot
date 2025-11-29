import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from fsm import StructuredPostState
from keyboards.inline_keyboards import get_regenerate_keyboard
from utils.generation_queue import get_generation_queue


structured_gen_router = Router(name="AI Structured Text Generation Router")
logger = logging.getLogger(__name__)

@structured_gen_router.message(StructuredPostState.entering_event)
async def event_entered(message: Message, state: FSMContext):
    """Обработка введённого события"""
    await state.update_data(event=message.text)
    await message.answer("Введите дату события:")
    await state.set_state(StructuredPostState.entering_date)

@structured_gen_router.message(StructuredPostState.entering_date)
async def date_entered(message: Message, state: FSMContext):
    """Обработка введённой даты"""
    await state.update_data(date=message.text)
    await message.answer("Введите место проведения события:")
    await state.set_state(StructuredPostState.entering_location)

@structured_gen_router.message(StructuredPostState.entering_location)
async def location_entered(message: Message, state: FSMContext):
    """Обработка введённого места"""
    await state.update_data(location=message.text)
    await message.answer("Кто приглашён на событие? (например, волонтёры, благотворители, все желающие):")
    await state.set_state(StructuredPostState.entering_invitees)

@structured_gen_router.message(StructuredPostState.entering_invitees)
async def invitees_entered(message: Message, state: FSMContext):
    """Обработка введённых приглашённых"""
    await state.update_data(invitees=message.text)
    await message.answer("Введите дополнительные детали о событии (например, программа, дресс-код, что взять с собой):")
    await state.set_state(StructuredPostState.entering_details)

@structured_gen_router.message(StructuredPostState.entering_details)
async def details_entered(message: Message, state: FSMContext, nko_repo,
                          content_history_repo, ai_api_repo, gigachat_service):
    """Обработка дополнительных деталей и генерация поста"""
    await state.update_data(details=message.text)
    
    data = await state.get_data()
    
    # Формируем информацию о событии
    event_info = {
        "событие": data["event"],
        "дата": data["date"],
        "место": data["location"],
        "приглашённые": data["invitees"],
        "дополнительные детали": data["details"]
    }
    
    # Получаем данные НКО пользователя
    nko_data = await nko_repo.get_nko_data(message.from_user.id)

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
        status_msg = await message.answer("📝 Генерирую пост... Пожалуйста, подождите🔄️")

    # Генерируем пост на основе структурированных данных
    try:
        result = await gigachat_service.generate_structured_post(
            event_info=event_info,
            nko_data=nko_data,
            user_api_key=user_api_key
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации структурированного поста: {e}", exc_info=True)
        await status_msg.edit_text("❌ Не удалось сгенерировать пост. Попробуйте позже.")
        await state.clear()
        return

    # Сохраняем в историю
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="structured_post",
        prompt=str(event_info),
        result=result,
        model="gigachat",
        additional_params={
            "event_info": event_info
        }
    )

    # Создаем инлайн-кнопку для перегенерации с ID записи
    regenerate_keyboard = get_regenerate_keyboard(history_entry.id)

    # Отправляем результат с кнопкой перегенерации
    try:
        await status_msg.edit_text(result, parse_mode="Markdown", reply_markup=regenerate_keyboard)
    except:
        if result:
            await status_msg.edit_text(result, reply_markup=regenerate_keyboard)
        else:
            await status_msg.edit_text("Не удалось сгенерировать текст")
    
    await state.clear()