import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from fsm import TextFromExamplesState
from keyboards.inline_keyboards import get_regenerate_keyboard
from utils.generation_queue import get_generation_queue


examples_gen_router = Router(name="AI Examples Generation")
logger = logging.getLogger(__name__)


@examples_gen_router.message(F.forward_date | F.is_copy, StateFilter(None))
async def handle_forwarded_message(message: Message, state: FSMContext):
    """Если пользователь переслал сообщение — сохраняем как пример и просим ввести идею"""
    text = message.text or message.caption or "Текст недоступен"
    
    # Проверяем, что текст не пустой
    if not text or text.strip() == "" or text == "Текст недоступен":
        await message.answer("❌ Не удалось получить текст из пересланного сообщения. Пожалуйста, перешлите сообщение с текстом.")
        return

    # Сохраняем пример в состояние
    await state.set_state(TextFromExamplesState.entering_new_idea)
    await state.update_data(examples=[text.strip()])
    
    logger.info(f"Пересланное сообщение сохранено как пример: {text[:50]}...")

    await message.answer("✅ Пример получен. Введите идею для нового поста:")

@examples_gen_router.message(TextFromExamplesState.entering_examples,F.forward_date)
async def forwarded_example_handler(message: Message, state: FSMContext):
    """Обработка пересланного сообщения как примера"""
    text = message.text or message.caption or "Текст недоступен"

    await state.update_data(examples=[text.strip()])
    await message.answer("Пример получен. Введите идею для нового поста:")
    await state.set_state(TextFromExamplesState.entering_new_idea)

@examples_gen_router.message(TextFromExamplesState.entering_examples)
async def examples_entered(message: Message, state: FSMContext):
    """Обработка введённых примеров"""
    examples = [ex.strip() for ex in message.text.split('\n') if ex.strip()]
    if len(examples) < 1:
        await message.answer("Пожалуйста, введите хотя бы один пример поста:")
        return
    
    await state.update_data(examples=examples)
    await message.answer("Введите идею для нового поста:")
    await state.set_state(TextFromExamplesState.entering_new_idea)

@examples_gen_router.message(TextFromExamplesState.entering_new_idea)
async def new_idea_entered(message: Message, state: FSMContext, nko_repo,
                           content_history_repo, ai_api_repo, gigachat_service):
    """Обработка новой идеи и генерация поста по аналогии с примерами"""
    await state.update_data(new_idea=message.text)
    
    data = await state.get_data()
    
    # Проверяем, что примеры есть в состоянии
    if "examples" not in data or not data["examples"]:
        await message.answer("❌ Ошибка: примеры не найдены. Пожалуйста, перешлите сообщение с примером поста сначала.")
        await state.clear()
        return
    
    logger.info(f"Генерация поста на основе примеров: {len(data['examples'])} пример(ов), идея: {data['new_idea'][:50]}...")
    
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
        status_msg = await message.answer("✨ Генерирую пост по вашим примерам... Пожалуйста, подождите🔄️")

    # Генерируем пост по аналогии с примерами
    try:
        result = await gigachat_service.generate_text_from_examples(
            example_posts=data["examples"],
            new_idea=data["new_idea"],
            user_api_key=user_api_key,
            nko_data=nko_data
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации текста по примерам: {e}", exc_info=True)
        await status_msg.edit_text("❌ Не удалось сгенерировать текст. Попробуйте позже.")
        await state.clear()
        return

    # Сохраняем в историю
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="text_from_examples",
        prompt=f"Примеры: {data['examples']}, Новая идея: {data['new_idea']}",
        result=result,
        model="gigachat",
        additional_params={
            "examples": data["examples"],
            "new_idea": data["new_idea"]
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