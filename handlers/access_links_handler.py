import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from fsm import AccessLinkState
from keyboards.inline_keyboards import (
    access_admin_keyboard,
    access_nko_keyboard,
    access_link_inline_keyboard,
)


access_router = Router(name="Access links router")
logger = logging.getLogger(__name__)


def _is_admin(user) -> bool:
    return bool(user and user.role == "admin")


def _is_nko(user) -> bool:
    return bool(user and user.role in {"nko", "admin"})


async def _ensure_user(user_repo, tg_id: int):
    user = await user_repo.get_user(tg_id)
    if user is None:
        user = await user_repo.create_user(tg_id)
    return user


async def _build_deeplink(bot, code: str) -> str:
    me = await bot.get_me()
    if me.username:
        return f"https://t.me/{me.username}?start={code}"
    return code


def _format_link_info(link, include_creator: bool = False) -> str:
    limit = "∞" if link.max_activations is None else str(link.max_activations)
    used = link.activations_used
    status = "🟢 активна" if link.is_active else "⚪️ отключена"
    lines = [
        f"{status}",
        f"ID: <code>{link.id}</code>",
        f"Код: <code>{link.code}</code>",
        f"Использований: {used}/{limit}",
    ]
    if include_creator:
        lines.append(f"Создатель: {link.created_by}")
    if link.expires_at:
        expires = link.expires_at.strftime("%d.%m.%Y %H:%M")
        lines.append(f"Истекает: {expires}")
    return "\n".join(lines)


@access_router.message(Command("access"))
@access_router.message(F.text == "Управление доступом 🔐")
async def access_panel(message: Message, user_repo):
    user = await _ensure_user(user_repo, message.from_user.id)

    if _is_admin(user):
        await message.answer(
            "👩‍💼 Панель администратора. Управляйте приглашениями:",
            reply_markup=access_admin_keyboard,
        )
        return

    if _is_nko(user):
        await message.answer(
            "🔗 Управление ссылками доступа вашей НКО:",
            reply_markup=access_nko_keyboard,
        )
        return

    await message.answer(
        "Доступ к панели есть только у администраторов и подтвержденных НКО."
    )


@access_router.callback_query(F.data == "access_admin_create")
async def admin_create_link(cb: CallbackQuery, user_repo, access_repo):
    user = await _ensure_user(user_repo, cb.from_user.id)
    if not _is_admin(user):
        await cb.answer("Недостаточно прав", show_alert=True)
        return

    link = await access_repo.create_access_link(
        created_by=cb.from_user.id,
        max_activations=1,
        role="nko",
    )
    deeplink = await _build_deeplink(cb.message.bot, link.code)
    await cb.message.answer(
        "✅ Одноразовая ссылка создана:\n"
        f"{deeplink}\n\n"
        "Передайте её НКО, чтобы выдать доступ.",
        reply_markup=access_admin_keyboard,
    )
    await cb.answer("Ссылка создана")


@access_router.callback_query(F.data == "access_nko_create")
async def nko_create_prompt(cb: CallbackQuery, user_repo, state: FSMContext):
    user = await _ensure_user(user_repo, cb.from_user.id)
    if not _is_nko(user) or _is_admin(user):
        await cb.answer("Команда доступна только НКО", show_alert=True)
        return

    await cb.message.answer(
        "Введите количество использований для ссылки (1-50) или 0 для безлимита."
    )
    await state.set_state(AccessLinkState.entering_multiuse_limit)
    await cb.answer()


@access_router.message(AccessLinkState.entering_multiuse_limit)
async def nko_create_link(message: Message, state: FSMContext, user_repo, access_repo):
    user = await _ensure_user(user_repo, message.from_user.id)
    if not _is_nko(user):
        await message.answer("У вас нет прав создавать ссылки.")
        await state.clear()
        return

    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число от 0 до 50.")
        return

    if count < 0 or count > 50:
        await message.answer("Допустимо значение от 0 до 50.")
        return

    # Ссылки, созданные НКО, выдают роль участника НКО (без прав управления доступом)
    link = await access_repo.create_access_link(
        created_by=message.from_user.id,
        max_activations=count if count > 0 else None,
        role="nko_member",
    )
    deeplink = await _build_deeplink(message.bot, link.code)
    limit_text = "без ограничений" if link.max_activations is None else f"{link.max_activations} раз(а)"
    await message.answer(
        f"🔁 Ссылка создана и доступна {limit_text}:\n{deeplink}",
        reply_markup=access_nko_keyboard,
    )
    await state.clear()


async def _send_links_list(
    target_message,
    links,
    *,
    show_creator: bool = False,
):
    if not links:
        await target_message.answer("Ссылок пока нет.")
        return

    for link in links:
        deeplink = await _build_deeplink(target_message.bot, link.code)
        text = _format_link_info(link, include_creator=show_creator)
        text = f"{text}\n{deeplink}"
        keyboard = access_link_inline_keyboard(link.id, link.is_active)
        await target_message.answer(text, reply_markup=keyboard)


@access_router.callback_query(F.data == "access_admin_list")
async def admin_list_links(cb: CallbackQuery, user_repo, access_repo):
    user = await _ensure_user(user_repo, cb.from_user.id)
    if not _is_admin(user):
        await cb.answer("Недостаточно прав", show_alert=True)
        return

    links = await access_repo.list_links(created_by=cb.from_user.id, limit=20)
    await _send_links_list(cb.message, links)
    await cb.answer()


@access_router.callback_query(F.data == "access_admin_list_all")
async def admin_list_all_links(cb: CallbackQuery, user_repo, access_repo):
    user = await _ensure_user(user_repo, cb.from_user.id)
    if not _is_admin(user):
        await cb.answer("Недостаточно прав", show_alert=True)
        return
    links = await access_repo.list_links(created_by=None, only_active=True, limit=20)
    await _send_links_list(cb.message, links, show_creator=True)
    await cb.answer()


@access_router.callback_query(F.data == "access_nko_list")
async def nko_list_links(cb: CallbackQuery, user_repo, access_repo):
    user = await _ensure_user(user_repo, cb.from_user.id)
    if not _is_nko(user):
        await cb.answer("Недостаточно прав", show_alert=True)
        return

    links = await access_repo.list_links(created_by=cb.from_user.id, limit=20)
    await _send_links_list(cb.message, links)
    await cb.answer()


@access_router.callback_query(F.data.startswith("access_toggle:"))
async def toggle_link(cb: CallbackQuery, user_repo, access_repo):
    _, link_id, action = cb.data.split(":")
    link = await access_repo.get_by_id(int(link_id))
    if not link:
        await cb.answer("Ссылка не найдена", show_alert=True)
        return

    user = await _ensure_user(user_repo, cb.from_user.id)
    if link.created_by != user.tg_id and not _is_admin(user):
        await cb.answer("Недостаточно прав", show_alert=True)
        return

    desired_state = action == "on"
    link = await access_repo.toggle_link(link, desired_state)
    status = "активирована" if desired_state else "отключена"
    await cb.answer(f"Ссылка {status}")
    await cb.message.edit_reply_markup(
        reply_markup=access_link_inline_keyboard(link.id, link.is_active)
    )

