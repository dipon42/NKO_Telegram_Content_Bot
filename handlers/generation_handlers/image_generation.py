import asyncio
import logging
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from keyboards.inline_keyboards import get_regenerate_keyboard, image_style_keyboard
from fsm import ImageGenerationState


image_gen_router = Router(name="API image generation")
logger = logging.getLogger(__name__)


@image_gen_router.message(F.text.startswith("Создание картинки 🎨"))
async def image_generation_start(message: Message, state: FSMContext):
    """Генерация изображения"""
    await message.answer("Введите вашу идею, для генерации изображения:")
    await state.set_state(ImageGenerationState.entering_description)

@image_gen_router.message(ImageGenerationState.entering_description)
async def image_description_entered(message: Message, state: FSMContext):
    description = message.text

    if not description:
        await message.answer("Пожалуйста, введите описание для генерации изображения.")
        return
    if len(description) < 10:
        await message.answer("Описание должно быть не менее 10 символов. Пожалуйста, попробуйте еще раз.")
        return

    await state.update_data(description=description)
    await message.answer("Выберите стиль для генерации изображения:", reply_markup=image_style_keyboard)
    await state.set_state(ImageGenerationState.style_selection)

@image_gen_router.callback_query(ImageGenerationState.style_selection, F.data.startswith("image_"))
async def style_selected(cb: CallbackQuery, state: FSMContext, ai_api_repo, gigachat_service, content_history_repo):
    """Генерация изображения"""
    style = cb.data.split("_")[1]
    description = (await state.get_data()).get("description", "")
    await cb.message.delete()

    msg = await cb.message.answer("Создаю изображение... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")

    user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    success, image_url = await gigachat_service.generate_image(prompt=description, style=style, credentials=user_api_key)

    try:
        if success and image_url:
            await msg.delete()
            await asyncio.sleep(0.1)
            img = await cb.message.answer_photo(
                photo=FSInputFile(image_url),
                caption="🖼 Вот ваше изображение:"
            )

            history_entry = await content_history_repo.add_content_history(
                tg_id=cb.from_user.id,
                content_type="image_generation",
                prompt=description,
                result=img.photo[-1].file_id,
                model="gigachat",
                additional_params={"model": "GigaChat", "style": style}
            )

            await img.edit_reply_markup(reply_markup=get_regenerate_keyboard(history_entry.id))

        else:
            # Ошибка генерации
            history_entry = await content_history_repo.add_content_history(
                tg_id=cb.from_user.id,
                content_type="image_generation",
                prompt=description,
                result="Не удалось создать изображение",
                model="gigachat",
                additional_params={"model": "GigaChat", "style": style}
            )
            await msg.edit_text(
                "Не удалось создать изображение. Пожалуйста, попробуйте еще раз.",
                reply_markup=get_regenerate_keyboard(history_entry.id)
            )
            logger.error(f"Ошибка при создании изображения: {image_url}")

    except Exception as e:
        logger.exception("Неожиданная ошибка при обработке результата генерации изображения")
        await msg.edit_text("Произошла ошибка. Попробуйте позже.")

    finally:
        # Удаляем временный файл
        if success and image_url and os.path.exists(image_url):
            try:
                os.remove(image_url)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {image_url}: {e}")



