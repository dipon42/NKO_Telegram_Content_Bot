import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import db_manager
from database.repositories import NotificationRepository
from handlers import msg_router, cb_router, settings_router, fsm_router, errors_router, history_router, access_router
from handlers.generation_handlers import (text_gen_router, image_gen_router, cp_router,
                                          editor_router, structured_gen_router, examples_gen_router, onmsg_router, reply_commands_router)
from middleware.di_middleware import InjectionMiddleware
from handlers.scheduled_notifications import ScheduledNotifications
from utils.generation_queue import get_generation_queue, stop_all_generation_queues


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__) # Для удобства указываем имя модуля

# Основная функция запуска
async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(
        parse_mode=ParseMode.HTML))

    await db_manager.init_db()

    dp = Dispatcher(storage=MemoryStorage()) # Можно будет потом заменить на Redis для более быстрого доступа и надежности

    dp.update.middleware(InjectionMiddleware(bot=bot)) # подключаем middleware (пост обработчик)
    # Создаем и подключаем репозитории
    notification_repo = NotificationRepository(db_manager.session_factory, bot)
    
    # Создаем и запускаем планировщик уведомлений
    scheduler = ScheduledNotifications(notification_repo)
    
    # Подключаем роутеры
    dp.include_routers(msg_router, settings_router, access_router, fsm_router, cb_router, text_gen_router, image_gen_router,
                       cp_router, editor_router, structured_gen_router, examples_gen_router,
                       errors_router, history_router, onmsg_router, reply_commands_router)

    logger.info("Инициализация базы данных...")

    logger.info("✅ Таблицы созданы успешно")

    # ЖЦ бота
    try:
        logger.info("🚀 Бот запущен.")
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем планировщик уведомлений
        await scheduler.start()
        
        # Запускаем очередь генерации
        generation_queue = get_generation_queue()
        await generation_queue.start()
        
        # Запускаем поллинг
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
        
    except Exception as e:
        logger.critical("Непредвиденная ошибка в polling: %s", e, exc_info=True)
        
    finally:
        logger.info("🔴 Бот останавливается...")
        
        # Останавливаем планировщик
        await scheduler.stop()
        
        # Останавливаем очередь генерации
        await stop_all_generation_queues()
        
        await bot.session.close()
        await db_manager.close()
        logger.info("✅ Успешное завершение работы.")

if __name__ == '__main__':
    asyncio.run(main())