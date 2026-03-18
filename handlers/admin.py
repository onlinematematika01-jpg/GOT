"""
Admin (Three-Eyed Raven) handlers — to'liq panel
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.queries import (
    get_all_kingdoms, create_kingdom, get_all_vassals, create_vassal,
    get_kingdom, get_vassal, update_kingdom, update_vassal,
    get_user, update_user, add_chronicle,
    get_kingdom_members, get_kingdom_vassals, get_vassal_members
)
from keyboards.kb import admin_main_kb, admin_kingdoms_kb, admin_vassal_kingdom_kb, back_kb
from config import ADMIN_IDS, KINGDOM_NAMES

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── States ────────────────────────────────────────────────────────────────────

class AdminStates(StatesGroup):
    # Vassal
    waiting_vassal_name      = State()
    waiting_vassal_kingdom   = State()
    # King
    waiting_king_id          = State()
    waiting_king_kingdom     = State()
    # Chronicle
    waiting_chronicle        = State()
    # Kingdom management
    waiting_new_kingdom_name  = State()
    waiting_new_kingdom_sigil = State()
    waiting_edit_res_kingdom  = State()
    waiting_edit_res_type     = State()
    waiting_edit_res_amount   = State()


# ── /admin command ────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Ruxsat yo'q!")
        return
    await message.answer(
        "🔮 <b>Uch Ko'zli Qarg'a Paneli</b>\n\nO'yin xudosi sifatida barcha narsani boshqarasiz.",
        reply_markup=admin_main_kb()
    )


# ── Main panel ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_main")
async def cb_admin_main(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await call.message.edit_text(
        "🔮 <b>Uch Ko'zli Qarg'a Paneli</b>",
        reply_markup=admin_main_kb()
    )


# ══════════════════════════════════════════════════════════════════════════════
#  QIROLLIK BOSHQARUVI
# ══════════════════════════════════════════════════════════════════════════════

def kingdoms_manage_kb(kingdoms):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Yangi qirollik qo'shish", callback_data="admin_add_kingdom"))
    if kingdoms:
        builder.row(InlineKeyboardButton(text="🗑️ Qirollikni o'chirish", callback_data="admin_del_kingdom_list"))
        builder.row(InlineKeyboardButton(text="✏️ Resurslarni tahrirlash", callback_data="admin_edit_res_list"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    return builder.as_markup()


@router.callback_query(F.data == "admin_manage_kingdoms")
async def cb_manage_kingdoms(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    text = "🏰 <b>Qirolliklar boshqaruvi</b>\n\n"
    if kingdoms:
        for k in kingdoms:
            king_mark = "👑" if k["king_id"] else "❌"
            text += f"{k['sigil']} <b>{k['name']}</b> {king_mark} | 💰{k['gold']} ⚔️{k['soldiers']}\n"
    else:
        text += "Hech qanday qirollik yo'q."
    await call.message.edit_text(text, reply_markup=kingdoms_manage_kb(kingdoms))


# ── Yangi qirollik qo'shish ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_kingdom")
async def cb_add_kingdom_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await state.set_state(AdminStates.waiting_new_kingdom_name)
    await call.message.edit_text(
        "✏️ Yangi qirollik nomini kiriting\n(masalan: <code>Targaryen</code>):",
        reply_markup=back_kb("admin_manage_kingdoms")
    )


@router.message(AdminStates.waiting_new_kingdom_name)
async def msg_new_kingdom_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    await state.update_data(new_kingdom_name=name)
    await state.set_state(AdminStates.waiting_new_kingdom_sigil)
    await message.answer(
        f"🎨 <b>{name}</b> uchun belgi (emoji) kiriting\n(masalan: 🐉):",
        reply_markup=back_kb("admin_manage_kingdoms")
    )


@router.message(AdminStates.waiting_new_kingdom_sigil)
async def msg_new_kingdom_sigil(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    sigil = message.text.strip()
    data = await state.get_data()
    name = data["new_kingdom_name"]

    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM kingdoms WHERE name=$1", name)
        if existing:
            await message.answer(
                f"❌ <b>{name}</b> qirolligi allaqachon mavjud!",
                reply_markup=admin_main_kb()
            )
            await state.clear()
            return
        kingdom = await conn.fetchrow(
            "INSERT INTO kingdoms (name, sigil) VALUES ($1, $2) RETURNING *",
            name, sigil
        )

    await state.clear()
    await message.answer(
        f"✅ {sigil} <b>{name}</b> qirolligi yaratildi!\n\n"
        f"💰 Boshlang'ich oltin: 1000\n⚔️ Boshlang'ich qo'shin: 500",
        reply_markup=admin_main_kb()
    )
    await add_chronicle("system", "Yangi Qirollik!", f"{sigil} {name} qirolligi tashkil topdi", actor_id=message.from_user.id)


# ── Qirollikni o'chirish ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_del_kingdom_list")
async def cb_del_kingdom_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        members = await get_kingdom_members(k["id"])
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']} ({len(members)} kishi)",
            callback_data=f"admin_del_k_confirm_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_manage_kingdoms"))
    await call.message.edit_text(
        "🗑️ <b>Qaysi qirollikni o'chirmoqchisiz?</b>\n\n"
        "⚠️ Oiladagi barcha a'zolar, vassallar va Qirol o'chiriladi!",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_del_k_confirm_"))
async def cb_del_kingdom_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdom_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom(kingdom_id)
    members = await get_kingdom_members(kingdom_id)
    vassals = await get_kingdom_vassals(kingdom_id)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chir", callback_data=f"admin_del_k_do_{kingdom_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="admin_del_kingdom_list")
    )
    await call.message.edit_text(
        f"⚠️ <b>{kingdom['sigil']} {kingdom['name']}</b> ni o'chirishni tasdiqlaysizmi?\n\n"
        f"👥 A'zolar: {len(members)}\n"
        f"🛡️ Vassallar: {len(vassals)}\n\n"
        f"Barchasi o'chiriladi!",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_del_k_do_"))
async def cb_del_kingdom_do(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdom_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom(kingdom_id)
    name = f"{kingdom['sigil']} {kingdom['name']}"
    members = await get_kingdom_members(kingdom_id)

    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        # A'zolarni reset qilish
        await conn.execute(
            "UPDATE users SET kingdom_id=NULL, vassal_id=NULL, role='member' WHERE kingdom_id=$1",
            kingdom_id
        )
        # Vassallarni o'chirish
        await conn.execute("DELETE FROM vassals WHERE kingdom_id=$1", kingdom_id)
        # Qirollikni o'chirish
        await conn.execute("DELETE FROM kingdoms WHERE id=$1", kingdom_id)

    # A'zolarga xabar
    for m in members:
        try:
            await bot.send_message(
                m["telegram_id"],
                f"⚠️ <b>{name}</b> qirolligi admin tomonidan tarqatib yuborildi.\n"
                f"Siz endi erkin holatdasiz."
            )
        except Exception:
            pass

    await add_chronicle("system", "Qirollik tarqatildi", f"{name} admin tomonidan o'chirildi", actor_id=call.from_user.id)
    await call.message.edit_text(
        f"✅ <b>{name}</b> qirolligi o'chirildi!",
        reply_markup=admin_main_kb()
    )


# ── Resurslarni tahrirlash ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_res_list")
async def cb_edit_res_list(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']} | 💰{k['gold']} ⚔️{k['soldiers']}",
            callback_data=f"admin_edit_res_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_manage_kingdoms"))
    await state.set_state(AdminStates.waiting_edit_res_kingdom)
    await call.message.edit_text(
        "✏️ <b>Qaysi qirollik resurslarini tahrirlaysiz?</b>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_edit_res_"), AdminStates.waiting_edit_res_kingdom)
async def cb_edit_res_kingdom(call: CallbackQuery, state: FSMContext):
    kingdom_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom(kingdom_id)
    await state.update_data(edit_kingdom_id=kingdom_id)
    await state.set_state(AdminStates.waiting_edit_res_type)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Oltin", callback_data="editres_gold"),
        InlineKeyboardButton(text="⚔️ Qo'shin", callback_data="editres_soldiers"),
        InlineKeyboardButton(text="🐉 Ajdar", callback_data="editres_dragons"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_edit_res_list"))
    await call.message.edit_text(
        f"✏️ <b>{kingdom['sigil']} {kingdom['name']}</b>\n\n"
        f"💰 Oltin: {kingdom['gold']}\n"
        f"⚔️ Qo'shin: {kingdom['soldiers']}\n"
        f"🐉 Ajdar: {kingdom['dragons']}\n\n"
        f"Qaysi resursni o'zgartirasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("editres_"), AdminStates.waiting_edit_res_type)
async def cb_edit_res_type(call: CallbackQuery, state: FSMContext):
    rtype = call.data.split("_")[1]
    labels = {"gold": "💰 oltin", "soldiers": "⚔️ qo'shin", "dragons": "🐉 ajdar"}
    await state.update_data(edit_res_type=rtype)
    await state.set_state(AdminStates.waiting_edit_res_amount)
    await call.message.edit_text(
        f"🔢 Yangi {labels[rtype]} miqdorini kiriting (butun son):",
        reply_markup=back_kb("admin_edit_res_list")
    )


@router.message(AdminStates.waiting_edit_res_amount)
async def msg_edit_res_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Musbat butun son kiriting.")
        return

    data = await state.get_data()
    kingdom_id = data["edit_kingdom_id"]
    rtype = data["edit_res_type"]
    kingdom = await get_kingdom(kingdom_id)
    await update_kingdom(kingdom_id, **{rtype: amount})
    await state.clear()

    labels = {"gold": "💰 oltin", "soldiers": "⚔️ qo'shin", "dragons": "🐉 ajdar"}
    await message.answer(
        f"✅ {kingdom['sigil']} <b>{kingdom['name']}</b>\n"
        f"{labels[rtype]} → <b>{amount}</b> ga o'zgartirildi!",
        reply_markup=admin_main_kb()
    )
    await add_chronicle(
        "system", "Resurs tahrirlandi",
        f"{kingdom['name']} {labels[rtype]}: {amount}",
        actor_id=message.from_user.id
    )


# ══════════════════════════════════════════════════════════════════════════════
#  STANDART 7 QIROLLIK YARATISH
# ══════════════════════════════════════════════════════════════════════════════

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
    text = f"✅ Yaratildi: {', '.join(created)}" if created else "ℹ️ Barcha 7 qirollik allaqachon mavjud"
    await call.message.edit_text(text, reply_markup=admin_main_kb())
    await add_chronicle("system", "Qirolliklar yaratildi", text, actor_id=call.from_user.id)


# ══════════════════════════════════════════════════════════════════════════════
#  QIROL TAYINLASH
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_assign_king")
async def cb_assign_king_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    if not kingdoms:
        await call.message.edit_text("❌ Avval qirolliklarni yarating!", reply_markup=admin_main_kb())
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
    text = f"✅ <b>{target_user['full_name']}</b> {kingdom['sigil']} <b>{kingdom['name']}</b> qiroli etib tayinlandi!"
    await message.answer(text, reply_markup=admin_main_kb())
    await add_chronicle("coronation", "Yangi Qirol!", f"{target_user['full_name']} — {kingdom['name']} Qiroli",
                        actor_id=message.from_user.id, target_id=king_id)


# ══════════════════════════════════════════════════════════════════════════════
#  VASSAL OʻQISH / QOʻSHISH / OʻCHIRISH
# ══════════════════════════════════════════════════════════════════════════════

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
    await call.message.edit_text("✏️ Vassal oilaning nomini kiriting:", reply_markup=back_kb("admin_main"))


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


@router.callback_query(F.data == "admin_delete_house")
async def cb_delete_house(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    vassals = await get_all_vassals()
    if not vassals:
        await call.message.edit_text("❌ Hech qanday vassal oila yo'q.", reply_markup=back_kb("admin_main"))
        return
    builder = InlineKeyboardBuilder()
    for v in vassals:
        kingdom = await get_kingdom(v["kingdom_id"])
        k_name = f"{kingdom['sigil']} {kingdom['name']}" if kingdom else "?"
        builder.row(InlineKeyboardButton(
            text=f"🗑️ {v['name']} ({k_name})",
            callback_data=f"admin_confirm_delete_{v['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    await call.message.edit_text(
        "🗑️ <b>Qaysi vassal oilani o'chirmoqchisiz?</b>\n\n⚠️ O'chirishdan oldin tasdiqlash so'raladi.",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_confirm_delete_"))
async def cb_confirm_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    vassal_id = int(call.data.split("_")[-1])
    vassal = await get_vassal(vassal_id)
    if not vassal:
        await call.message.edit_text("❌ Vassal topilmadi!", reply_markup=back_kb("admin_main"))
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chir", callback_data=f"admin_do_delete_{vassal_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="admin_delete_house")
    )
    await call.message.edit_text(
        f"⚠️ <b>{vassal['name']}</b> oilasini o'chirishni tasdiqlaysizmi?\n\nOiladagi barcha a'zolar vassalsiz qoladi.",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_do_delete_"))
async def cb_do_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    vassal_id = int(call.data.split("_")[-1])
    vassal = await get_vassal(vassal_id)
    if not vassal:
        await call.message.edit_text("❌ Vassal topilmadi!", reply_markup=back_kb("admin_main"))
        return
    name = vassal["name"]
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET vassal_id=NULL, role='member' WHERE vassal_id=$1", vassal_id)
        await conn.execute("DELETE FROM vassals WHERE id=$1", vassal_id)
    await add_chronicle("system", "Vassal o'chirildi", f"{name} oilasi admin tomonidan o'chirildi", actor_id=call.from_user.id)
    await call.message.edit_text(f"✅ <b>{name}</b> oilasi muvaffaqiyatli o'chirildi!", reply_markup=admin_main_kb())


# ══════════════════════════════════════════════════════════════════════════════
#  XRONIKA
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_write_chronicle")
async def cb_write_chronicle(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await state.set_state(AdminStates.waiting_chronicle)
    await call.message.edit_text("📜 Xronikaga yozmoqchi bo'lgan xabaringizni yuboring:", reply_markup=back_kb("admin_main"))


@router.message(AdminStates.waiting_chronicle)
async def msg_chronicle(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await add_chronicle("gm_event", "⚔️ Global Voqea", message.text, actor_id=message.from_user.id)
    await state.clear()
    await message.answer("✅ Xronikaga yozildi!", reply_markup=admin_main_kb())


# ══════════════════════════════════════════════════════════════════════════════
#  O'YIN HOLATI
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_game_status")
async def cb_game_status(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    vassals = await get_all_vassals()
    text = "📊 <b>O'yin Holati</b>\n\n"
    text += f"🏰 Qirolliklar: {len(kingdoms)}\n"
    text += f"🛡️ Vassal oilalar: {len(vassals)}\n\n"
    for k in kingdoms:
        members = await get_kingdom_members(k["id"])
        kvassals = await get_kingdom_vassals(k["id"])
        king_mark = "👑" if k["king_id"] else "❌"
        text += f"{k['sigil']} <b>{k['name']}</b> {king_mark} | 👥{len(members)} 🛡️{len(kvassals)}\n"
        text += f"  💰{k['gold']} | ⚔️{k['soldiers']} | 🐉{k['dragons']}\n"
    await call.message.edit_text(text, reply_markup=admin_main_kb())
