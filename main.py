import asyncio
import logging
import sys

import redis.asyncio as redis_async
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from bot.handlers.callbacks import callback_router
from bot.handlers.commands import commands_router
from bot.handlers.messages import message_router
from bot.keyboards.set_menu import set_default_menu
from core.settings import settings, Settings
from scheduled.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    config: Settings = settings
    logger.info("Запуск бота...")

    # redis = redis_async.Redis(
    #     host=settings.redis_settings.REDIS_HOST,
    #     port=settings.redis_settings.REDIS_PORT,
    #     db=settings.redis_settings.REDIS_DB
    # )
    # storage = RedisStorage(redis=redis)
    storage = MemoryStorage()

    bot = Bot(
        token=config.bot.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    scheduler.start()

    dp.include_routers(commands_router, callback_router, message_router)

    await set_default_menu(bot)


    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот начал поллинг...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical("Критическая ошибка при работе бота: %s", e, exc_info=True)
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
    except Exception as e:
        logger.critical("Необработанное исключение: %s", e, exc_info=True)