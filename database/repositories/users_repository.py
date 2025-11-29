from typing import Optional

from sqlalchemy.future import select
from sqlalchemy import update, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import config
from database.models import UserModel


class UserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_user(self, tg_id: int) -> Optional[UserModel]:
        """Получение пользователя по tg_id"""
        result = await self.db_session.execute(
            select(UserModel).where(UserModel.tg_id == tg_id)
            .options(
                selectinload(UserModel.nko_data),
                selectinload(UserModel.api_keys),
            )
        )
        return result.scalar_one_or_none()

    async def create_user(self, tg_id: int) -> UserModel:
        """Добавление пользователя в бд"""
        existing_user = await self.db_session.execute(
            select(UserModel).where(UserModel.tg_id == tg_id)
        )
        user = existing_user.scalar_one_or_none()
        if user:
            return user  # Возвращаем существующего

        # Создаём нового пользователя
        role = "admin" if tg_id in config.ADMIN_IDS else "guest"
        new_user = UserModel(
            tg_id=tg_id,
            role=role,
            access=role == "admin"
        )
        self.db_session.add(new_user)
        await self.db_session.commit()
        await self.db_session.refresh(new_user)
        return new_user

    async def set_access_and_role(
        self,
        tg_id: int,
        access: bool,
        role: str | None = None,
        invited_link_id: int | None = None,
    ) -> UserModel:
        values: dict = {"access": access}
        if role is not None:
            values["role"] = role
        if invited_link_id is not None:
            values["invited_by_link_id"] = invited_link_id

        result = await self.db_session.execute(
            update(UserModel)
            .where(UserModel.tg_id == tg_id)
            .values(**values)
            .returning(UserModel)
        )
        user = result.scalar_one()
        await self.db_session.commit()
        return user

    async def _update_access(self, tg_id: int, new_access: bool) -> bool:
        """Обновляет статус доступа и возвращает новое значение"""
        result = await self.db_session.execute(
            update(UserModel)
            .where(UserModel.tg_id == tg_id)
            .values(access=new_access)
            .returning(UserModel.access)
        )
        row = result.fetchone()
        await self.db_session.commit()

        if row is None:
            raise ValueError(f"Пользователь с tg_id {tg_id} не найден")

        return row[0]

    async def activate_access(self, tg_id: int) -> bool:
        """Активация доступа"""
        return await self._update_access(tg_id, True)

    async def deactivate_access(self, tg_id: int) -> bool:
        """Деактивация доступа"""
        return await self._update_access(tg_id, False)

    async def change_access(self, tg_id: int) -> bool:
        """Переключение доступа (вкл/выкл)"""
        result = await self.db_session.execute(
            update(UserModel)
            .where(UserModel.tg_id == tg_id)
            .values(access=not_(UserModel.access))
            .returning(UserModel.access)
        )
        row = result.fetchone()
        await self.db_session.commit()

        if row is None:
            raise ValueError(f"Пользователь с tg_id {tg_id} не найден")

        return row[0]
