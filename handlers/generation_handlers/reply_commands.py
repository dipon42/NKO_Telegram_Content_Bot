import logging
import asyncio
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from database.repositories import ContentHistoryRepository, AIAPIRepository
from ai_service.gigachat_ai_service import get_gigachat_service
from keyboards.inline_keyboards import get_regenerate_keyboard
from utils.generation_queue import get_generation_queue

reply_commands_router = Router(name="Reply Commands Router")
logger = logging.getLogger(__name__)


@reply_commands_router.message(Command("картинка", "image"))
async def create_image_from_text(message: Message, ai_api_repo: AIAPIRepository, 
                                  content_history_repo: ContentHistoryRepository, 
                                  gigachat_service=None):
    """Создание изображения для поста исходя из его текста (работает только на ответ на сообщение)"""
    
    # Получаем gigachat_service если он не был передан
    if gigachat_service is None:
        gigachat_service = get_gigachat_service()
    
    # Проверяем, что сообщение является ответом и содержит текст или подпись
    if not message.reply_to_message:
        await message.answer(
            "❌ Эта команда работает только при ответе на сообщение.\n\n"
            "📝 Как использовать:\n"
            "1. Найдите сообщение с текстом поста (или изображение с подписью)\n"
            "2. Ответьте на это сообщение командой /картинка\n"
            "3. Бот создаст изображение для поста",
            parse_mode=None
        )
        return
    
    # Проверяем наличие текста или подписи (caption) в сообщении
    post_text = message.reply_to_message.text or message.reply_to_message.caption
    if not post_text:
        await message.answer("❌ Сообщение, на которое вы ответили, не содержит текста или подписи. Ответьте на сообщение с текстом или изображением с подписью.", parse_mode=None)
        return
    
    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None
    
    # Проверяем размер очереди перед генерацией
    queue = get_generation_queue(user_api_key)
    pending_tasks = queue.get_pending_tasks_count()
    
    # Отправляем сообщение о начале генерации
    if pending_tasks > 0:
        msg = await message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {pending_tasks + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        msg = await message.answer("🎨 Создаю изображение для поста... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")
    
    # Callback для обновления сообщения при начале обработки
    async def update_message():
        try:
            await msg.edit_text("🎨 Создаю изображение для поста... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")
        except:
            pass
    
    try:
        # Сначала улучшаем промпт на основе текста поста
        enhanced_prompt, _ = await gigachat_service.enhance_image_prompt(
            user_prompt=f"Создай изображение для поста в соцсетях на тему: {post_text}",
            user_api_key=user_api_key,
            on_start_callback=update_message if pending_tasks == 0 else None
        )
        await msg.edit_text("Улучшаю промпт...")
        await asyncio.sleep(3)
        await msg.edit_text(" Создаю изображение для поста... Это может занять до 30 секунд. Подождите, пожалуйста... ⏳")

        # Генерируем изображение с улучшенным промптом (используем стиль по умолчанию - реализм)
        success, image_url, position = await gigachat_service.generate_image(
            prompt=enhanced_prompt,
            style="реализм",
            credentials=user_api_key,
            on_start_callback=update_message if pending_tasks > 0 else None
        )
        
        if success and image_url:
            await msg.delete()
            await asyncio.sleep(0.1)
            
            # Отправляем изображение
            photo = await message.answer_photo(
                photo=FSInputFile(image_url),
                caption=f"🖼 Изображение для поста:\n\n{post_text[:200]}..." if len(post_text) > 200 else f"🖼 Изображение для поста:\n\n{post_text}"
            )
            
            # Сохраняем в историю
            history_entry = await content_history_repo.add_content_history(
                tg_id=message.from_user.id,
                content_type="image_generation",
                prompt=enhanced_prompt,  # Сохраняем улучшенный промпт
                result=photo.photo[-1].file_id if photo.photo else None,
                model="gigachat",
                additional_params={
                    "original_text": post_text,
                    "enhanced_prompt": enhanced_prompt,
                    "was_enhanced": True,
                    "style": "реализм"
                }
            )
            
            # Удаляем временный файл
            try:
                if os.path.exists(image_url):
                    os.remove(image_url)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {image_url}: {e}")
            
            # Редактируем подпись с кнопкой перегенерации
            if photo.photo and len(photo.photo) > 0:
                await photo.edit_caption(
                    caption=f"🖼 Изображение для поста:\n\n{post_text[:200]}..." if len(post_text) > 200 else f"🖼 Изображение для поста:\n\n{post_text}",
                    reply_markup=get_regenerate_keyboard(history_entry.id)
                )
        else:
            error_message = image_url if isinstance(image_url, str) else "Не удалось создать изображение. Попробуйте еще раз."
            await msg.edit_text(error_message)
            
    except Exception as e:
        logger.error(f"Ошибка при создании изображения для поста: {e}", exc_info=True)
        await msg.edit_text("❌ Произошла ошибка при создании изображения. Попробуйте позже.")


@reply_commands_router.message(Command("измени", "edit", "edit_with_wishes"))
async def edit_text_with_wishes(message: Message, ai_api_repo: AIAPIRepository,
                                content_history_repo: ContentHistoryRepository,
                                gigachat_service=None):
    """Редактирование текста согласно пожеланиям пользователя (работает только на ответ на сообщение)"""
    
    # Получаем gigachat_service если он не был передан
    if gigachat_service is None:
        gigachat_service = get_gigachat_service()
    
    # Проверяем, что сообщение является ответом и содержит текст или подпись
    if not message.reply_to_message:
        await message.answer(
            "❌ Эта команда работает только при ответе на сообщение.\n\n"
            "📝 Как использовать:\n"
            "1. Найдите сообщение с текстом, который хотите отредактировать (или изображение с подписью)\n"
            "2. Ответьте на это сообщение командой /измени (ваши пожелания)\n"
            "3. Например: /измени сделать короче и добавить эмодзи",
            parse_mode=None
        )
        return
    
    # Проверяем наличие текста или подписи (caption) в сообщении
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    if not original_text:
        await message.answer("❌ Сообщение, на которое вы ответили, не содержит текста или подписи. Ответьте на сообщение с текстом или изображением с подписью.", parse_mode=None)
        return
    
    # Извлекаем пожелания из команды
    # Команда может быть в формате: /измени сделать короче или /измени <пожелания>
    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)
    user_wishes = parts[1] if len(parts) > 1 else None
    
    if not user_wishes:
        await message.answer("❌ Укажите пожелания по редактированию текста. Например: /измени сделать короче и более эмоционально")
        return
    
    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None
    
    # Проверяем размер очереди перед генерацией
    queue = get_generation_queue(user_api_key)
    pending_tasks = queue.get_pending_tasks_count()
    
    # Отправляем сообщение о начале редактирования
    if pending_tasks > 0:
        msg = await message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {pending_tasks + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        msg = await message.answer("✏️ Редактирую текст согласно вашим пожеланиям... Пожалуйста, подождите🔄️")
    
    # Callback для обновления сообщения при начале обработки
    async def update_message():
        try:
            await msg.edit_text("✏️ Редактирую текст согласно вашим пожеланиям... Пожалуйста, подождите🔄️")
        except:
            pass
    
    try:
        # Редактируем текст с учетом пожеланий пользователя (используем специальный метод)
        result, position = await gigachat_service.edit_text_with_wishes(
            text=original_text,
            user_wishes=user_wishes,
            user_api_key=user_api_key,
            on_start_callback=update_message
        )
        
        # Сохраняем в историю
        history_entry = await content_history_repo.add_content_history(
            tg_id=message.from_user.id,
            content_type="text_edit",
            prompt=original_text,
            result=result,
            model="gigachat",
            additional_params={
                "original_text": original_text,
                "user_wishes": user_wishes
            }
        )
        
        # Отправляем результат
        try:
            await msg.edit_text(result, parse_mode="Markdown", reply_markup=get_regenerate_keyboard(history_entry.id))
        except:
            await msg.edit_text(result, reply_markup=get_regenerate_keyboard(history_entry.id))
            
    except Exception as e:
        logger.error(f"Ошибка при редактировании текста с пожеланиями: {e}", exc_info=True)
        await msg.edit_text("❌ Произошла ошибка при редактировании текста. Попробуйте позже.")

