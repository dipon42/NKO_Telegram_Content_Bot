import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config import config
from database.models import Base


logger = logging.getLogger(__name__)

DATABASE_URL = config.DATABASE_URL


class DatabaseManager:
    """менеджер для работы с базой данных (единая точка входа для БД)"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = create_async_engine(
            self.database_url,
            echo=True,  # Логирование запросов
            future=True
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """получение сессии БД как контекстного менеджера(для транзакций)"""
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка при работе с БД: {e}")
            raise
        finally:
            await session.close()
    async def init_db(self):
        """создание таблиц"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """закрытие соединений с БД"""
        await self.engine.dispose()


# экземпляр менеджера БД
db_manager = DatabaseManager()

