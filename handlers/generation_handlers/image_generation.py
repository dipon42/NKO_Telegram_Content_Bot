import asyncio
import logging
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from keyboards.inline_keyboards import get_regenerate_keyboard, image_style_keyboard, image_prompt_enhancement_keyboard
from fsm import ImageGenerationState
from texts import IMAGE_PROMPT_ENHANCEMENT
from utils.generation_queue import get_generation_queue


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
    await message.answer(IMAGE_PROMPT_ENHANCEMENT, reply_markup=image_prompt_enhancement_keyboard)
    await state.set_state(ImageGenerationState.choosing_improvement)

@image_gen_router.callback_query(ImageGenerationState.choosing_improvement, F.data == "image_prompt_original")
async def prompt_original_selected(cb: CallbackQuery, state: FSMContext):
    """Пользователь выбрал оставить промт без изменений"""
    await cb.answer()
    
    data = await state.get_data()
    description = data.get("description", "")
    
    # Сохраняем оригинальный промт как финальный
    await state.update_data(final_prompt=description)
    
    # Удаляем сообщение с кнопками выбора
    await cb.message.delete()
    
    # Переходим к выбору стиля
    await cb.message.answer("Выберите стиль для генерации изображения:", reply_markup=image_style_keyboard)
    await state.set_state(ImageGenerationState.style_selection)

@image_gen_router.callback_query(ImageGenerationState.choosing_improvement, F.data == "image_prompt_enhance")
async def prompt_enhance_selected(cb: CallbackQuery, state: FSMContext, ai_api_repo, gigachat_service):
    """Пользователь выбрал улучшить промт с помощью ИИ"""
    await cb.answer()
    
    data = await state.get_data()
    description = data.get("description", "")
    
    # Удаляем сообщение с кнопками выбора
    await cb.message.delete()
    
    # Отправляем сообщение о начале улучшения промта
    msg = await cb.message.answer("Улучшаю ваш промт с помощью ИИ... Подождите немного ⏳")
    
    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None
    
    # Улучшаем промт с помощью ИИ
    enhanced_prompt, _ = await gigachat_service.enhance_image_prompt(
        user_prompt=description,
        user_api_key=user_api_key
    )
    
    # Сохраняем улучшенный промт
    await state.update_data(final_prompt=enhanced_prompt)
    
    # Редактируем сообщение с результатом и предупреждением о длительной генерации
    await msg.edit_text(
        "✅ Промт успешно улучшен!\n\n"
        f"Оригинальный промт:\n`{description}`\n\n"
        f"Улучшенный промт:\n`{enhanced_prompt}`\n\n"
        "⚠️ После улучшения промта генерация изображения может занимать немного больше времени.\n\n"
        "Теперь выберите стиль для генерации изображения:",
        reply_markup=image_style_keyboard
    )
    
    # Переходим к выбору стиля
    await state.set_state(ImageGenerationState.style_selection)

@image_gen_router.callback_query(ImageGenerationState.style_selection, F.data.startswith("image_"))
async def style_selected(cb: CallbackQuery, state: FSMContext, ai_api_repo, gigachat_service, content_history_repo):
    try:
        style = cb.data.split("_")[1]
    except (IndexError, ValueError):
        await cb.answer("❌ Ошибка при выборе стиля. Попробуйте еще раз.")
        return
    data = await state.get_data()
    original_description = data.get("description", "")
    final_prompt = data.get("final_prompt", original_description)
    
    await cb.message.delete()

    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Проверяем размер очереди перед генерацией
    queue = get_generation_queue(user_api_key)
    pending_tasks = queue.get_pending_tasks_count()
    
    # Отправляем сообщение о начале генерации
    if pending_tasks > 0:
        msg = await cb.message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {pending_tasks + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        msg = await cb.message.answer("Создаю изображение... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")
    
    # Callback для обновления сообщения при начале обработки
    async def update_message():
        try:
            await msg.edit_text("Создаю изображение... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")
        except:
            pass

    # Генерируем изображение
    success, image_url, position = await gigachat_service.generate_image(
        prompt=final_prompt, 
        style=style, 
        credentials=user_api_key,
        on_start_callback=update_message
    )

    try:
        if success and image_url:
            await msg.delete()
            await asyncio.sleep(0.1)
            img = await cb.message.answer_photo(
                photo=FSInputFile(image_url),
                caption="🖼 Вот ваше изображение:"
            )

            # Сохраняем в историю
            if img.photo and len(img.photo) > 0:
                photo_file_id = img.photo[-1].file_id
            else:
                logger.error("Не удалось получить file_id из отправленного фото")
                photo_file_id = "Ошибка сохранения изображения"
            
            # Определяем, был ли промпт улучшен ИИ
            was_enhanced = final_prompt != original_description
            
            history_entry = await content_history_repo.add_content_history(
                tg_id=cb.from_user.id,
                content_type="image_generation",
                prompt=final_prompt,  # Сохраняем финальный промпт (улучшенный или оригинальный)
                result=photo_file_id,
                model="gigachat",
                additional_params={
                    "model": "GigaChat", 
                    "style": style,
                    "original_prompt": original_description,
                    "enhanced_prompt": final_prompt if was_enhanced else None,
                    "was_enhanced": was_enhanced
                }
            )

            # Формируем подпись с информацией о промте
            prompt_info = ""
            if final_prompt != original_description:
                prompt_info = f"\n\n🔧 Промт был улучшен ИИ:\n\n`{final_prompt}`"
            
            await img.edit_caption(
                caption=f"🖼 Вот ваше изображение:{prompt_info}",
                reply_markup=get_regenerate_keyboard(history_entry.id)
            )

        else:
            # Ошибка генерации - image_url содержит сообщение об ошибке
            error_message = image_url if isinstance(image_url, str) else "Не удалось создать изображение. Пожалуйста, попробуйте еще раз."
            
            # Определяем, был ли промпт улучшен ИИ
            was_enhanced = final_prompt != original_description
            
            history_entry = await content_history_repo.add_content_history(
                tg_id=cb.from_user.id,
                content_type="image_generation",
                prompt=final_prompt,  # Сохраняем финальный промпт (улучшенный или оригинальный)
                result="Не удалось создать изображение",
                model="gigachat",
                additional_params={
                    "model": "GigaChat", 
                    "style": style,
                    "original_prompt": original_description,
                    "enhanced_prompt": final_prompt if was_enhanced else None,
                    "was_enhanced": was_enhanced
                }
            )
            await msg.edit_text(
                error_message,
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

        # Сбрасываем состояние, чтобы пользователь мог начать новый сценарий
        await state.clear()