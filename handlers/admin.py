"""
Admin (Three-Eyed Raven) handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.queries import (
    get_all_kingdoms, create_kingdom, get_all_vassals, create_vassal,
    get_kingdom, update_kingdom, get_user, update_user, add_chronicle,
    get_kingdom_members, get_kingdom_vassals, get_vassal_members
)
from keyboards.kb import (
    admin_main_kb, admin_kingdoms_kb, admin_vassal_kingdom_kb,
    back_kb, confirm_kb
)
from config import ADMIN_IDS, KINGDOM_NAMES

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── States ────────────────────────────────────────────────────────────────────

class AdminStates(StatesGroup):
    waiting_vassal_name = State()
    waiting_vassal_kingdom = State()
    waiting_king_id = State()
    waiting_king_kingdom = State()
    waiting_chronicle = State()
    waiting_delete_kingdom = State()


# ── Access guard ──────────────────────────────────────────────────────────────

def admin_only(func):
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, "from_user") else 0
        if not is_admin(uid):
            if hasattr(event, "answer"):
                await event.answer("🚫 Sizda admin huquqlari yo'q!")
            return
        return await func(event, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Commands ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Ruxsat yo'q!")
        return
    await message.answer(
        "🔮 <b>Uch Ko'zli Qarg'a Paneli</b>\n\nO'yin xudosi sifatida barcha narsani boshqarasiz.",
        reply_markup=admin_main_kb()
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_main")
async def cb_admin_main(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await call.message.edit_text(
        "🔮 <b>Uch Ko'zli Qarg'a Paneli</b>",
        reply_markup=admin_main_kb()
    )


@router.callback_query(F.data == "admin_create_kingdoms")
async def cb_create_kingdoms(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    existing = await get_all_kingdoms()
    existing_names = {k["name"] for k in existing}
    created = []
    for name in KINGDOM_NAMES:
        if name not in existing_names:
            await create_kingdom(name)
            created.append(name)

    if created:
        text = f"✅ Yaratildi: {', '.join(created)}"
    else:
        text = "ℹ️ Barcha 7 qirollik allaqachon mavjud"

    await call.message.edit_text(text, reply_markup=admin_main_kb())
    await add_chronicle("system", "Qirolliklar yaratildi", text, actor_id=call.from_user.id)


@router.callback_query(F.data == "admin_assign_king")
async def cb_assign_king_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    if not kingdoms:
        await call.message.edit_text(
            "❌ Avval qirolliklarni yarating!", reply_markup=admin_main_kb()
        )
        return
    await state.set_state(AdminStates.waiting_king_kingdom)
    await call.message.edit_text(
        "👑 Qaysi qirollikka Qirol tayinlansin?",
        reply_markup=admin_kingdoms_kb(kingdoms)
    )


@router.callback_query(F.data.startswith("admin_kingdom_"), AdminStates.waiting_king_kingdom)
async def cb_assign_king_kingdom(call: CallbackQuery, state: FSMContext):
    kingdom_id = int(call.data.split("_")[-1])
    await state.update_data(kingdom_id=kingdom_id)
    await state.set_state(AdminStates.waiting_king_id)
    await call.message.edit_text(
        "👤 Qirol bo'ladigan foydalanuvchi Telegram ID sini yuboring:",
        reply_markup=back_kb("admin_main")
    )


@router.message(AdminStates.waiting_king_id)
async def msg_assign_king(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        king_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID noto'g'ri. Faqat raqam kiriting.")
        return

    data = await state.get_data()
    kingdom_id = data.get("kingdom_id")
    target_user = await get_user(king_id)
    if not target_user:
        await message.answer("❌ Bu foydalanuvchi topilmadi (avval /start bosishi kerak).")
        return

    kingdom = await get_kingdom(kingdom_id)
    await update_kingdom(kingdom_id, king_id=king_id)
    await update_user(king_id, role="king", kingdom_id=kingdom_id)
    await state.clear()

    text = (
        f"✅ <b>{target_user['full_name']}</b> "
        f"{kingdom['sigil']} <b>{kingdom['name']}</b> qiroli etib tayinlandi!"
    )
    await message.answer(text, reply_markup=admin_main_kb())
    await add_chronicle(
        "coronation", "Yangi Qirol!",
        f"{target_user['full_name']} — {kingdom['name']} Qiroli",
        actor_id=message.from_user.id, target_id=king_id
    )


@router.callback_query(F.data == "admin_add_vassal")
async def cb_add_vassal_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    if not kingdoms:
        await call.message.edit_text("❌ Avval qirolliklarni yarating!", reply_markup=admin_main_kb())
        return
    await state.set_state(AdminStates.waiting_vassal_kingdom)
    await call.message.edit_text(
        "🛡️ Vassal oila qaysi qirollikka tegishli?",
        reply_markup=admin_vassal_kingdom_kb(kingdoms)
    )


@router.callback_query(F.data.startswith("admin_vassal_kingdom_"), AdminStates.waiting_vassal_kingdom)
async def cb_vassal_kingdom_select(call: CallbackQuery, state: FSMContext):
    kingdom_id = int(call.data.split("_")[-1])
    await state.update_data(kingdom_id=kingdom_id)
    await state.set_state(AdminStates.waiting_vassal_name)
    await call.message.edit_text(
        "✏️ Vassal oilaning nomini kiriting:", reply_markup=back_kb("admin_main")
    )


@router.message(AdminStates.waiting_vassal_name)
async def msg_vassal_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    kingdom_id = data.get("kingdom_id")
    vassal = await create_vassal(message.text.strip(), kingdom_id)
    kingdom = await get_kingdom(kingdom_id)
    await state.clear()

    text = f"✅ <b>{vassal['name']}</b> vassal oilasi {kingdom['sigil']} {kingdom['name']} qirolligiga qo'shildi!"
    await message.answer(text, reply_markup=admin_main_kb())
    await add_chronicle("vassal_created", "Yangi vassal oila", text, actor_id=message.from_user.id)


@router.callback_query(F.data == "admin_write_chronicle")
async def cb_write_chronicle(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await state.set_state(AdminStates.waiting_chronicle)
    await call.message.edit_text(
        "📜 Xronikaga yozmoqchi bo'lgan xabaringizni yuboring:",
        reply_markup=back_kb("admin_main")
    )


@router.message(AdminStates.waiting_chronicle)
async def msg_chronicle(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await add_chronicle("gm_event", "⚔️ Global Voqea", message.text, actor_id=message.from_user.id)
    await state.clear()
    await message.answer("✅ Xronikaga yozildi!", reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin_game_status")
async def cb_game_status(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    vassals = await get_all_vassals()

    text = "📊 <b>O'yin Holati</b>\n\n"
    text += f"🏰 Qirolliklar: {len(kingdoms)}/7\n"
    text += f"🛡️ Vassal oilalar: {len(vassals)}\n\n"

    for k in kingdoms:
        members = await get_kingdom_members(k["id"])
        kvassals = await get_kingdom_vassals(k["id"])
        king_mark = "👑 " if k["king_id"] else "❌ "
        text += f"{k['sigil']} <b>{k['name']}</b> {king_mark}\n"
        text += f"  👥 A'zolar: {len(members)}/7 | 💰 {k['gold']} | ⚔️ {k['soldiers']}\n"
        text += f"  🛡️ Vassallar: {len(kvassals)}\n"

    await call.message.edit_text(text, reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin_delete_house")
async def cb_delete_house(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await call.message.edit_text(
        "🗑️ O'chirish uchun vassal ID sini /delete_vassal <id> formatida yuboring.",
        reply_markup=back_kb("admin_main")
    )


@router.message(Command("delete_vassal"))
async def cmd_delete_vassal(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Format: /delete_vassal <id>")
        return
    try:
        vassal_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID noto'g'ri")
        return
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM vassals WHERE id=$1", vassal_id)
    await message.answer(f"✅ Vassal {vassal_id} o'chirildi.", reply_markup=admin_main_kb())
