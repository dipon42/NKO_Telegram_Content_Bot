from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import Optional, List

from database.models import AIAPIModel


class AIAPIRepository:
    """Класс-репозиторий для работы с API-ключами ИИ-моделей"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_user_api_keys(self, tg_id: int) -> List[AIAPIModel]:
        """Получить все API-ключи пользователя"""
        result = await self.db_session.execute(
            select(AIAPIModel)
            .where(AIAPIModel.tg_id == tg_id)
        )
        return list(result.scalars().all())

    async def get_user_api_key(self, tg_id: int, model_name: str) -> Optional[AIAPIModel]:
        """Получить API-ключ пользователя для конкретной модели"""
        result = await self.db_session.execute(
            select(AIAPIModel)
            .where(AIAPIModel.tg_id == tg_id)
            .where(AIAPIModel.model_name == model_name)
        )
        return result.scalar_one_or_none()

    async def create_api_key(self, tg_id: int, model_name: str, api_key: str, connected: bool = True) -> AIAPIModel:
        """Создать новый API-ключ"""
        new_api_key = AIAPIModel(
            tg_id=tg_id,
            model_name=model_name,
            connected=connected
        )
        new_api_key.api_key = api_key  # Используем property-сеттер для шифрования
        
        self.db_session.add(new_api_key)
        await self.db_session.commit()
        await self.db_session.refresh(new_api_key)
        return new_api_key

    async def update_api_key(self, tg_id: int, model_name: str, api_key: str) -> Optional[AIAPIModel]:
        """Обновить API-ключ пользователя"""
        api_key_obj = await self.get_user_api_key(tg_id, model_name)
        if api_key_obj:
            api_key_obj.api_key = api_key  # Используем property-сеттер для шифрования
            api_key_obj.connected = True
            await self.db_session.commit()
            await self.db_session.refresh(api_key_obj)
            return api_key_obj
        return None

    async def delete_api_key(self, tg_id: int, model_name: str) -> bool:
        """Удалить API-ключ пользователя"""
        api_key_obj = await self.get_user_api_key(tg_id, model_name)
        if not api_key_obj:
            return False
            
        await self.db_session.execute(
            delete(AIAPIModel)
            .where(AIAPIModel.tg_id == tg_id)
            .where(AIAPIModel.model_name == model_name)
        )
        await self.db_session.commit()
        return True

    async def get_all_api_keys(self) -> List[AIAPIModel]:
        """Получить все API-ключи"""
        result = await self.db_session.execute(select(AIAPIModel))
        return list(result.scalars().all())

    async def get_connected_api_keys(self) -> List[AIAPIModel]:
        """Получить все подключенные API-ключи"""
        result = await self.db_session.execute(
            select(AIAPIModel)
            .where(AIAPIModel.connected == True)
        )
        return list(result.scalars().all())