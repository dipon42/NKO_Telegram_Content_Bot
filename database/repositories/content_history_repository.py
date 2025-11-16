from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from database.models import ContentHistoryModel


class ContentHistoryRepository:
    """Класс-репозиторйи для работы с историей"""
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_content_history(
            self,
            tg_id: int,
            content_type: str,
            model: str,
            prompt: str = None,
            result: str = None,
            style: str = None,
            additional_params: dict = None
    ) -> ContentHistoryModel:
        """Добавить запись в историю генераций"""
        history = ContentHistoryModel(
            tg_id=tg_id,
            content_type=content_type,
            prompt=prompt,
            result=result,
            model=model,
            style=style,
            additional_params=additional_params
        )
        self.db_session.add(history)
        await self.db_session.commit()
        await self.db_session.refresh(history)
        return history

    async def get_user_content_history(
            self,
            tg_id: int,
            limit: int = 10
    ) -> List[ContentHistoryModel]:
        """Получить историю генераций пользователя"""
        result = await self.db_session.execute(
            select(ContentHistoryModel)
            .where(ContentHistoryModel.tg_id == tg_id)
            .order_by(ContentHistoryModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(self, history_id: int) -> Optional[ContentHistoryModel]:
        """Получить запись истории по ID"""
        result = await self.db_session.execute(
            select(ContentHistoryModel)
            .where(ContentHistoryModel.id == history_id)
        )
        return result.scalar_one_or_none()