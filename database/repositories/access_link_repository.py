from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccessLinksModel


class AccessLinksRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def list_links(
        self,
        created_by: Optional[int] = None,
        only_active: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[AccessLinksModel]:
        """Получение ссылок доступа с фильтрами и пагинацией"""
        query = select(AccessLinksModel).order_by(AccessLinksModel.created_at.desc())
        if created_by is not None:
            query = query.where(AccessLinksModel.created_by == created_by)
        if only_active:
            query = query.where(AccessLinksModel.is_active.is_(True))
        query = query.limit(limit).offset(offset)

        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def create_access_link(
        self,
        created_by: int,
        max_activations: Optional[int],
        role: str,
        expires_at=None,
    ) -> AccessLinksModel:
        """Создание ссылки"""
        normalized_activations = max_activations if (max_activations or 0) > 0 else None
        link = AccessLinksModel(
            created_by=created_by,
            max_activations=normalized_activations,
            role=role,
            expires_at=expires_at,
        )
        self.db_session.add(link)
        await self.db_session.commit()
        await self.db_session.refresh(link)
        return link

    async def get_by_code(self, code: str) -> Optional[AccessLinksModel]:
        result = await self.db_session.execute(
            select(AccessLinksModel).where(AccessLinksModel.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, link_id: int) -> Optional[AccessLinksModel]:
        result = await self.db_session.execute(
            select(AccessLinksModel).where(AccessLinksModel.id == link_id)
        )
        return result.scalar_one_or_none()

    async def save(self, link: AccessLinksModel) -> AccessLinksModel:
        await self.db_session.commit()
        await self.db_session.refresh(link)
        return link

    async def register_activation(self, link: AccessLinksModel) -> AccessLinksModel:
        link.activations_used += 1
        if link.max_activations and link.activations_used >= link.max_activations:
            link.is_active = False
        return await self.save(link)

    async def toggle_link(self, link: AccessLinksModel, active: bool) -> AccessLinksModel:
        link.is_active = active
        return await self.save(link)
