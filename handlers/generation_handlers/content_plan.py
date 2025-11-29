from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from fsm import ContentPlanState
from keyboards.inline_keyboards import get_regenerate_keyboard, content_plan_type_keyboard, get_accept_plan_keyboard, \
    nko_add_info_keyboard
from utils.generation_queue import get_generation_queue

cp_router = Router(name="AI Content Plan Router")


@cp_router.message(F.text == "Создать контент-план 📅")
async def content_plan_start(message: Message, state: FSMContext, content_plan_repo):
    """Начало процесса создания контент-плана"""
    # Проверяем, есть ли у пользователя активный контент-план
    plan = await content_plan_repo.get_plan_by_user_id(message.from_user.id)
    
    if plan:
        # Если есть план, предлагаем выбор: создать новый или посмотреть существующий
        from keyboards.inline_keyboards import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Посмотреть контент-план",
                    callback_data="view_content_plan"
                )],
                [InlineKeyboardButton(
                    text="📅 Создать новый контент-план",
                    callback_data="create_new_content_plan"
                )]
            ]
        )
        await message.answer(
            "У вас уже есть активный контент-план. Что вы хотите сделать?",
            reply_markup=keyboard
        )
        return
    
    await message.answer("Введите период для контент-плана (например, 'неделя', 'месяц', 'квартал'):")
    await state.set_state(ContentPlanState.entering_period)


@cp_router.message(ContentPlanState.entering_period)
async def period_entered(message: Message, state: FSMContext):
    """Обработка введенного периода"""
    await state.update_data(period=message.text)
    await message.answer("Введите частоту публикаций (например, 'ежедневно', '3 раза в неделю'):")
    await state.set_state(ContentPlanState.entering_frequency)


@cp_router.message(ContentPlanState.entering_frequency)
async def frequency_entered(message: Message, state: FSMContext):
    """Обработка введенной частоты и выбор способа создания контент-плана"""
    await state.update_data(frequency=message.text)

    # Предлагаем выбор способа создания контент-плана
    await message.answer(
        "Какой контент-план вы хотите создать?",
        reply_markup=content_plan_type_keyboard
    )
    await state.set_state(ContentPlanState.choosing_plan_type)


@cp_router.callback_query(F.data == "content_plan_from_data")
async def plan_from_data_selected(cb: CallbackQuery, state: FSMContext, nko_repo, content_history_repo, ai_api_repo,
                                  gigachat_service):
    """Обработка выбора создания плана на основе данных НКО"""
    await cb.answer()

    # Получаем сохраненные данные
    data = await state.get_data()

    # Получаем данные НКО указанные пользователем
    nko_data = await nko_repo.get_nko_data(cb.from_user.id)
    user_api = await ai_api_repo.get_user_api_key(cb.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    if nko_data and nko_data.name:
        # Проверяем размер очереди перед генерацией
        queue = get_generation_queue(user_api_key)
        pending_tasks = queue.get_pending_tasks_count()
        
        # Показываем статус генерации ПЕРЕД началом генерации
        if pending_tasks > 0:
            msg = await cb.message.edit_text(
                f"⏳ Ваш запрос поставлен в очередь (позиция: {pending_tasks + 1}). "
                f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
            )
        else:
            msg = await cb.message.edit_text("Генерация контент-плана на основе данных... Пожалуйста, подождите🔄️")
        
        # Callback для обновления сообщения при начале обработки
        async def update_message():
            try:
                await msg.edit_text("Генерация контент-плана на основе данных... Пожалуйста, подождите🔄️")
            except:
                pass
        
        # Используем данные НКО для генерации плана
        result, position = await gigachat_service.generate_content_plan(
            period=data["period"],
            frequency=data["frequency"],
            nko_data=nko_data,
            user_api_key=user_api_key,  # Используем ключ по умолчанию
            on_start_callback=update_message
        )

        # Сохраняем результат в историю
        history_entry = await content_history_repo.add_content_history(
            tg_id=cb.from_user.id,
            content_type="content_plan",
            prompt=f"Период: {data['period']}, Частота: {data['frequency']}",
            result=result,
            model="gigachat",
            additional_params={
                "period": data["period"],
                "frequency": data["frequency"],
                "nko_focus": (nko_data.activities if nko_data and nko_data.activities else "благотворительность")
            }
        )

        # Отправляем результат с кнопкой принятия плана
        await msg.edit_text(result, reply_markup=get_accept_plan_keyboard(history_entry.id), parse_mode="Markdown")

        await state.clear()
    else:
        await cb.message.edit_text(
            "К сожалению, у вас не заполнены данные об НКО. Пожалуйста, заполните их для создания плана на основе данных.",
            reply_markup=nko_add_info_keyboard
        )
        await state.clear()


@cp_router.callback_query(F.data == "content_plan_with_goal")
async def plan_with_goal_selected(cb: CallbackQuery, state: FSMContext):
    """Обработка выбора создания плана по цели"""
    await cb.answer()
    await cb.message.edit_text(
        "Введите цель вашего контент-плана (например: привлечь волонтёров, собрать средства на мероприятие и т.д.):")
    await state.set_state(ContentPlanState.entering_goal)


@cp_router.message(ContentPlanState.entering_goal)
async def goal_entered(message: Message, state: FSMContext, nko_repo, content_history_repo, ai_api_repo,
                       gigachat_service):
    """Обработка введенной цели контент-плана"""
    await state.update_data(goal=message.text)
    data = await state.get_data()

    # Получаем данные НКО указанные пользователем
    nko_data = await nko_repo.get_nko_data(message.from_user.id)
    user_api = await ai_api_repo.get_user_api_key(message.from_user.id, "GigaChat")
    user_api_key = user_api.api_key if user_api and user_api.connected else None

    # Проверяем размер очереди перед генерацией
    queue = get_generation_queue(user_api_key)
    pending_tasks = queue.get_pending_tasks_count()
    
    # Показываем статус генерации ПЕРЕД началом генерации
    if pending_tasks > 0:
        msg = await message.answer(
            f"⏳ Ваш запрос поставлен в очередь (позиция: {pending_tasks + 1}). "
            f"Ожидайте...\n\n💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
        )
    else:
        msg = await message.answer("Генерация контент-плана на основе цели... Пожалуйста, подождите🔄️")
    
    # Callback для обновления сообщения при начале обработки
    async def update_message():
        try:
            await msg.edit_text("Генерация контент-плана на основе цели... Пожалуйста, подождите🔄️")
        except:
            pass
    
    # Генерируем контент-план с учетом цели
    result, position = await gigachat_service.generate_content_plan(
        period=data["period"],
        frequency=data["frequency"],
        nko_data=nko_data,
        user_goal=data["goal"],
        user_api_key=user_api_key,  # Используем ключ по умолчанию
        on_start_callback=update_message
    )

    # Сохраняем результат в историю
    history_entry = await content_history_repo.add_content_history(
        tg_id=message.from_user.id,
        content_type="content_plan",
        prompt=f"Период: {data['period']}, Частота: {data['frequency']}, Цель: {data['goal']}",
        result=result,
        model="gigachat",
        additional_params={
            "period": data["period"],
            "frequency": data["frequency"],
            "user_goal": data["goal"]
        }
    )

    # Отправляем результат с кнопкой принятия плана
    await msg.edit_text(result, reply_markup=get_accept_plan_keyboard(history_entry.id), parse_mode="Markdown")

    await state.clear()