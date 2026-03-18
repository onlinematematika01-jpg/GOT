"""
Auth middleware — auto-registers users on first interaction
"""
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.queries import get_user, create_user, assign_user_to_slot
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            db_user = await get_user(user.id)
            if db_user is None:
                # Auto-register
                db_user = await create_user(
                    user.id,
                    user.username or "",
                    user.full_name or ""
                )
                # Assign role if admin
                if user.id in ADMIN_IDS:
                    from database.db import get_pool
                    pool = await get_pool()
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE users SET role='admin' WHERE telegram_id=$1",
                            user.id
                        )
                else:
                    logger.info(f"New user registered: {user.id} — {user.full_name}")

            data["db_user"] = dict(db_user)

        return await handler(event, data)
