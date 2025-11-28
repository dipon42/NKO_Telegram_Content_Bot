import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

import texts
from keyboards import reply_kb,inline_kb


msg_router = Router(name="Message router")
logger = logging.getLogger(__name__)

@msg_router.message(CommandStart())
async def start_cmd(message: Message, user_repo):
    """Обработка команды start"""
    await message.answer(texts.START_TEXT, reply_markup=inline_kb.main_keyboard, parse_mode="HTML")
    await user_repo.create_user(message.from_user.id)

@msg_router.message(Command("help"))
async def help_cmd(message: Message):
    """Обработка команды help"""
    await message.answer(texts.HELP_TEXT, parse_mode="HTML")

@msg_router.message(Command("отмена","cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    """Обработка команды отмена"""
    await message.answer("Ввод отменен",reply_markup=reply_kb.main_keyboard)
    await state.clear()

@msg_router.message(Command("menu","меню"))
async def menu_cmd(message: Message):
    """Обработка команды меню"""
    await message.answer("Выберите действие из кнопок меню\n\n<b>Или напишите вашу идею и я сразу создам текст!</b>",
                         reply_markup=reply_kb.main_keyboard)

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
        return
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

