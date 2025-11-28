from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from database.repositories import NotificationRepository
from keyboards.inline_keyboards import get_daily_post_keyboard

logger = logging.getLogger(__name__)

class ScheduledNotifications:
    """Класс для управления запланированными уведомлениями"""
    
    def __init__(self, notification_repo: NotificationRepository):
        self.notification_repo = notification_repo
        self.scheduler = AsyncIOScheduler()
    
    async def start(self):
        """Запуск планировщика"""
        # Добавляем задачу, которая будет выполняться каждый день в 7:00 по МСК
        self.scheduler.add_job(
            self.send_daily_notifications,
            CronTrigger(hour=7, timezone="Europe/Moscow"),
            id="daily_notifications",
            name="Отправка ежедневных уведомлений",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Планировщик уведомлений запущен")
    
    async def stop(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик уведомлений остановлен")
    
    async def send_daily_notifications(self):
        """Отправка ежедневных уведомлений"""
        try:
            # Получаем все неотправленные уведомления на текущую дату
            pending_notifications = await self.notification_repo.get_pending_notifications(
                current_datetime=datetime.now()
            )
            
            logger.info(f"Найдено {len(pending_notifications)} уведомлений для отправки")
            
            for notification in pending_notifications:
                try:
                    # Получаем бота из хранилища (предполагается, что он будет добавлен в репозиторий)
                    bot = self.notification_repo.bot
                    
                    if not bot:
                        logger.error("Бот не найден в репозитории уведомлений")
                        continue
                    
                    # Отправляем уведомление пользователю (без системного текста)
                    await bot.send_message(
                        chat_id=notification.tg_id,
                        text=f"**{notification.content_date} — {notification.content_topic}**",
                        parse_mode="Markdown",
                        reply_markup=get_daily_post_keyboard()
                    )
                    
                    # Отмечаем уведомление как отправленное
                    await self.notification_repo.mark_as_sent(notification.id)
                    logger.info(f"Уведомление отправлено пользователю {notification.tg_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления для пользователя {notification.tg_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневных уведомлений: {e}")