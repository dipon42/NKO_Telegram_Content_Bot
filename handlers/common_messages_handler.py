import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

import texts
from keyboards import reply_kb,inline_kb
from handlers.utils import should_show_access_button, build_user_main_keyboard


msg_router = Router(name="Message router")
logger = logging.getLogger(__name__)


def _extract_start_payload(message: Message) -> str | None:
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        payload = parts[1].strip()
        return payload or None
    return None


async def _activate_invite_link(code: str, message: Message, user, access_repo, user_repo):
    link = await access_repo.get_by_code(code)
    if not link:
        await message.answer("❌ Приглашение не найдено или устарело.")
        return user

    if not link.is_active:
        await message.answer("⚠️ Эта ссылка уже деактивирована.")
        return user

    if link.max_activations and link.activations_used >= link.max_activations:
        await message.answer("⚠️ Лимит использований ссылки исчерпан.")
        return user

    if user.access:
        await message.answer("У вас уже активирован доступ, дополнительная ссылка не требуется.")
        return user

    updated_user = await user_repo.set_access_and_role(
        tg_id=user.tg_id,
        access=True,
        role=link.role,
        invited_link_id=link.id,
    )
    await access_repo.register_activation(link)
    await message.answer(texts.ACCESS_SUCCESS_TEXT, parse_mode="HTML", reply_markup=inline_kb.main_keyboard)
    return updated_user

@msg_router.message(CommandStart())
async def start_cmd(message: Message, user_repo, access_repo):
    """Обработка команды start"""
    user = await user_repo.create_user(message.from_user.id)
    payload = _extract_start_payload(message)
    if payload:
        user = await _activate_invite_link(payload, message, user, access_repo, user_repo)

    if user.access:
        await message.answer(
            texts.START_TEXT,
            reply_markup=reply_kb.build_main_keyboard(should_show_access_button(user)),
            parse_mode="HTML"
        )
    else:
        await message.answer(texts.ACCESS_REQUIRED_TEXT, parse_mode="HTML")

@msg_router.message(Command("help"))
async def help_cmd(message: Message):
    """Обработка команды help"""
    await message.answer(texts.HELP_TEXT, parse_mode="HTML")

@msg_router.message(Command("отмена","cancel"))
async def cancel_cmd(message: Message, state: FSMContext, user_repo):
    """Обработка команды отмена"""
    keyboard = await build_user_main_keyboard(user_repo, message.from_user.id)
    await message.answer("Ввод отменен",reply_markup=keyboard)
    await state.clear()

@msg_router.message(Command("menu","меню"))
async def menu_cmd(message: Message, user_repo):
    """Обработка команды меню"""
    keyboard = await build_user_main_keyboard(user_repo, message.from_user.id)
    await message.answer("Выберите действие из кнопок меню\n\n<b>Или напишите вашу идею и я сразу создам текст!</b>",
                         reply_markup=keyboard)

@msg_router.message(F.text == "Информация об НКО")
async def info_nko(message: Message, nko_repo):
    """Заполнение/просмотр информации об НКО"""
    nko_data = await nko_repo.get_nko_data(message.from_user.id)
    if nko_data:
        # Формируем текст с учетом наличия всех полей
        info_text = "Информация о вашем НКО 📋:\n"
        
        if nko_data.name:
            info_text += f"📌 <b>Наименование:</b> {nko_data.name}\n"
        else:
            info_text += "📌 <b>Наименование:</b> не указано\n"
            
        if nko_data.description:
            info_text += f"📌 <b>Описание:</b> {nko_data.description}\n"
        else:
            info_text += "📌 <b>Описание:</b> не указано\n"
            
        if nko_data.activities:
            info_text += f"📌 <b>Формы деятельности:</b> {nko_data.activities}\n"
        else:
            info_text += "📌 <b>Формы деятельности:</b> не указано\n"
            
        if nko_data.organization_size:
            info_text += f"📌 <b>Количество людей в организации:</b> {nko_data.organization_size}\n"
        else:
            info_text += "📌 <b>Количество людей в организации:</b> не указано\n"
        
        info_text += "\nЧтобы обновить данные, нажмите «Редактировать данные»"
        
        await message.answer(info_text, reply_markup=inline_kb.nko_edit_info_keyboard)
    else:
        await message.answer(texts.NKO_EMPTY,reply_markup=inline_kb.nko_add_info_keyboard)

@msg_router.message(Command("test_notifications", "тест_уведомления"))
async def test_notifications_cmd(message: Message, notification_repo):
    """Тестовая команда для преждевременной отправки уведомлений на сегодня"""
    from datetime import datetime
    from handlers.scheduled_notifications import ScheduledNotifications
    
    try:
        # Создаем временный экземпляр ScheduledNotifications для отправки уведомлений
        scheduler = ScheduledNotifications(notification_repo)
        
        # Отправляем уведомления
        await scheduler.send_daily_notifications()
        
        await message.answer("✅ Тестовые уведомления отправлены!")
    except Exception as e:
        logger.error(f"Ошибка при отправке тестовых уведомлений: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при отправке уведомлений: {e}")

