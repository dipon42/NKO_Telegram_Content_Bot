import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import texts
from fsm import AddInfoNkoStateGroup
from keyboards import reply_kb

fsm_router = Router(name="NKO add info router")

@fsm_router.callback_query(F.data == "add_info_nko")
async def add_info_nko(cb: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить информацию о НКО'"""
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer()
    await cb.message.answer("Введите наименование НКО:")
    await state.set_state(AddInfoNkoStateGroup.name)

@fsm_router.message(AddInfoNkoStateGroup.name)
async def add_name_nko(message: Message, state: FSMContext):
    """Обработчик ввода наименования НКО"""
    name = message.text
    if not name:
        await message.answer("Наименование НКО не может быть пустым. Пожалуйста, введите наименование НКО:")
        return
    if len(name) > 255:
        await message.answer("Наименование НКО не может быть длиннее 100 символов. Пожалуйста, введите наименование НКО:")
        return
    if name.isdigit():
        await message.answer("Наименование НКО не может состоять только из цифр. Пожалуйста, введите наименование НКО:")
        return

    await state.update_data(name=message.text)
    await message.answer("Опишите НКО, его цели, основные задачи и т.д.:")
    await state.set_state(AddInfoNkoStateGroup.description)

@fsm_router.message(AddInfoNkoStateGroup.description)
async def add_description_nko(message: Message, state: FSMContext):
    """Обработчик ввода описания НКО"""
    description = message.text
    if not description:
        await message.answer("Описание НКО не может быть пустым. Пожалуйста, введите описание НКО:")
        return
    if len(description) > 1000:
        await message.answer("Описание НКО не может быть длиннее 1000 символов. Пожалуйста, введите описание НКО:")
        return
    if description.isdigit():
        await message.answer("Описание НКО не может состоять только из цифр. Пожалуйста, введите описание НКО:")
        return

    await state.update_data(description=message.text)
    await message.answer("Опишите формы деятельности НКО:")
    await state.set_state(AddInfoNkoStateGroup.forms_of_activity)

@fsm_router.message(AddInfoNkoStateGroup.forms_of_activity)
async def add_forms_of_activity_nko(message: Message, state: FSMContext, nko_repo):
    """Обработчик ввода форм деятельности НКО"""
    forms_of_activity = message.text
    if not forms_of_activity:
        await message.answer("Формы деятельности НКО не могут быть пустыми. Пожалуйста, введите формы деятельности НКО:")
        return
    if len(forms_of_activity) > 1000:
        await message.answer("Формы деятельности НКО не могут быть длиннее 1000 символов. Пожалуйста, введите формы деятельности НКО:")
        return
    if forms_of_activity.isdigit():
        await message.answer("Формы деятельности НКО не могут состоять только из цифр. Пожалуйста, введите формы деятельности НКО:")
        return
    await state.update_data(activities=message.text)
    data = await state.get_data()
    await nko_repo.save_nko_data(message.from_user.id, data)
    await message.answer("Информация о НКО успешно сохранена и будет использоваться при создании контента! 🎉")
    await  asyncio.sleep(1.25)
    await message.answer(texts.PASS_TEXT,reply_markup=reply_kb.main_keyboard)
    await state.clear()