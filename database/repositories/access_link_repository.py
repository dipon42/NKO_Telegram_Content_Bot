from typing import Optional, List, Any, Coroutine, Sequence

from sqlalchemy import select, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccessLinksModel


class AccessLinksRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_access_links(self,
                               tg_id: Optional[int],
                               limit: int = 10,
                               offset: int = 5) -> Sequence[AccessLinksModel]:
        """Получение ссылок доступа с фильтрами и пагинацией"""
        query = select(AccessLinksModel)
        if tg_id is not None:
            query = query.where(AccessLinksModel. created_by == tg_id)
        query = query.limit(limit).offset(offset)

        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def create_access_link(self,tg_id: int,count_activate: int = 99999) -> AccessLinksModel:
        """Создание ссылки"""
        new_link = AccessLinksModel(tg_id=tg_id, count=count_activate)
        self.db_session.add(new_link)
        await self.db_session.commit()
        await self.db_session.refresh(new_link) # обновляем объект после создания
        return new_link
