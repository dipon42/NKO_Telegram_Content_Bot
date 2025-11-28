import logging

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message, CallbackQuery

from ai_service.gigachat_ai_service import get_gigachat_service
from database import db_manager
from database.repositories import UserRepository, NKORepository, AccessLinksRepository, ContentHistoryRepository, \
    AIAPIRepository, ContentPlanRepository, NotificationRepository


class InjectionMiddleware(BaseMiddleware):
    """Внутренний middleware для внедрения зависимостей (Инъекция зависимостей, делал по аналогии с FastAPI Dependency Injection)"""
    def __init__(self, bot=None):
        self.bot = bot
    
    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        logger = logging.getLogger(__name__)
        logger.info(f"Middleware обработка {type(event).__name__}") # логирование
        async with db_manager.get_session() as session:
            # инициализация репозиториев
            user_repo = UserRepository(session)
            data['user_repo'] = user_repo
            data['nko_repo'] = NKORepository(session)
            data['access_repo'] = AccessLinksRepository(session)
            data['content_history_repo'] = ContentHistoryRepository(session)
            data['ai_api_repo'] = AIAPIRepository(session)
            data['content_plan_repo'] = ContentPlanRepository(session)
            data['notification_repo'] = NotificationRepository(session, bot=self.bot)
            # инициализация сервисов
            data['gigachat_service'] = get_gigachat_service()

            # Автоматически создаем пользователя, если его нет в БД (кроме команды /start, где это делается явно)
            if hasattr(event, 'from_user') and event.from_user:
                tg_id = event.from_user.id
                # Проверяем, не является ли это командой /start
                is_start_command = False
                if isinstance(event, Message) and event.text:
                    is_start_command = event.text.startswith('/start')
                
                if not is_start_command:
                    # Проверяем существование пользователя и создаем, если его нет
                    existing_user = await user_repo.get_user(tg_id)
                    if existing_user is None:
                        logger.info(f"Пользователь {tg_id} не найден в БД, создаю автоматически")
                        await user_repo.create_user(tg_id)

            result = await handler(event, data)
            return result