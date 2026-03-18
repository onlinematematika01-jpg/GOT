"""
Utility helpers — formatting, notifications, role checks
"""
from aiogram import Bot
from database.queries import get_kingdom_members, get_vassal_members
import logging

logger = logging.getLogger(__name__)


async def broadcast_to_kingdom(bot: Bot, kingdom_id: int, text: str, exclude_id: int = None):
    """Send message to all kingdom members."""
    members = await get_kingdom_members(kingdom_id)
    sent = 0
    for m in members:
        if m["telegram_id"] == exclude_id:
            continue
        try:
            await bot.send_message(m["telegram_id"], text)
            sent += 1
        except Exception as e:
            logger.warning(f"Could not send to {m['telegram_id']}: {e}")
    return sent


async def broadcast_to_vassal(bot: Bot, vassal_id: int, text: str, exclude_id: int = None):
    """Send message to all vassal members."""
    members = await get_vassal_members(vassal_id)
    sent = 0
    for m in members:
        if m["telegram_id"] == exclude_id:
            continue
        try:
            await bot.send_message(m["telegram_id"], text)
            sent += 1
        except Exception as e:
            logger.warning(f"Could not send to {m['telegram_id']}: {e}")
    return sent


def format_resources(gold: int, soldiers: int, dragons: int = 0) -> str:
    """Format resource line."""
    line = f"💰 {gold} oltin | ⚔️ {soldiers} qo'shin"
    if dragons:
        line += f" | 🐉 {dragons} ajdar"
    return line


def role_display(role: str) -> str:
    labels = {
        "admin": "🔮 Uch Ko'zli Qarg'a",
        "king":  "👑 Qirol",
        "lord":  "🛡️ Lord",
        "member": "⚔️ Jangchi",
    }
    return labels.get(role, role)
