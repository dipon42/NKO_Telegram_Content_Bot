from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, date
from typing import List
import logging
import re

from database.models import UserNotificationModel

logger = logging.getLogger(__name__)

class NotificationRepository:
    """Репозиторий для работы с уведомлениями"""
    
    def __init__(self, db_session: AsyncSession, bot=None):
        self.db_session = db_session
        self.bot = bot  # Сохраняем ссылку на бота для отправки сообщений
    
    async def create_notifications_from_plan(
        self, 
        tg_id: int, 
        plan_content: str,
        current_date: date
    ) -> List[UserNotificationModel]:
        """Создать уведомления на основе контент-плана"""
        notifications = []
        
        # Удаляем существующие уведомления пользователя
        await self.remove_user_notifications(tg_id)
        
        # Парсим план и создаем уведомления для каждой даты
        lines = plan_content.strip().split('\n')
        logger.info(f"Парсинг контент-плана для пользователя {tg_id}, строк: {len(lines)}")
        for line in lines:
            line = line.strip()
            # Проверяем наличие длинного тире (—), обычного дефиса (-) или вертикальной черты (|)
            if not line or ('—' not in line and ' - ' not in line and '|' not in line):
                logger.debug(f"Пропущена строка (нет разделителя): '{line}'")
                continue
                
            try:
                # Поддерживаем три формата: длинное тире, дефис и вертикальная черта
                if '—' in line:
                    date_str, topic = line.split('—', 1)
                elif '|' in line:
                    date_str, topic = line.split('|', 1)
                else:
                    date_str, topic = line.split(' - ', 1)
                    
                date_str = date_str.strip()
                topic = topic.strip()
                
                # Удаляем markdown форматирование из темы, если есть
                topic = re.sub(r'(\*\*|__)(.*?)\1', r'\2', topic)  # Bold
                topic = re.sub(r'(\*|_)(.*?)\1', r'\2', topic)    # Italic
                topic = topic.strip()
                
                # Преобразуем ДД.ММ в дату
                # Сначала пробуем текущий год
                try:
                    plan_date = datetime.strptime(f"{date_str}.{current_date.year}", "%d.%m.%Y").date()
                    # Если дата уже прошла в текущем году, пробуем следующий год
                    if plan_date < current_date:
                        plan_date = datetime.strptime(f"{date_str}.{current_date.year + 1}", "%d.%m.%Y").date()
                except ValueError:
                    logger.warning(f"Не удалось распарсить дату '{date_str}' из строки '{line}'")
                    continue
                
                # Создаем уведомление только для будущих дат
                if plan_date >= current_date:
                    notification = UserNotificationModel(
                        tg_id=tg_id,
                        notification_date=datetime.combine(plan_date, datetime.min.time()),
                        content_date=date_str,
                        content_topic=topic
                    )
                    self.db_session.add(notification)
                    notifications.append(notification)
                    logger.info(f"Создано уведомление для {date_str}: {topic[:50]}...")
                else:
                    logger.debug(f"Пропущена дата {date_str} (уже прошла): {topic[:50]}...")
                    
            except Exception as e:
                logger.error(f"Ошибка при создании уведомления из строки '{line}': {e}", exc_info=True)
                continue
        
        if notifications:
            await self.db_session.commit()
            
        return notifications
    
    async def remove_user_notifications(self, tg_id: int) -> bool:
        """Удалить все уведомления пользователя"""
        result = await self.db_session.execute(
            select(UserNotificationModel).where(UserNotificationModel.tg_id == tg_id)
        )
        notifications = result.scalars().all()
        
        for notification in notifications:
            self.db_session.delete(notification)
            
        await self.db_session.commit()
        return True
    
    async def get_pending_notifications(self, current_datetime: datetime) -> List[UserNotificationModel]:
        """Получить все неотправленные уведомления на текущую дату"""
        result = await self.db_session.execute(
            select(UserNotificationModel)
            .where(
                UserNotificationModel.notification_date <= current_datetime,
                UserNotificationModel.sent == False
            )
            .order_by(UserNotificationModel.tg_id)
        )
        return list(result.scalars().all())
    
    async def mark_as_sent(self, notification_id: int) -> bool:
        """Отметить уведомление как отправленное"""
        result = await self.db_session.execute(
            select(UserNotificationModel).where(UserNotificationModel.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.sent = True
            notification.sent_at = datetime.now()
            await self.db_session.commit()
            return True
        return False
    
    async def get_user_notifications(self, tg_id: int) -> List[UserNotificationModel]:
        """Получить все уведомления пользователя (отсортированные по дате)"""
        result = await self.db_session.execute(
            select(UserNotificationModel)
            .where(UserNotificationModel.tg_id == tg_id)
            .order_by(UserNotificationModel.notification_date)
        )
        return list(result.scalars().all())