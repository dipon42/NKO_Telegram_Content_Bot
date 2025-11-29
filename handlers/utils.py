from keyboards import reply_kb

ACCESS_ROLES = {"admin", "nko"}


def should_show_access_button(user) -> bool:
    return bool(user and user.role in ACCESS_ROLES)


async def build_user_main_keyboard(user_repo, tg_id: int):
    user = await user_repo.get_user(tg_id)
    return reply_kb.build_main_keyboard(should_show_access_button(user))

