from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import Optional, List

from database.models import NKODataModel


class NKORepository:
    """Класс-репозиторий для работы с НКО"""
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_nko_data(self, tg_id: int) -> Optional[NKODataModel]:
        """Получить данные НКО по tg_id"""

        result = await self.db_session.execute(
            select(NKODataModel).where(NKODataModel.tg_id == tg_id)
        )
        return result.scalar_one_or_none()

    async def save_nko_data(self, tg_id: int, nko_data: dict) -> NKODataModel:
        """Сохранить или обновить данные НКО"""
        existing_data = await self.get_nko_data(tg_id)
        if existing_data:
            return await self._update_nko_data(existing_data, nko_data)
        else:
            return await self._create_nko_data(tg_id, nko_data)

    async def _create_nko_data(self, tg_id: int, nko_data: dict) -> NKODataModel:
        """Создать новую запись НКО."""
        new_nko = NKODataModel(tg_id=tg_id, **nko_data)
        self.db_session.add(new_nko)
        await self.db_session.commit()
        await self.db_session.refresh(new_nko)
        return new_nko

    async def _update_nko_data(self, existing_data: NKODataModel, nko_data: dict) -> NKODataModel:
        """Обновить существующую запись НКО."""
        for key, value in nko_data.items():
            setattr(existing_data, key, value)
        await self.db_session.commit()
        await self.db_session.refresh(existing_data)
        return existing_data

    async def delete_nko_data(self, tg_id: int) -> bool:
        """Удалить данные НКО"""
        # существует ли запись
        existing_data = await self.get_nko_data(tg_id)
        if not existing_data:
            return False

        await self.db_session.execute(
            delete(NKODataModel).where(NKODataModel.tg_id == tg_id)
        )
        await self.db_session.commit()

        return True

    async def get_all_nko_data(self) -> List[NKODataModel]:
        """Получить все записи"""
        result = await self.db_session.execute(select(NKODataModel))
        return list(result.scalars().all())
