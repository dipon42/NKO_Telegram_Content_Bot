import logging

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message, CallbackQuery

from ai_service.gigachat_ai_service import get_gigachat_service
from database import db_manager
from database.repositories import UserRepository, NKORepository, AccessLinksRepository, ContentHistoryRepository, \
    AIAPIRepository


class InjectionMiddleware(BaseMiddleware):
    """Внутренний middleware для внедрения зависимостей (Инъекция зависимостей, делал по аналогии с FastAPI Dependency Injection)"""
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
            data['user_repo'] = UserRepository(session)
            data['nko_repo'] = NKORepository(session)
            data['access_repo'] = AccessLinksRepository(session)
            data['content_history_repo'] = ContentHistoryRepository(session)
            data['ai_api_repo'] = AIAPIRepository(session)
            # инициализация сервисов
            data['gigachat_service'] = get_gigachat_service()

            result = await handler(event, data)
            return result