import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.inline_keyboards import api_key_management_keyboard, confirm_replace_api_keyboard, \
    add_gigachat_api_keyboard
from fsm import APIKeyState, AddAPIkeyState


settings_router = Router(name="Settings Router")
logger = logging.getLogger(__name__)

@settings_router.message(F.text == "Настройки")
async def settings_command(message: Message, ai_api_repo):
    """Обработка команды настроек"""
    
    # Получаем API ключ
    gigachat_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    
    if gigachat_api:
        status_text = f"🔑 API ключ GigaChat: <b>{"установлен" if gigachat_api.api_key else "не установлен"}</b>\n"\
                      f"Модель: {gigachat_api.model_name}\n"\
                      f"Статус: {"Подключен" if gigachat_api.connected else "Отключен"}"
        kb = api_key_management_keyboard
    else:
        status_text = "❌ API ключ GigaChat: <b>не установлен</b>"
        kb = add_gigachat_api_keyboard

    await message.answer(f"Настройки:\n{status_text}", reply_markup=kb)


@settings_router.callback_query(F.data == "add_api_gigachat")
async def add_api_key_prompt(cb: CallbackQuery, state: FSMContext, ai_api_repo):
    """Запрос на ввод API ключа GigaChat"""
    await cb.message.edit_reply_markup(reply_markup=None)
    
    # Проверяем, есть ли уже API ключ
    existing_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    
    if existing_api:
        await cb.message.answer(
            "У вас уже есть API ключ GigaChat. Хотите его заменить?",
            reply_markup=confirm_replace_api_keyboard
        )
        await state.set_state(APIKeyState.confirming_replacement)
    else:
        await cb.message.answer("Введите ваш API ключ для GigaChat:")
        await state.set_state(AddAPIkeyState.entering_api_key)
    
    await cb.answer()


@settings_router.callback_query(F.data == "confirm_replace_api")
async def confirm_replace_api(cb: CallbackQuery, state: FSMContext, ai_api_repo, gigachat_service):
    """Подтверждение замены существующего API ключа"""
    existing_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    
    if not existing_api:
        await cb.message.edit_text("❌ Не найден существующий API ключ для замены.")
        await cb.answer()
        return
    
    data = await state.get_data()
    new_api_key = data.get("new_api_key")
    
    # Проверяем валидность нового API
    is_valid, validation_msg = await gigachat_service.validate_credentials(new_api_key)
    
    if not is_valid:
        await cb.message.edit_text(f"❌ Не удалось подключить API ключ, проверьте его и попробуйте снова!")
        await state.clear()
        await cb.answer()
        return
    
    # Обновляем API ключ в репозитории
    updated_api = await ai_api_repo.update_api_key(cb.from_user.id, "GigaChat", new_api_key)
    
    if updated_api:

        if updated_api.connected:
            await cb.message.edit_text("✅ API ключ GigaChat успешно заменен и подключен!")
        else:
            await cb.message.edit_text("⚠️ API ключ обновлен, но не подключен. Проверьте его работоспособность.")
    else:
        await cb.message.edit_text("❌ Не удалось обновить API ключ в базе данных.")
    
    await state.clear()
    await cb.answer()


@settings_router.callback_query(F.data == "cancel_replace_api")
async def cancel_replace_api(cb: CallbackQuery, state: FSMContext):
    """Отмена замены API ключа"""
    await cb.message.edit_text("❌ Добавление API ключа отменено.")
    await state.clear()
    await cb.answer()


@settings_router.callback_query(F.data == "view_tokens_gigachat")
async def view_tokens_gigachat(cb: CallbackQuery, ai_api_repo,gigachat_service):
    """Просмотр оставшихся токенов GigaChat"""
    gigachat_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    
    if not gigachat_api or not gigachat_api.connected:
        await cb.message.answer("❌ Для просмотра токенов необходимо сначала добавить API ключ GigaChat в настройках.")
    else:
        # Получаем информацию об оставшихся токенах через API
        has_tokens, tokens_msg = await gigachat_service.get_token_info(gigachat_api.api_key)
        await cb.message.answer(
            f"ℹ️ Текущая информация о токенах GigaChat:\n\n"
            f"Модель: {gigachat_api.model_name}\n"
            f"Статус: Подключен\n\n"
            f"{tokens_msg}"
        )
    
    await cb.answer()


@settings_router.callback_query(F.data == "change_api_gigachat")
async def change_api_gigachat(cb: CallbackQuery, state: FSMContext, ai_api_repo):
    """Изменение API ключа GigaChat"""
    await cb.message.edit_reply_markup(reply_markup=None)
    
    # Проверяем наличие существующего API ключа
    existing_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    
    if not existing_api:
        await cb.message.answer("❌ У вас еще нет API ключа GigaChat. Сначала добавьте его.")
        await cb.answer()
        return
        
    await cb.message.answer("Введите новый API ключ для GigaChat:")
    await state.set_state(APIKeyState.entering_api_key)
    await cb.answer()


@settings_router.message(APIKeyState.entering_api_key)
async def process_new_api_key(message: Message, state: FSMContext, ai_api_repo):
    """Обработка введенного API ключа и подтверждение замены"""
    new_api_key = message.text.strip()
    
    # Сохраняем новый ключ во временное состояние
    await state.update_data(new_api_key=new_api_key)
    
    # Получаем текущий API ключ
    current_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    
    # Запрашиваем подтверждение замены
    await message.answer(
        f"Вы уверены, что хотите заменить текущий API ключ?\n\n"
        f"Текущий ключ: {current_api.api_key if current_api else 'Не установлен'}\n"
        f"Новый ключ: {new_api_key[:5]}...{new_api_key[-3:]}\n\n"
        f"Подтвердите замену.",
        reply_markup=confirm_replace_api_keyboard
    )
    await state.set_state(APIKeyState.confirming_replacement)


@settings_router.message(AddAPIkeyState.entering_api_key)
async def add_api_key(message: Message, state: FSMContext, ai_api_repo, gigachat_service):
    """Добавление API ключа """
    api_key = message.text.strip()
    is_valid, validation_msg = await gigachat_service.validate_credentials(api_key)
    if is_valid:
        await ai_api_repo.create_api_key(message.from_user.id, "GigaChat", api_key)
        await message.answer("API ключ GigaChat успешно добавлен!")
        await state.clear()
    else:
        logger.error(f"Invalid API key: {validation_msg}")
        await message.answer(
            f"❌ Не удалось подключить API ключ, проверьте правильность ввода!"
        )
        return