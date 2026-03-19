"""
Game of Thrones: Telegram Battle
Main entry point
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from handlers import admin, king, lord, member, common, assassination, war, help, rating
from handlers.war import process_weekly_tributes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from middlewares.auth import AuthMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    await init_db()

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(king.router)
    dp.include_router(lord.router)
    dp.include_router(member.router)
    dp.include_router(assassination.router)
    dp.include_router(war.router)
    dp.include_router(help.router)
    dp.include_router(rating.router)

    # Haftalik tribute scheduler
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    scheduler.add_job(
        process_weekly_tributes,
        trigger='cron',
        day_of_week='sat',
        hour=20, minute=0,
        args=[bot]
    )
    scheduler.start()

    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
