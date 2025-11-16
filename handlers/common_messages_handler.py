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
    await message.answer(texts.START_TEXT,reply_markup=inline_kb.main_keyboard)
    await user_repo.create_user(message.from_user.id)

@msg_router.message(Command("help"))
async def help_cmd(message: Message):
    """Обработка команды help"""
    await message.answer(texts.PASS_TEXT)

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
        await message.answer(texts.NKO_FILLED.format(
            name=nko_data.name,
            description=nko_data.description,
            activity=nko_data.activities
        ), reply_markup=inline_kb.nko_edit_info_keyboard)
        return
    await message.answer(texts.NKO_EMPTY,reply_markup=inline_kb.nko_add_info_keyboard)

