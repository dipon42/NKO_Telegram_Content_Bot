from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from fsm import ContentPlanState
from keyboards.inline_keyboards import get_regenerate_keyboard

cp_router = Router(name="AI Content Plan Router")

@cp_router.message(F.text == "Создать контент-план 📅")
async def content_plan_start(message: Message, state: FSMContext):
    """Начало процесса создания контент-плана"""
    await message.answer("Введите период для контент-плана (например, 'неделя', 'месяц', 'квартал'):")
    await state.set_state(ContentPlanState.entering_period)

@cp_router.message(ContentPlanState.entering_period)
async def period_entered(message: Message, state: FSMContext):
    """Обработка введенного периода"""
    await state.update_data(period=message.text)
    await message.answer("Введите частоту публикаций (например, 'ежедневно', '3 раза в неделю'):")
    await state.set_state(ContentPlanState.entering_frequency)

@cp_router.message(ContentPlanState.entering_frequency)
async def frequency_entered(message: Message, state: FSMContext, nko_repo, content_history_repo, ai_api_repo, gigachat_service):
    """Обработка введенной частоты и генерация контент-плана"""
    await state.update_data(frequency=message.text)
    
    data = await state.get_data()
    
    # Получаем данные НКО указанные пользователем
    nko_data = await nko_repo.get_nko_data(message.from_user.id)
    

    nko_focus = "благотворительность"
    if nko_data:
        nko_focus = nko_data.activities if nko_data.activities else "благотворительность"  # По умолчанию - благотворительность
    
    # Получаем пользовательский API ключ
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Генерируем контент-план
    result = await gigachat_service.generate_content_plan(
        period=data["period"],
        frequency=data["frequency"],
        nko_focus=nko_focus,
        nko_data=nko_data,
        user_api_key=user_api_key
    )
    msg = await message.answer("Генерация текста... Пожалуйста, подождите🔄️")
    # Сохраняем в историю с дополнительными параметрами
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="content_plan",
        prompt=f"Период: {data['period']}, Частота: {data['frequency']}",
        result=result,
        model="gigachat",
        additional_params={
            "period": data["period"],
            "frequency": data["frequency"],
            "nko_focus": nko_focus
        }
    )

    # Создаем инлайн-кнопку для перегенерации с ID записи
    regenerate_keyboard = get_regenerate_keyboard(history_entry.id)

    # Отправляем результат с кнопкой перегенерации
    await msg.edit_text(result, reply_markup=regenerate_keyboard,parse_mode="Markdown")
    
    await state.clear()