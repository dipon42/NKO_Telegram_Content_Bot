import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from keyboards.inline_keyboards import models_select_keyboard, text_style_keyboard, get_regenerate_keyboard, text_generation_type_keyboard
from fsm import TextGenerationState, StructuredPostState, TextFromExamplesState


text_gen_router = Router(name="AI Text Generation")
logger = logging.getLogger(__name__)


@text_gen_router.message(Command("создать_текст","generate_text")) # Реагируем на команды
@text_gen_router.message(F.text == "Создание текста ✍️")
async def text_generation_start(message: Message, state: FSMContext):
    """Начало процесса генерации текста"""
    await message.answer(
        "Выберите тип генерации текста:",
        reply_markup=text_generation_type_keyboard
    )
    await state.set_state(TextGenerationState.choosing_model)

@text_gen_router.callback_query(F.data == "free_text")
async def choose_free_text(cb: CallbackQuery, state: FSMContext):
    """Выбор генерации свободного текста"""
    await state.update_data(generation_type="free")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        "Выберите модель для генерации:\n\n"
        "1. GigaChat - русскоязычная модель от Сбера\n",
        reply_markup=models_select_keyboard # в будущем добавим еще модели для выбора(например GigaChat Pro)
    )
    await state.set_state(TextGenerationState.choosing_model)

@text_gen_router.callback_query(F.data == "structured_text")
async def choose_structured_text(cb: CallbackQuery, state: FSMContext):
    """Выбор генерации структурированного текста"""
    await state.update_data(generation_type="structured")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Опишите событие:")
    await state.set_state(StructuredPostState.entering_event)

@text_gen_router.callback_query(F.data == "examples_text")
async def choose_examples_text(cb: CallbackQuery, state: FSMContext):
    """Выбор генерации текста по примерам"""
    await state.update_data(generation_type="examples")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Введите 2-3 примера готовых постов (каждый пример с новой строки):")
    await state.set_state(TextFromExamplesState.entering_examples)

@text_gen_router.callback_query(TextGenerationState.choosing_model, F.data == "model_gigachat")
async def model_chosen_gigachat(cb: CallbackQuery, state: FSMContext):
    """Обработчик выбора модели GigaChat для свободной формы"""
    await state.update_data(model="GigaChat")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Введите описание для генерации поста:")
    await state.set_state(TextGenerationState.entering_description)

@text_gen_router.message(TextGenerationState.entering_description)
async def description_entered(message: Message, state: FSMContext):
    """Обработка введенного описания"""
    await state.update_data(description=message.text)
    await message.answer(
        "Выберите стиль текста:",
        reply_markup=text_style_keyboard
    )
    await state.set_state(TextGenerationState.choosing_style)

@text_gen_router.callback_query(TextGenerationState.choosing_style)
async def style_chosen(cb: CallbackQuery, state: FSMContext, nko_repo, content_history_repo, ai_api_repo, gigachat_service):
    """Обработчик выбора стиля и финальная генерация"""
    style_mapping = {
        "style_official": "официальный",
        "style_friendly": "дружелюбный",
        "style_creative": "креативный"
    }
    
    style = style_mapping.get(cb.data, "нейтральный")
    await cb.message.delete()
    msg = await cb.message.answer("Генерация текста... Пожалуйста, подождите🔄️")
    await state.update_data(style=style)
    
    data = await state.get_data()
    description = data["description"]
    
    # Получаем данные НКО пользователя
    nko_data = await nko_repo.get_nko_data(cb.from_user.id)

    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Генерируем текст с учетом стиля
    prompt_with_style = f"{description} (в {style} стиле)"
    
    result = await gigachat_service.generate_free_text(
        user_idea=prompt_with_style,
        nko_data=nko_data,
        user_api_key=user_api_key
    )

    # Сохраняем в историю с дополнительными параметрами
    history_entry = await content_history_repo.add_content_history(
        tg_id=cb.from_user.id,
        content_type="text_generation",
        prompt=description,
        result=result,
        model="gigachat",
        style=style,
        additional_params={
            "model": "GigaChat",
            "style": style,
            "description": description
        }
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
            await msg.edit_text("Не удалось сгенерировать текст. "
                                "Попробуйте пересоздать или попробуйте позже.",reply_markup=regenerate_keyboard)

    await state.clear()
    await cb.answer()