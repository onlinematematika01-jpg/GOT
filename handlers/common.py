"""
Common handlers — /start, /help, main menu routing
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from database.queries import get_user, assign_user_to_slot, add_chronicle
from keyboards.kb import admin_main_kb, king_main_kb, lord_main_kb, member_main_kb
from config import ADMIN_IDS

router = Router()


def get_role_kb(role: str):
    if role == "admin":
        return admin_main_kb()
    elif role == "king":
        return king_main_kb()
    elif role == "lord":
        return lord_main_kb()
    else:
        return member_main_kb()


GOT_WELCOME = """
⚔️ <b>Game of Thrones: Telegram Battle</b> ⚔️

<i>Qish kelmoqda. Taxtlar o'yini boshlanmoqda.</i>

Siz quyidagi dunyoga kirmoqdasiz:
🏰 <b>7 ta Qirollik</b> — kuch va obro' uchun kurash
👑 <b>Qirollar va Vassallar</b> — ierarxiya va siyosat
⚔️ <b>Urush va Diplomatiya</b> — g'alaba va xiyonat
📜 <b>Xronika</b> — barcha voqealar tarixi

<i>Taxt uchun kurash shafqatsizdir...</i>
"""


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: dict):
    user = db_user
    role = user.get("role", "member")

    # Queue: yangi user YOKI vassali o'chirilgan user
    if role == "member" and not user.get("vassal_id"):
        result = await assign_user_to_slot(message.from_user.id)
        if "error" not in result:
            phase = result.get("phase", 1)
            if phase == 1:
                place = f"<b>{result.get('kingdom', '?')}</b> qirolligiga"
            else:
                place = f"<b>{result.get('vassal', '?')}</b> vassal oilasiga"
            await message.answer(
                f"⚔️ Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
                f"Siz {place} joylashtirildinqiz.\n\n" + GOT_WELCOME,
                reply_markup=member_main_kb()
            )
            await add_chronicle(
                "join", "Yangi jangchi",
                f"{message.from_user.full_name} o'yinga qo'shildi",
                actor_id=message.from_user.id
            )
            return
        else:
            await message.answer(
                GOT_WELCOME + "\n\n⏳ Hozircha bo'sh joy yo'q. Iltimos kuting.",
            )
            return

    await message.answer(
        f"⚔️ <b>{message.from_user.full_name}</b>, xush kelibsiz!\n\n"
        f"🎭 Rolingiz: <b>{role.upper()}</b>",
        reply_markup=get_role_kb(role)
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, db_user: dict):
    role = db_user.get("role", "member")
    await message.answer(
        "🏰 <b>Asosiy menyu</b>",
        reply_markup=get_role_kb(role)
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, db_user: dict):
    role = db_user.get("role", "member")
    await call.message.edit_text(
        "🏰 <b>Asosiy menyu</b>",
        reply_markup=get_role_kb(role)
    )


@router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, db_user: dict):
    role = db_user.get("role", "member")
    await call.message.edit_text(
        "❌ Bekor qilindi.",
        reply_markup=get_role_kb(role)
    )


@router.callback_query(F.data == "my_status")
async def cb_my_status(call: CallbackQuery, db_user: dict):
    from database.queries import get_kingdom, get_vassal
    u = db_user
    role_emoji = {"admin": "🔮", "king": "👑", "lord": "🛡️", "member": "⚔️"}.get(u["role"], "⚔️")

    text = f"{role_emoji} <b>Mening holatim</b>\n\n"
    text += f"👤 Ism: {u.get('full_name', 'Noma\'lum')}\n"
    text += f"🎭 Rol: <b>{u['role'].upper()}</b>\n"
    text += f"💰 Oltin: {u.get('gold', 0)}\n"

    if u.get("kingdom_id"):
        k = await get_kingdom(u["kingdom_id"])
        if k:
            text += f"🏰 Qirollik: {k['sigil']} {k['name']}\n"

    if u.get("vassal_id"):
        v = await get_vassal(u["vassal_id"])
        if v:
            text += f"🛡️ Vassal oila: {v['name']}\n"

    from keyboards.kb import back_kb
    await call.message.edit_text(text, reply_markup=back_kb())
