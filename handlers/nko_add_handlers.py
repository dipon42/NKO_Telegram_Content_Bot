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
    await cb.message.answer("Введите наименование НКО:", reply_markup=reply_kb.skip_keyboard)
    await state.set_state(AddInfoNkoStateGroup.name)

@fsm_router.message(AddInfoNkoStateGroup.name)
async def add_name_nko(message: Message, state: FSMContext):
    """Обработчик ввода наименования НКО"""
    if message.text.strip().lower() == "пропустить":
        await state.update_data(name=None)
        await message.answer("Опишите НКО, его цели, основные задачи и т.д.:", reply_markup=reply_kb.skip_keyboard)
        await state.set_state(AddInfoNkoStateGroup.description)
        return
    
    name = message.text
    if not name:
        await message.answer("Наименование НКО не может быть пустым. Пожалуйста, введите наименование НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if len(name) > 255:
        await message.answer("Наименование НКО не может быть длиннее 255 символов. Пожалуйста, введите наименование НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if name.isdigit():
        await message.answer("Наименование НКО не может состоять только из цифр. Пожалуйста, введите наименование НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return

    await state.update_data(name=message.text)
    await message.answer("Опишите НКО, его цели, основные задачи и т.д.:", reply_markup=reply_kb.skip_keyboard)
    await state.set_state(AddInfoNkoStateGroup.description)

@fsm_router.message(AddInfoNkoStateGroup.description)
async def add_description_nko(message: Message, state: FSMContext):
    """Обработчик ввода описания НКО"""
    if message.text.strip().lower() == "пропустить":
        await state.update_data(description=None)
        await message.answer("Опишите формы деятельности НКО:", reply_markup=reply_kb.skip_keyboard)
        await state.set_state(AddInfoNkoStateGroup.forms_of_activity)
        return
    
    description = message.text
    if not description:
        await message.answer("Описание НКО не может быть пустым. Пожалуйста, введите описание НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if len(description) > 1000:
        await message.answer("Описание НКО не может быть длиннее 1000 символов. Пожалуйста, введите описание НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if description.isdigit():
        await message.answer("Описание НКО не может состоять только из цифр. Пожалуйста, введите описание НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return

    await state.update_data(description=message.text)
    await message.answer("Опишите формы деятельности НКО:", reply_markup=reply_kb.skip_keyboard)
    await state.set_state(AddInfoNkoStateGroup.forms_of_activity)

@fsm_router.message(AddInfoNkoStateGroup.forms_of_activity)
async def add_forms_of_activity_nko(message: Message, state: FSMContext):
    """Обработчик ввода форм деятельности НКО"""
    if message.text.strip().lower() == "пропустить":
        await state.update_data(activities=None)
        await message.answer("Введите приблизительное количество людей в организации (только число):", reply_markup=reply_kb.skip_keyboard)
        await state.set_state(AddInfoNkoStateGroup.organization_size)
        return
    
    forms_of_activity = message.text
    if not forms_of_activity:
        await message.answer("Формы деятельности НКО не могут быть пустыми. Пожалуйста, введите формы деятельности НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if len(forms_of_activity) > 1000:
        await message.answer("Формы деятельности НКО не могут быть длиннее 1000 символов. Пожалуйста, введите формы деятельности НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    if forms_of_activity.isdigit():
        await message.answer("Формы деятельности НКО не могут состоять только из цифр. Пожалуйста, введите формы деятельности НКО или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
        return
    
    await state.update_data(activities=message.text)
    await message.answer("Введите приблизительное количество людей в организации (только число):", reply_markup=reply_kb.skip_keyboard)
    await state.set_state(AddInfoNkoStateGroup.organization_size)

@fsm_router.message(AddInfoNkoStateGroup.organization_size)
async def add_organization_size_nko(message: Message, state: FSMContext, nko_repo):
    """Обработчик ввода размера организации"""
    if message.text.strip().lower() == "пропустить":
        await state.update_data(organization_size=None)
    else:
        try:
            size = int(message.text)
            if size <= 0:
                await message.answer("Количество людей должно быть положительным числом. Пожалуйста, введите корректное значение:")
                return
            if size > 1000000:
                await message.answer("Количество людей слишком велико. Пожалуйста, введите реалистичное значение:")
                return
            await state.update_data(organization_size=size)
        except ValueError:
            await message.answer("Пожалуйста, введите число или нажмите 'Пропустить':", reply_markup=reply_kb.skip_keyboard)
            return
    
    data = await state.get_data()
    await nko_repo.save_nko_data(message.from_user.id, data)
    await message.answer("Информация о НКО успешно сохранена и будет использоваться при создании контента! 🎉")
    await  asyncio.sleep(1.25)
    await message.answer(texts.START_TEXT, reply_markup=reply_kb.main_keyboard, parse_mode="HTML")
    await state.clear()