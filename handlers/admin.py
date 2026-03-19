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
    get_kingdom_members, get_kingdom_vassals, get_vassal_members,
    get_all_prices, update_price, create_loan, get_all_active_loans,
    repay_loan, get_loan, get_loans
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
    # Member ko'chirish
    waiting_move_user_id      = State()
    waiting_move_target_type  = State()
    waiting_move_kingdom      = State()
    waiting_move_vassal       = State()
    # Temir Bank
    waiting_price_item        = State()
    waiting_price_amount      = State()
    waiting_loan_type         = State()
    waiting_loan_borrower     = State()
    waiting_loan_amount       = State()
    waiting_loan_interest     = State()
    waiting_repay_loan        = State()
    waiting_repay_amount      = State()


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

    await add_chronicle("system", "Qirollik tarqatildi", f"{name} admin tomonidan o'chirildi", actor_id=call.from_user.id, bot=bot)
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
        await conn.execute("UPDATE users SET vassal_id=NULL, kingdom_id=NULL, role='member' WHERE vassal_id=$1", vassal_id)
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


# ══════════════════════════════════════════════════════════════════════════════
#  A'ZONI KO'CHIRISH (QIROLLIK YOKI VASSALGA)
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_move_user")
async def cb_move_user_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    await state.set_state(AdminStates.waiting_move_user_id)
    await call.message.edit_text(
        "🔀 <b>A'zoni ko'chirish</b>\n\n"
        "Ko'chirmoqchi bo'lgan foydalanuvchining Telegram ID sini yuboring:",
        reply_markup=back_kb("admin_main")
    )


@router.message(AdminStates.waiting_move_user_id)
async def msg_move_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri ID. Faqat raqam kiriting.")
        return

    target = await get_user(user_id)
    if not target:
        await message.answer("❌ Foydalanuvchi topilmadi (avval /start bosishi kerak).")
        return
    if target["role"] in ("admin",):
        await message.answer("❌ Admin boshqa joyga ko'chirilmaydi!")
        return

    await state.update_data(move_user_id=user_id)
    await state.set_state(AdminStates.waiting_move_target_type)

    name = target["full_name"] or target["username"] or str(user_id)
    role_emoji = {"king": "👑", "lord": "🛡️", "member": "⚔️"}.get(target["role"], "⚔️")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏰 Qirollikka ko'chirish", callback_data="move_to_kingdom"))
    builder.row(InlineKeyboardButton(text="🛡️ Vassalga ko'chirish", callback_data="move_to_vassal"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_move_user"))

    await message.answer(
        f"👤 <b>{name}</b> {role_emoji}\n\n"
        f"Hozirgi joyi:\n"
        f"🏰 Kingdom ID: {target.get('kingdom_id', 'Yoq')}\n"
        f"🛡️ Vassal ID: {target.get('vassal_id', 'Yoq')}\n\n"
        f"Qayerga ko'chirasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "move_to_kingdom", AdminStates.waiting_move_target_type)
async def cb_move_to_kingdom(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdoms = await get_all_kingdoms()
    if not kingdoms:
        await call.message.edit_text("❌ Qirolliklar yo'q!", reply_markup=back_kb("admin_main"))
        return
    await state.set_state(AdminStates.waiting_move_kingdom)
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        members = await get_kingdom_members(k["id"])
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']} ({len(members)} kishi)",
            callback_data=f"move_kingdom_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_move_user"))
    await call.message.edit_text(
        "🏰 Qaysi qirollikka ko'chirasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("move_kingdom_"), AdminStates.waiting_move_kingdom)
async def cb_do_move_kingdom(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    kingdom_id = int(call.data.split("_")[-1])
    data = await state.get_data()
    user_id = data["move_user_id"]

    target = await get_user(user_id)
    kingdom = await get_kingdom(kingdom_id)

    # Eski lord lavozimini olib tashlash
    if target["role"] == "lord" and target.get("vassal_id"):
        await update_vassal(target["vassal_id"], lord_id=None)

    await update_user(user_id,
        kingdom_id=kingdom_id,
        vassal_id=None,
        role="member"
    )
    await state.clear()

    name = target["full_name"] or str(user_id)
    try:
        await bot.send_message(
            user_id,
            f"🔀 <b>Admin sizni ko'chirdi!</b>\n\n"
            f"Yangi qirolligingiz: {kingdom['sigil']} <b>{kingdom['name']}</b>"
        )
    except Exception:
        pass

    await add_chronicle(
        "system", "A'zo ko'chirildi",
        f"{name} → {kingdom['sigil']} {kingdom['name']} qirolligiga",
        actor_id=call.from_user.id
    )
    await call.message.edit_text(
        f"✅ <b>{name}</b> {kingdom['sigil']} <b>{kingdom['name']}</b> qirolligiga ko'chirildi!",
        reply_markup=admin_main_kb()
    )


@router.callback_query(F.data == "move_to_vassal", AdminStates.waiting_move_target_type)
async def cb_move_to_vassal(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    vassals = await get_all_vassals()
    if not vassals:
        await call.message.edit_text("❌ Vassal oilalar yo'q!", reply_markup=back_kb("admin_main"))
        return
    await state.set_state(AdminStates.waiting_move_vassal)
    builder = InlineKeyboardBuilder()
    for v in vassals:
        kingdom = await get_kingdom(v["kingdom_id"])
        k_name = f"{kingdom['sigil']} {kingdom['name']}" if kingdom else "?"
        members = await get_vassal_members(v["id"])
        builder.row(InlineKeyboardButton(
            text=f"🛡️ {v['name']} • {k_name} ({len(members)} kishi)",
            callback_data=f"move_vassal_{v['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_move_user"))
    await call.message.edit_text(
        "🛡️ Qaysi vassal oilaga ko'chirasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("move_vassal_"), AdminStates.waiting_move_vassal)
async def cb_do_move_vassal(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    vassal_id = int(call.data.split("_")[-1])
    data = await state.get_data()
    user_id = data["move_user_id"]

    target = await get_user(user_id)
    vassal = await get_vassal(vassal_id)
    kingdom = await get_kingdom(vassal["kingdom_id"])

    # Eski lord lavozimini olib tashlash
    if target["role"] == "lord" and target.get("vassal_id"):
        await update_vassal(target["vassal_id"], lord_id=None)

    await update_user(user_id,
        kingdom_id=vassal["kingdom_id"],
        vassal_id=vassal_id,
        role="member"
    )
    await state.clear()

    name = target["full_name"] or str(user_id)
    try:
        await bot.send_message(
            user_id,
            f"🔀 <b>Admin sizni ko'chirdi!</b>\n\n"
            f"Yangi oilangiz: 🛡️ <b>{vassal['name']}</b>\n"
            f"Qirollik: {kingdom['sigil']} <b>{kingdom['name']}</b>"
        )
    except Exception:
        pass

    await add_chronicle(
        "system", "A'zo ko'chirildi",
        f"{name} → {vassal['name']} oilasiga ({kingdom['name']})",
        actor_id=call.from_user.id
    )
    await call.message.edit_text(
        f"✅ <b>{name}</b> 🛡️ <b>{vassal['name']}</b> oilasiga ko'chirildi!",
        reply_markup=admin_main_kb()
    )


# ══════════════════════════════════════════════════════════════════════════════
#  TEMIR BANK BOSHQARUVI
# ══════════════════════════════════════════════════════════════════════════════

def iron_bank_admin_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Narxlarni o'zgartirish", callback_data="admin_bank_prices"))
    builder.row(InlineKeyboardButton(text="🏰 Qirollikka qarz berish", callback_data="admin_loan_kingdom"))
    builder.row(InlineKeyboardButton(text="🛡️ Vassalga qarz berish", callback_data="admin_loan_vassal"))
    builder.row(InlineKeyboardButton(text="📋 Barcha qarzlar", callback_data="admin_all_loans"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    return builder.as_markup()


@router.callback_query(F.data == "admin_iron_bank")
async def cb_iron_bank(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    prices = await get_all_prices()
    text = "🏦 <b>Temir Bank Boshqaruvi</b>\n\n"
    text += "📦 <b>Hozirgi narxlar:</b>\n"
    for item, info in prices.items():
        text += f"  {info['label']}: <b>{info['price']}💰</b>\n"
    await call.message.edit_text(text, reply_markup=iron_bank_admin_kb())


# ── Narx o'zgartirish ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_bank_prices")
async def cb_bank_prices(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    prices = await get_all_prices()
    builder = InlineKeyboardBuilder()
    for item, info in prices.items():
        builder.row(InlineKeyboardButton(
            text=f"{info['label']} — {info['price']}💰",
            callback_data=f"admin_setprice_{item}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_iron_bank"))
    await state.set_state(AdminStates.waiting_price_item)
    await call.message.edit_text(
        "💰 <b>Qaysi tovar narxini o'zgartirmoqchisiz?</b>",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("admin_setprice_"), AdminStates.waiting_price_item)
async def cb_setprice_item(call: CallbackQuery, state: FSMContext):
    item = call.data.replace("admin_setprice_", "")
    prices = await get_all_prices()
    info = prices.get(item, {})
    await state.update_data(price_item=item, price_label=info.get("label", item))
    await state.set_state(AdminStates.waiting_price_amount)
    await call.message.edit_text(
        f"🔢 <b>{info.get('label', item)}</b> uchun yangi narx kiriting\n"
        f"(hozirgi: {info.get('price', '?')}💰):",
        reply_markup=back_kb("admin_bank_prices")
    )


@router.message(AdminStates.waiting_price_amount)
async def msg_price_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Musbat butun son kiriting.")
        return
    data = await state.get_data()
    item = data["price_item"]
    label = data["price_label"]
    await update_price(item, price)
    await state.clear()
    await message.answer(
        f"✅ {label} narxi <b>{price}💰</b> ga o'zgartirildi!",
        reply_markup=admin_main_kb()
    )
    await add_chronicle("system", "Narx o'zgartirildi",
                        f"{label}: {price} oltin", actor_id=message.from_user.id)


# ── Qarz berish ───────────────────────────────────────────────────────────────

async def _start_loan(call, state, borrower_type: str):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    if borrower_type == "kingdom":
        items = await get_all_kingdoms()
        builder = InlineKeyboardBuilder()
        for k in items:
            builder.row(InlineKeyboardButton(
                text=f"{k['sigil']} {k['name']} | 💰{k['gold']}",
                callback_data=f"loan_borrower_kingdom_{k['id']}"
            ))
    else:
        items = await get_all_vassals()
        builder = InlineKeyboardBuilder()
        for v in items:
            kingdom = await get_kingdom(v["kingdom_id"])
            k_name = f"{kingdom['sigil']}{kingdom['name']}" if kingdom else "?"
            builder.row(InlineKeyboardButton(
                text=f"🛡️ {v['name']} • {k_name} | 💰{v['gold']}",
                callback_data=f"loan_borrower_vassal_{v['id']}"
            ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_iron_bank"))
    await state.set_state(AdminStates.waiting_loan_borrower)
    label = "Qirollik" if borrower_type == "kingdom" else "Vassal oila"
    await call.message.edit_text(
        f"🏦 Qaysi {label}ga qarz berasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_loan_kingdom")
async def cb_loan_kingdom(call: CallbackQuery, state: FSMContext):
    await state.update_data(loan_type="kingdom")
    await _start_loan(call, state, "kingdom")


@router.callback_query(F.data == "admin_loan_vassal")
async def cb_loan_vassal(call: CallbackQuery, state: FSMContext):
    await state.update_data(loan_type="vassal")
    await _start_loan(call, state, "vassal")


@router.callback_query(F.data.startswith("loan_borrower_"), AdminStates.waiting_loan_borrower)
async def cb_loan_borrower(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    # loan_borrower_kingdom_5  yoki  loan_borrower_vassal_3
    btype = parts[2]
    bid = int(parts[3])
    await state.update_data(loan_borrower_type=btype, loan_borrower_id=bid)
    await state.set_state(AdminStates.waiting_loan_amount)
    await call.message.edit_text(
        "💰 Qarz miqdorini kiriting (oltin):",
        reply_markup=back_kb("admin_iron_bank")
    )


@router.message(AdminStates.waiting_loan_amount)
async def msg_loan_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Musbat butun son kiriting.")
        return
    await state.update_data(loan_amount=amount)
    await state.set_state(AdminStates.waiting_loan_interest)
    await message.answer(
        f"📊 Foiz stavkasini kiriting (%)\n"
        f"(0 kiritsangiz — foizsiz qarz):",
        reply_markup=back_kb("admin_iron_bank")
    )


@router.message(AdminStates.waiting_loan_interest)
async def msg_loan_interest(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        interest = int(message.text.strip())
        if interest < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ 0 yoki undan katta son kiriting.")
        return

    data = await state.get_data()
    btype = data["loan_borrower_type"]
    bid = data["loan_borrower_id"]
    amount = data["loan_amount"]
    total = amount + (amount * interest // 100)

    # Qarzni DB ga yozish
    loan = await create_loan(btype, bid, amount, interest)

    # Oltin berish
    if btype == "kingdom":
        obj = await get_kingdom(bid)
        await update_kingdom(bid, gold=obj["gold"] + amount)
        obj_name = f"{obj['sigil']} {obj['name']}"
        # Qirolga xabar
        if obj["king_id"]:
            try:
                await bot.send_message(
                    obj["king_id"],
                    f"🏦 <b>Temir Bank qarzi!</b>\n\n"
                    f"💰 Miqdor: {amount} oltin\n"
                    f"📊 Foiz: {interest}%\n"
                    f"💸 Qaytarish: {total} oltin\n\n"
                    f"Oltin xazinangizga qo'shildi!"
                )
            except Exception:
                pass
    else:
        obj = await get_vassal(bid)
        await update_vassal(bid, gold=obj["gold"] + amount)
        obj_name = obj["name"]
        # Lordga xabar
        if obj["lord_id"]:
            try:
                await bot.send_message(
                    obj["lord_id"],
                    f"🏦 <b>Temir Bank qarzi!</b>\n\n"
                    f"💰 Miqdor: {amount} oltin\n"
                    f"📊 Foiz: {interest}%\n"
                    f"💸 Qaytarish: {total} oltin\n\n"
                    f"Oltin oila xazinasiga qo'shildi!"
                )
            except Exception:
                pass

    await state.clear()
    foiz_text = f"{interest}% foiz bilan" if interest > 0 else "foizsiz"
    await message.answer(
        f"✅ <b>{obj_name}</b> ga qarz berildi!\n\n"
        f"💰 Berildi: {amount} oltin ({foiz_text})\n"
        f"💸 Qaytarish kerak: {total} oltin",
        reply_markup=admin_main_kb()
    )
    await add_chronicle("loan", "Temir Bank qarzi",
                        f"{obj_name}: {amount} oltin ({foiz_text})",
                        actor_id=message.from_user.id)


# ── Barcha qarzlar ro'yxati ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin_all_loans")
async def cb_all_loans(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    loans = await get_all_active_loans()
    if not loans:
        await call.message.edit_text(
            "📋 Hozircha faol qarz yo'q.",
            reply_markup=back_kb("admin_iron_bank")
        )
        return

    builder = InlineKeyboardBuilder()
    text = "📋 <b>Faol qarzlar:</b>\n\n"
    for loan in loans:
        if loan["borrower_type"] == "kingdom":
            obj = await get_kingdom(loan["borrower_id"])
            name = f"{obj['sigil']} {obj['name']}" if obj else "?"
        else:
            obj = await get_vassal(loan["borrower_id"])
            name = f"🛡️ {obj['name']}" if obj else "?"

        remaining = loan["total_due"] - loan["paid"]
        text += (
            f"🆔 #{loan['id']} — {name}\n"
            f"  💰 Qarz: {loan['amount']} | 💸 Qoldi: {remaining}\n"
        )
        builder.row(InlineKeyboardButton(
            text=f"✅ #{loan['id']} {name} — {remaining}💰 qoldi",
            callback_data=f"admin_repay_{loan['id']}"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_iron_bank"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin_repay_"))
async def cb_repay_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return
    loan_id = int(call.data.split("_")[-1])
    loan = await get_loan(loan_id)
    if not loan:
        await call.answer("❌ Qarz topilmadi!")
        return
    remaining = loan["total_due"] - loan["paid"]
    await state.update_data(repay_loan_id=loan_id)
    await state.set_state(AdminStates.waiting_repay_amount)
    await call.message.edit_text(
        f"💸 <b>Qarz #{loan_id}</b>\n\n"
        f"Jami: {loan['total_due']} | To'langan: {loan['paid']} | Qoldi: {remaining}\n\n"
        f"To'lanayotgan miqdorni kiriting:",
        reply_markup=back_kb("admin_all_loans")
    )


@router.message(AdminStates.waiting_repay_amount)
async def msg_repay_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Musbat son kiriting.")
        return

    data = await state.get_data()
    loan_id = data["repay_loan_id"]
    loan = await repay_loan(loan_id, amount)
    await state.clear()

    if loan["status"] == "paid":
        status_text = "✅ <b>Qarz to'liq yopildi!</b>"
    else:
        remaining = loan["total_due"] - loan["paid"]
        status_text = f"💸 Qolgan qarz: <b>{remaining}</b> oltin"

    await message.answer(
        f"✅ #{loan_id} qarzga {amount} oltin to'landi!\n\n{status_text}",
        reply_markup=admin_main_kb()
    )


# ══════════════════════════════════════════════════════════════════════════════
#  O'YINNI TO'XTATISH / DAVOM ETTIRISH
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_pause_game")
async def cb_pause_game(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return

    from database.queries import get_game_active, set_game_active
    is_active = await get_game_active()

    if is_active:
        # O'yinni to'xtatish
        await set_game_active(False)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="▶️ O'yinni davom ettirish",
            callback_data="admin_resume_game"
        ))
        builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
        await call.message.edit_text(
            "⏸️ <b>O'yin to'xtatildi!</b>\n\n"
            "Barcha tugmalar va buyruqlar vaqtincha bloklandi.\n"
            "Faqat Admin ishlashi mumkin.",
            reply_markup=builder.as_markup()
        )
        # Barcha foydalanuvchilarga xabar
        from database.queries import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            members = await conn.fetch("SELECT telegram_id FROM users")
        for m in members:
            try:
                await bot.send_message(
                    m["telegram_id"],
                    "⏸️ <b>O'yin vaqtincha to'xtatildi!</b>\n\n"
                    "Admin tez orada davom ettiradi..."
                )
            except Exception:
                pass
        await add_chronicle(
            "system", "⏸️ O'yin to'xtatildi",
            "Admin tomonidan o'yin vaqtincha to'xtatildi",
            actor_id=call.from_user.id, bot=bot
        )
    else:
        await call.answer("O'yin allaqachon to'xtatilgan!", show_alert=True)


@router.callback_query(F.data == "admin_resume_game")
async def cb_resume_game(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Ruxsat yo'q!")
        return

    from database.queries import set_game_active
    await set_game_active(True)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⏸️ O'yinni to'xtatish",
        callback_data="admin_pause_game"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    await call.message.edit_text(
        "▶️ <b>O'yin davom ettirildi!</b>\n\n"
        "Barcha tugmalar va buyruqlar faollashdi.",
        reply_markup=builder.as_markup()
    )

    # Barcha foydalanuvchilarga xabar
    from database.queries import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        members = await conn.fetch("SELECT telegram_id FROM users")
    for m in members:
        try:
            await bot.send_message(
                m["telegram_id"],
                "▶️ <b>O'yin davom ettirildi!</b>\n\n"
                "Endi barcha funksiyalar ishlaydi! ⚔️"
            )
        except Exception:
            pass
    await add_chronicle(
        "system", "▶️ O'yin davom ettirildi",
        "Admin tomonidan o'yin qayta ishga tushirildi",
        actor_id=call.from_user.id, bot=bot
    )
