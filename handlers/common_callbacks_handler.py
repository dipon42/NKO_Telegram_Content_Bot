import logging
import os

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

import texts
from keyboards import reply_kb
from keyboards.inline_keyboards import get_regenerate_keyboard
from ai_service.gigachat_ai_service import get_gigachat_service


gigachat_service = get_gigachat_service()

cb_router = Router(name="CallBack router")
logger = logging.getLogger(__name__)

@cb_router.callback_query(F.data=="pass_add_info")
async def pass_add_info(cb: CallbackQuery):
    """Обработка callback пропуска заполнения"""
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(texts.PASS_TEXT,reply_markup=reply_kb.main_keyboard)
    await cb.answer()

@cb_router.callback_query(F.data=="api_instruction")
async def api_instruction(cb: CallbackQuery):
    await cb.message.answer(texts.API_HELP_TEXT)
    await cb.answer()

@cb_router.callback_query(F.data.startswith("regenerate_"))
async def regenerate_content(cb: CallbackQuery, nko_repo, content_history_repo, ai_api_repo):
    """Пересоздание контента"""
    try:

        await cb.answer()

        # Удаляем клавиатуру и показываем индикатор
        await cb.message.edit_reply_markup(reply_markup=None)
        if cb.message.text:
            await cb.message.edit_text("🔄 Пересоздаю контент, ожидайте...")
        elif cb.message.caption:
            await cb.message.edit_caption(caption="🔄 Пересоздаю контент, ожидайте...", reply_markup=None)

        # Извлекаем ID записи
        history_id = int(cb.data.split("_")[1])

        # Получаем запись из истории
        history_entry = await content_history_repo.get_by_id(history_id)
        if not history_entry or history_entry.tg_id != cb.from_user.id:
            await cb.message.edit_text("❌ Запись не найдена или доступ запрещён.")
            return

        # Получаем данные НКО и API-ключ
        nko_data = await nko_repo.get_nko_data(cb.from_user.id)
        user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
        user_api_key = user_api.api_key if user_api and user_api.connected else None

        content_type = history_entry.content_type
        new_result = None
        regenerate_button = get_regenerate_keyboard(history_id)  # Это InlineKeyboard

        # Создаём новую запись для пересозданного контента
        new_history_entry = await content_history_repo.add_content_history(
            tg_id=cb.from_user.id,
            content_type=history_entry.content_type,
            prompt=history_entry.prompt,
            model=history_entry.model,
            style=history_entry.style,
            result=None,  # Результат будет добавлен позже
            additional_params={
                **(history_entry.additional_params or {}),
                "regenerated_from": history_id  # Ссылка на оригинальную запись
            }
        )
        
        if content_type == "text_generation" and history_entry.additional_params:
            style = history_entry.additional_params.get('style', '')
            description = history_entry.additional_params.get('description', history_entry.prompt)
            prompt_with_style = f"{description} (в {style} стиле)" if style else description

            new_result = await gigachat_service.generate_free_text(
                user_idea=prompt_with_style,
                nko_data=nko_data,
                user_api_key=user_api_key
            )

        elif content_type == "content_plan" and history_entry.additional_params:
            new_result = await gigachat_service.generate_content_plan(
                period=history_entry.additional_params.get('period', 'неделя'),
                frequency=history_entry.additional_params.get('frequency', 'ежедневно'),
                nko_focus=history_entry.additional_params.get('nko_focus', 'благотворительность'),
                nko_data=nko_data,
                user_api_key=user_api_key
            )

        elif content_type == "image_generation":
            # Удаляем старое сообщение с изображением
            await cb.message.delete()

            # Отправляем уведомление о генерации
            wait_msg = await cb.message.answer(
                "🎨 Создаю изображение... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳"
            )

            # Генерируем изображение
            try:
                success, new_result = await gigachat_service.generate_image(
                    prompt=history_entry.prompt,
                    style=history_entry.additional_params.get('style', ''),
                    credentials=user_api_key
                )
                if not success:
                    raise Exception(f"Ошибка при генерации изображения: {success}")
            except Exception as img_exc:
                logger.error(f"Ошибка генерации изображения: {img_exc}")
                await wait_msg.edit_text(
                    "❌ Не удалось создать изображение. Попробуйте позже или уточните запрос.",
                    reply_markup=regenerate_button
                )
                # Удаляем запись о неудачной перегенерации
                await content_history_repo.db_session.delete(new_history_entry)
                await content_history_repo.db_session.commit()
                return

            await wait_msg.delete()
            
            # Отправляем изображение
            sent_message = await cb.message.answer_photo(
                photo=FSInputFile(new_result),
                caption="🖼 Вот ваше новое изображение:",
                reply_markup=get_regenerate_keyboard(new_history_entry.id)
            )
            
            # Сохраняем file_id и коммитим
            new_history_entry.result = sent_message.photo[-1].file_id
            await content_history_repo.db_session.commit()
            
            os.remove(new_result) # Удаляем временный файл
            return

        else:
            # Для других типов контента
            if content_type == "text_edit":
                new_result = await gigachat_service.edit_text(
                    text=history_entry.additional_params.get('original_text', history_entry.prompt),
                    user_api_key=user_api_key
                )
            else:
                new_result = await gigachat_service.generate_free_text(
                    user_idea=history_entry.prompt,
                    nko_data=nko_data,
                    user_api_key=user_api_key
                )

        # Сохраняем и редактируем текст
        if new_result:
            # Обновляем результат для новой записи
            new_history_entry.result = new_result
            await content_history_repo.db_session.commit()
            
            # Обновляем клавиатуру с новым ID для пересоздания
            new_regenerate_button = get_regenerate_keyboard(new_history_entry.id)
            
            try:
                await cb.message.edit_text(
                    new_result,
                    parse_mode="Markdown",
                    reply_markup=new_regenerate_button
                )
            except Exception:
                await cb.message.edit_text(
                    new_result,
                    reply_markup=new_regenerate_button
                )
        else:
            # Если перегенерация не удалась, удаляем запись
            await content_history_repo.db_session.delete(new_history_entry)
            await content_history_repo.db_session.commit()
            
            await cb.message.edit_text(
                "❌ Не удалось пересоздать контент. Попробуйте позже.",
                reply_markup=regenerate_button
            )

    except ValueError:
        await cb.message.edit_text("⚠️ Некорректный идентификатор записи.")
    except Exception as e:
        logger.error(f"Ошибка при пересоздании контента: {e}")
        await cb.message.edit_text(
            "❌ Произошла ошибка при пересоздании контента. Попробуйте позже.",
            reply_markup=reply_kb.main_keyboard
        )