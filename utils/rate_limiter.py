import asyncio
import logging
from typing import Dict, Optional

class RateLimiter:
    """
    Простой rate limiter для ограничения количества одновременных запросов к API.
    Используется для предотвращения ошибок при превышении лимита на бесплатном тарифе GigaChat.
    """

    def __init__(self, max_concurrent: int = 1):
        """
        Инициализация RateLimiter.

        :param max_concurrent: Максимальное количество одновременных запросов
        """
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._logger = logging.getLogger(__name__)

    async def acquire(self):
        """
        Блокирует выполнение, пока не станет доступно место для выполнения запроса.
        """
        await self._semaphore.acquire()

    def release(self):
        """
        Освобождает место, позволяя следующему запросу выполниться.
        """
        self._semaphore.release()

    async def __aenter__(self):
        """
        Вход в контекстный менеджер. Блокирует выполнение до получения разрешения.
        """
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Выход из контекстного менеджера. Освобождает место после выполнения запроса.
        """
        self.release()


# Глобальный экземпляр RateLimiter с ограничением в 1 одновременный запрос
_global_limiter = RateLimiter(max_concurrent=1)


def get_global_limiter() -> RateLimiter:
    """
    Возвращает глобальный экземпляр RateLimiter.

    :return: Экземпляр RateLimiter
    """
    return _global_limiter