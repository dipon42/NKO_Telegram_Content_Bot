from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List

from database.models import ContentPlanModel

class ContentPlanRepository:
    """Репозиторий для работы с контент-планами"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def add_or_update_plan(
        self, 
        tg_id: int, 
        plan_content: str
    ) -> ContentPlanModel:
        """Добавить или обновить контент-план для пользователя"""
        # Проверяем, есть ли уже план у пользователя
        result = await self.db_session.execute(
            select(ContentPlanModel).where(ContentPlanModel.tg_id == tg_id)
        )
        existing_plan = result.scalar_one_or_none()
        
        if existing_plan:
            # Обновляем существующий план
            existing_plan.plan_content = plan_content
            await self.db_session.commit()
            await self.db_session.refresh(existing_plan)
            return existing_plan
        else:
            # Создаем новый план
            new_plan = ContentPlanModel(
                tg_id=tg_id,
                plan_content=plan_content
            )
            self.db_session.add(new_plan)
            await self.db_session.commit()
            await self.db_session.refresh(new_plan)
            return new_plan
    
    async def get_plan_by_user_id(self, tg_id: int) -> Optional[ContentPlanModel]:
        """Получить контент-план по ID пользователя"""
        result = await self.db_session.execute(
            select(ContentPlanModel).where(ContentPlanModel.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    
    async def remove_plan(self, tg_id: int) -> bool:
        """Удалить контент-план пользователя"""
        result = await self.db_session.execute(
            select(ContentPlanModel).where(ContentPlanModel.tg_id == tg_id)
        )
        plan = result.scalar_one_or_none()
        
        if plan:
            self.db_session.delete(plan)
            await self.db_session.commit()
            return True
        return False