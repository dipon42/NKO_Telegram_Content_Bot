import logging

from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.filters import ExceptionTypeFilter


errors_router = Router(name="Error router")
logger = logging.getLogger(__name__)

@errors_router.errors(ExceptionTypeFilter(Exception))
async def handle_unexpected_error(event: ErrorEvent):
    """Глобальный обработчик непредвиденных ошибок."""
    logger.exception(
        "Необработанное исключение %s:\n%s",
        event.update,
        event.exception
    )