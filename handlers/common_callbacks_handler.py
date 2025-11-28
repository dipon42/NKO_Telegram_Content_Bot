import logging
import os

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import texts
from fsm import ContentPlanState
from keyboards import reply_kb
from keyboards.inline_keyboards import get_regenerate_keyboard, get_accept_plan_keyboard, get_unaccept_plan_keyboard, get_daily_post_keyboard
from ai_service.gigachat_ai_service import get_gigachat_service


gigachat_service = get_gigachat_service()

cb_router = Router(name="CallBack router")
logger = logging.getLogger(__name__)

@cb_router.callback_query(F.data=="pass_add_info")
async def pass_add_info(cb: CallbackQuery):
    """Обработка callback пропуска заполнения"""
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(texts.START_TEXT, reply_markup=reply_kb.main_keyboard, parse_mode="HTML")
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

            new_result, _ = await gigachat_service.generate_free_text(
                user_idea=prompt_with_style,
                nko_data=nko_data,
                user_api_key=user_api_key
            )

        elif content_type == "content_plan" and history_entry.additional_params:
            new_result, _ = await gigachat_service.generate_content_plan(
                period=history_entry.additional_params.get('period', 'неделя'),
                frequency=history_entry.additional_params.get('frequency', 'ежедневно'),
                nko_data=nko_data,
                user_goal=history_entry.additional_params.get('user_goal'),  # Передаем user_goal если он был
                user_api_key=user_api_key
            )

        elif content_type == "image_generation":
            # Удаляем старое сообщение с изображением
            await cb.message.delete()

            # Отправляем уведомление о генерации
            wait_msg = await cb.message.answer(
                "🎨 Создаю изображение... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳"
            )

            # Используем промпт из истории (там уже сохранен финальный промпт - улучшенный или оригинальный)
            prompt_to_use = history_entry.prompt
            
            # Получаем стиль из additional_params (сохраняется как английское название: realistic, anime и т.д.)
            style_to_use = history_entry.additional_params.get('style', 'realistic') if history_entry.additional_params else 'realistic'
            
            logger.info(f"Пересоздание изображения: промпт='{prompt_to_use[:100]}...', стиль='{style_to_use}'")

            # Генерируем изображение
            try:
                success, new_result, _ = await gigachat_service.generate_image(
                    prompt=prompt_to_use,
                    style=style_to_use,
                    credentials=user_api_key
                )
                if not success:
                    # new_result содержит сообщение об ошибке (может быть специальное сообщение для 429 или таймаута)
                    error_message = new_result if isinstance(new_result, str) else "❌ Не удалось создать изображение. Попробуйте позже или уточните запрос."
                    await wait_msg.edit_text(
                        error_message,
                        reply_markup=regenerate_button
                    )
                    # НЕ удаляем запись из истории - она может быть полезна для отладки
                    # await content_history_repo.db_session.delete(new_history_entry)
                    # await content_history_repo.db_session.commit()
                    return
            except Exception as img_exc:
                logger.error(f"Ошибка генерации изображения: {img_exc}", exc_info=True)
                await wait_msg.edit_text(
                    "❌ Не удалось создать изображение. Попробуйте позже или уточните запрос.",
                    reply_markup=regenerate_button
                )
                # НЕ удаляем запись из истории - она может быть полезна для отладки
                # await content_history_repo.db_session.delete(new_history_entry)
                # await content_history_repo.db_session.commit()
                return

            await wait_msg.delete()
            
            # Отправляем изображение
            sent_message = await cb.message.answer_photo(
                photo=FSInputFile(new_result),
                caption="🖼 Вот ваше новое изображение:",
                reply_markup=get_regenerate_keyboard(new_history_entry.id)
            )
            
            # Сохраняем file_id и коммитим
            if sent_message.photo and len(sent_message.photo) > 0:
                new_history_entry.result = sent_message.photo[-1].file_id
            else:
                logger.error("Не удалось получить file_id из отправленного фото")
                new_history_entry.result = "Ошибка сохранения изображения"
            # Сохраняем промт и стиль в новой записи для возможности дальнейшей перегенерации
            if history_entry.additional_params:
                new_history_entry.additional_params = {
                    **history_entry.additional_params,
                    "original_prompt": history_entry.additional_params.get('original_prompt', history_entry.prompt),
                    "final_prompt": prompt_to_use,
                    "style": style_to_use
                }
            await content_history_repo.db_session.commit()
            
            os.remove(new_result) # Удаляем временный файл
            return

        else:
            # Для других типов контента
            if content_type == "text_edit":
                new_result, _ = await gigachat_service.edit_text(
                    text=history_entry.additional_params.get('original_text', history_entry.prompt),
                    user_api_key=user_api_key
                )
            else:
                new_result, _ = await gigachat_service.generate_free_text(
                    user_idea=history_entry.prompt,
                    nko_data=nko_data,
                    user_api_key=user_api_key
                )

        # Сохраняем и редактируем текст
        if new_result:
            # Обновляем результат для новой записи
            new_history_entry.result = new_result
            await content_history_repo.db_session.commit()
            
            # Для контент-плана используем клавиатуру с кнопкой принятия плана
            if content_type == "content_plan":
                new_keyboard = get_accept_plan_keyboard(new_history_entry.id)
            else:
                new_keyboard = get_regenerate_keyboard(new_history_entry.id)
            
            try:
                await cb.message.edit_text(
                    new_result,
                    parse_mode="Markdown",
                    reply_markup=new_keyboard
                )
            except Exception:
                await cb.message.edit_text(
                    new_result,
                    reply_markup=new_keyboard
                )
        else:
            # Если перегенерация не удалась, НЕ удаляем запись - она может быть полезна для отладки
            # await content_history_repo.db_session.delete(new_history_entry)
            # await content_history_repo.db_session.commit()
            
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

@cb_router.callback_query(F.data == "accept_content_plan")
async def accept_content_plan(cb: CallbackQuery, content_plan_repo, notification_repo):
    """Обработка принятия контент-плана"""
    try:
        await cb.answer()
        await cb.message.edit_reply_markup(reply_markup=None)

        # Проверяем, является ли сообщение текстом
        if not cb.message.text:
            await cb.message.edit_text("❌ Не удалось принять контент-план: сообщение не содержит текст.")
            return

        plan_text = cb.message.text
        
        # Сохраняем план в базу данных
        await content_plan_repo.add_or_update_plan(
            tg_id=cb.from_user.id,
            plan_content=plan_text
        )
        
        # Создаем уведомления на основе плана
        # remove_user_notifications вызывается внутри create_notifications_from_plan
        from datetime import date
        created_notifications = await notification_repo.create_notifications_from_plan(
            tg_id=cb.from_user.id,
            plan_content=plan_text,
            current_date=date.today()
        )
        
        logger.info(f"Создано {len(created_notifications)} уведомлений для пользователя {cb.from_user.id}")
        
        # Меняем кнопку на "Отметить план"
        await cb.message.edit_text(
            plan_text,
            parse_mode="Markdown",
            reply_markup=get_unaccept_plan_keyboard()
        )
        
        # Отправляем сообщение об успешном принятии
        await cb.message.answer(
            "✅ Контент-план принят!",
            reply_markup=reply_kb.main_keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при принятии контент-плана: {e}")
        await cb.message.edit_text(
            "❌ Произошла ошибка при принятии контент-плана. Попробуйте позже.",
            reply_markup=reply_kb.main_keyboard
        )


@cb_router.callback_query(F.data == "unaccept_content_plan")
async def unaccept_content_plan(cb: CallbackQuery, content_plan_repo, notification_repo, content_history_repo):
    """Обработка отмены принятия контент-плана"""
    try:
        await cb.answer()
        await cb.message.edit_reply_markup(reply_markup=None)

        # Удаляем план из базы данных
        await content_plan_repo.remove_plan(tg_id=cb.from_user.id)
        
        # Удаляем все уведомления пользователя
        await notification_repo.remove_user_notifications(tg_id=cb.from_user.id)
        
        # Восстанавливаем оригинальный текст сообщения
        plan_text = cb.message.text
        
        # Находим последнюю запись контент-плана для получения history_id
        history_entries = await content_history_repo.get_user_content_history(
            tg_id=cb.from_user.id,
            limit=10
        )
        # Фильтруем по типу контент-плана и берем первую запись
        content_plan_entries = [e for e in history_entries if e.content_type == "content_plan"]
        history_id = content_plan_entries[0].id if content_plan_entries else None
        
        # Возвращаем кнопку "Принять план" и "Пересоздать контент"
        if history_id:
            await cb.message.edit_text(
                plan_text,
                parse_mode="Markdown",
                reply_markup=get_accept_plan_keyboard(history_id)
            )
        else:
            # Если history_id не найден, используем клавиатуру без кнопки перегенерации
            from keyboards.inline_keyboards import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✅ Принять контент-план", 
                        callback_data="accept_content_plan"
                    )]
                ]
            )
            await cb.message.edit_text(
                plan_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        
        await cb.message.answer(
            "❌ Контент-план отменён.",
            reply_markup=reply_kb.main_keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене принятия контент-плана: {e}")
        await cb.message.edit_text(
            "❌ Произошла ошибка при отмене принятия контент-плана. Попробуйте позже.",
            reply_markup=reply_kb.main_keyboard
        )


@cb_router.callback_query(F.data == "generate_daily_post")
async def generate_daily_post(cb: CallbackQuery, nko_repo, content_history_repo, ai_api_repo):
    """Генерация поста на тему из уведомления контент-плана"""
    try:
        await cb.answer()
        
        # Извлекаем тему из сообщения уведомления
        # Формат: "**28.11 — Призыв к поддержке: Почему вам стоит помочь нам сейчас?**"
        notification_text = cb.message.text or ""
        
        # Убираем markdown форматирование и извлекаем тему
        import re
        # Убираем ** в начале и конце
        clean_text = re.sub(r'^\*\*|\*\*$', '', notification_text).strip()
        
        # Разделяем на дату и тему
        if '—' in clean_text:
            parts = clean_text.split('—', 1)
        elif ' - ' in clean_text:
            parts = clean_text.split(' - ', 1)
        elif '|' in clean_text:
            parts = clean_text.split('|', 1)
        else:
            # Если нет разделителя, используем весь текст как тему
            parts = ['', clean_text]
        
        topic = parts[1].strip() if len(parts) > 1 else clean_text
        
        if not topic:
            await cb.message.answer("❌ Не удалось извлечь тему из уведомления.")
            return
        
        # Получаем данные НКО пользователя
        nko_data = await nko_repo.get_nko_data(cb.from_user.id)
        
        # Получаем пользовательский API ключ
        user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
        user_api_key = user_api.api_key if user_api and user_api.connected else None
        
        # Проверяем размер очереди перед генерацией
        from utils.generation_queue import get_generation_queue
        queue = get_generation_queue()
        queue_size = queue._queue.qsize()
        
        # Отправляем сообщение о начале генерации
        if queue_size > 0:
            msg = await cb.message.answer(
                f"⏳ Ваш запрос поставлен в очередь (позиция: {queue_size + 1}). "
                f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
            )
        else:
            msg = await cb.message.answer("📝 Генерирую пост на тему... Пожалуйста, подождите🔄️")
        
        # Callback для обновления сообщения при начале обработки
        async def update_message():
            try:
                await msg.edit_text("📝 Генерирую пост на тему... Пожалуйста, подождите🔄️")
            except:
                pass
        
        # Генерируем пост на основе темы
        result, position = await gigachat_service.generate_free_text(
            user_idea=topic,
            nko_data=nko_data,
            user_api_key=user_api_key,
            on_start_callback=update_message
        )
        
        # Сохраняем в историю
        history_entry = await content_history_repo.add_content_history(
            tg_id=cb.from_user.id,
            content_type="free_text",
            prompt=topic,
            result=result,
            model="gigachat",
            additional_params={
                "from_notification": True,
                "notification_topic": topic
            }
        )
        
        # Отправляем результат с кнопкой перегенерации
        try:
            await msg.edit_text(
                result,
                parse_mode="Markdown",
                reply_markup=get_regenerate_keyboard(history_entry.id)
            )
        except:
            await msg.edit_text(
                result,
                reply_markup=get_regenerate_keyboard(history_entry.id)
            )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации поста из уведомления: {e}", exc_info=True)
        await cb.message.answer("❌ Произошла ошибка при генерации поста. Попробуйте позже.")


@cb_router.callback_query(F.data == "view_content_plan")
async def view_content_plan(cb: CallbackQuery, content_plan_repo, notification_repo):
    """Просмотр контент-плана с темами и статусами"""
    try:
        await cb.answer()
        
        # Получаем контент-план пользователя
        plan = await content_plan_repo.get_plan_by_user_id(cb.from_user.id)
        if not plan:
            await cb.message.answer("❌ У вас нет активного контент-плана.")
            return
        
        # Получаем все уведомления пользователя
        notifications = await notification_repo.get_user_notifications(cb.from_user.id)
        
        # Создаем словарь для быстрого поиска статуса по теме
        notification_dict = {}
        for notif in notifications:
            key = f"{notif.content_date} — {notif.content_topic}"
            notification_dict[key] = notif
        
        # Парсим контент-план и формируем сообщение
        from datetime import date
        current_date = date.today()
        lines = plan.plan_content.strip().split('\n')
        
        plan_text = "📅 **Ваш контент-план:**\n\n"
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем разделитель
            if '—' in line:
                parts = line.split('—', 1)
            elif '|' in line:
                parts = line.split('|', 1)
            elif ' - ' in line:
                parts = line.split(' - ', 1)
            else:
                plan_text += f"{line}\n"
                continue
            
            if len(parts) < 2:
                plan_text += f"{line}\n"
                continue
            
            date_str = parts[0].strip()
            topic = parts[1].strip()
            
            # Убираем markdown форматирование из темы для поиска
            import re
            topic_clean = re.sub(r'(\*\*|__)(.*?)\1', r'\2', topic)
            topic_clean = re.sub(r'(\*|_)(.*?)\1', r'\2', topic_clean)
            
            # Ищем статус уведомления
            # Пробуем разные варианты ключей для поиска
            key_variants = [
                f"{date_str} — {topic_clean}",
                f"{date_str} - {topic_clean}",
                f"{date_str}|{topic_clean}"
            ]
            
            status = "⏳ Предстоит"
            notif = None
            
            for key in key_variants:
                if key in notification_dict:
                    notif = notification_dict[key]
                    break
            
            if notif:
                if notif.sent:
                    status = "✅ Отправлено"
                else:
                    # Проверяем, прошла ли дата
                    from datetime import datetime
                    if isinstance(notif.notification_date, datetime):
                        notif_date = notif.notification_date.date()
                    else:
                        notif_date = notif.notification_date
                    
                    if notif_date < current_date:
                        status = "⏰ Пропущено"
                    else:
                        status = "⏳ Предстоит"
            
            plan_text += f"{date_str} — {topic} {status}\n"
        
        # Отправляем сообщение
        try:
            await cb.message.answer(plan_text, parse_mode="Markdown")
        except:
            await cb.message.answer(plan_text)
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре контент-плана: {e}", exc_info=True)
        await cb.message.answer("❌ Произошла ошибка при просмотре контент-плана. Попробуйте позже.")


@cb_router.callback_query(F.data == "create_new_content_plan")
async def create_new_content_plan(cb: CallbackQuery, state: FSMContext):
    """Начало создания нового контент-плана"""
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Введите период для контент-плана (например, 'неделя', 'месяц', 'квартал'):")
    await state.set_state(ContentPlanState.entering_period)