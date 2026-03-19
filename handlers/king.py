"""
King handlers — Decree, Resources, Punishment, Diplomacy
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.queries import (
    get_kingdom_by_king, get_kingdom, get_kingdom_vassals, get_vassal,
    get_kingdom_members, update_kingdom, update_vassal, get_user,
    add_chronicle, create_diplomacy, update_diplomacy, get_pending_diplomacy,
    get_all_kingdoms, get_vassal_members
)
from keyboards.kb import (
    king_main_kb, diplomacy_kb, kingdoms_select_kb, vassals_select_kb,
    resource_type_kb, back_kb, diplomacy_respond_kb, order_respond_kb
)
from config import PUNISHMENT_SOLDIER_COST

router = Router()


class KingStates(StatesGroup):
    waiting_decree_text = State()
    waiting_resource_vassal = State()
    waiting_resource_type = State()
    waiting_resource_amount = State()
    waiting_punish_vassal = State()
    waiting_war_target = State()
    waiting_alliance_target = State()


def is_king(db_user: dict) -> bool:
    return db_user.get("role") == "king"


# ── Main panel ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "king_main")
async def cb_king_main(call: CallbackQuery, db_user: dict):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    if not kingdom:
        await call.answer("❌ Qirollik topilmadi!")
        return
    await call.message.edit_text(
        f"👑 <b>{kingdom['sigil']} {kingdom['name']} Qiroli Paneli</b>",
        reply_markup=king_main_kb()
    )


# ── Kingdom status ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "king_status")
async def cb_king_status(call: CallbackQuery, db_user: dict):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    if not kingdom:
        await call.answer("❌ Qirollik topilmadi!")
        return
    vassals = await get_kingdom_vassals(kingdom["id"])
    members = await get_kingdom_members(kingdom["id"])

    text = f"{kingdom['sigil']} <b>{kingdom['name']} Qirollik Holati</b>\n\n"
    text += f"💰 Oltin: {kingdom['gold']}\n"
    text += f"⚔️ Qo'shin: {kingdom['soldiers']}\n"
    text += f"🐉 Ajdarlar: {kingdom['dragons']}\n"
    text += f"👥 Jami a'zolar: {len(members)}\n"
    text += f"🛡️ Vassal oilalar: {len(vassals)}\n\n"

    for v in vassals:
        lord_mark = "👑 Lord" if v["lord_id"] else "❌ Lodsiz"
        vmembers = await get_kingdom_members(kingdom["id"])
        text += f"  🛡️ <b>{v['name']}</b> — {lord_mark} | 💰 {v['gold']}\n"

    await call.message.edit_text(text, reply_markup=back_kb("king_main"))


# ── Decree (farmon) ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "king_decree")
async def cb_king_decree(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    await state.set_state(KingStates.waiting_decree_text)
    await call.message.edit_text(
        "📣 <b>Farmon matni</b>\n\nBarcha vassal va a'zolaringizga yuboriladigan farmonni yozing:",
        reply_markup=back_kb("king_main")
    )


@router.message(KingStates.waiting_decree_text)
async def msg_decree(message: Message, state: FSMContext, bot: Bot, db_user: dict):
    if not is_king(db_user):
        return
    kingdom = await get_kingdom_by_king(message.from_user.id)
    if not kingdom:
        return
    members = await get_kingdom_members(kingdom["id"])
    text = (
        f"📜 <b>QIROLLIK FARMONI</b>\n"
        f"{kingdom['sigil']} <b>{kingdom['name']}</b> Qirolidan:\n\n"
        f"{message.text}"
    )
    sent = 0
    for m in members:
        if m["telegram_id"] != message.from_user.id:
            try:
                await bot.send_message(m["telegram_id"], text)
                sent += 1
            except Exception:
                pass
    await state.clear()
    await message.answer(
        f"✅ Farmon {sent} ta a'zoga yuborildi!",
        reply_markup=king_main_kb()
    )
    await add_chronicle("decree", f"{kingdom['name']} Farmoni", message.text, actor_id=message.from_user.id, bot=bot)


# ── Request resources from vassal ─────────────────────────────────────────────

@router.callback_query(F.data == "king_request_resources")
async def cb_request_resources(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    vassals = await get_kingdom_vassals(kingdom["id"])
    if not vassals:
        await call.message.edit_text("❌ Vassallar yo'q!", reply_markup=back_kb("king_main"))
        return
    await state.set_state(KingStates.waiting_resource_vassal)
    await call.message.edit_text(
        "💰 Qaysi vassaldan resurs so'raysiz?",
        reply_markup=vassals_select_kb(vassals, "kreq_vassal")
    )


@router.callback_query(F.data.startswith("kreq_vassal_"), KingStates.waiting_resource_vassal)
async def cb_resource_vassal(call: CallbackQuery, state: FSMContext):
    vassal_id = int(call.data.split("_")[-1])
    await state.update_data(vassal_id=vassal_id)
    await state.set_state(KingStates.waiting_resource_type)
    await call.message.edit_text(
        "📦 Qaysi resurs so'raysiz?", reply_markup=resource_type_kb()
    )


@router.callback_query(F.data.startswith("resource_"), KingStates.waiting_resource_type)
async def cb_resource_type(call: CallbackQuery, state: FSMContext):
    rtype = call.data.split("_")[1]
    await state.update_data(resource_type=rtype)
    await state.set_state(KingStates.waiting_resource_amount)
    label = "oltin" if rtype == "gold" else "qo'shin"
    await call.message.edit_text(
        f"🔢 Nechta {label} so'raysiz?", reply_markup=back_kb("king_main")
    )


@router.message(KingStates.waiting_resource_amount)
async def msg_resource_amount(message: Message, state: FSMContext, bot: Bot, db_user: dict):
    if not is_king(db_user):
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting.")
        return
    data = await state.get_data()
    vassal = await get_vassal(data["vassal_id"])
    if not vassal:
        await state.clear()
        return
    kingdom = await get_kingdom_by_king(message.from_user.id)
    rtype = data["resource_type"]
    label = "💰 oltin" if rtype == "gold" else "⚔️ qo'shin"

    # Notify lord if exists
    if vassal["lord_id"]:
        try:
            await bot.send_message(
                vassal["lord_id"],
                f"👑 <b>Qirollik talabi!</b>\n\n"
                f"{kingdom['sigil']} {kingdom['name']} Qirolidan:\n"
                f"<b>{vassal['name']}</b> oilasidan {amount} {label} talab qilinmoqda!",
                reply_markup=order_respond_kb(f"{rtype}_{amount}_{vassal['id']}")
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"✅ <b>{vassal['name']}</b> Lordiga {amount} {label} talabi yuborildi!",
        reply_markup=king_main_kb()
    )
    await add_chronicle(
        "resource_demand",
        f"Resurs talabi",
        f"{kingdom['name']} Qiroli {vassal['name']}dan {amount} {label} talab qildi",
        actor_id=message.from_user.id
    )


# ── Punishment ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "king_punish")
async def cb_punish_start(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    vassals = await get_kingdom_vassals(kingdom["id"])
    if not vassals:
        await call.message.edit_text("❌ Vassallar yo'q!", reply_markup=back_kb("king_main"))
        return
    await state.set_state(KingStates.waiting_punish_vassal)
    await call.message.edit_text(
        f"⚠️ <b>OGOHLANTIRISH</b>\n\nJazo berish {PUNISHMENT_SOLDIER_COST} ta askar sarflaydi "
        f"va vassal oilani yo'q qiladi!\n\nQaysi vassalni jazolaysiz?",
        reply_markup=vassals_select_kb(vassals, "punish_vassal")
    )


@router.callback_query(F.data.startswith("punish_vassal_"), KingStates.waiting_punish_vassal)
async def cb_punish_vassal(call: CallbackQuery, state: FSMContext, db_user: dict, bot: Bot):
    vassal_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom_by_king(call.from_user.id)
    if kingdom["soldiers"] < PUNISHMENT_SOLDIER_COST:
        await call.message.edit_text(
            f"❌ Yetarli qo'shin yo'q! Kerak: {PUNISHMENT_SOLDIER_COST}, Sizda: {kingdom['soldiers']}",
            reply_markup=back_kb("king_main")
        )
        await state.clear()
        return

    vassal = await get_vassal(vassal_id)
    # Deduct soldiers & notify members
    await update_kingdom(kingdom["id"], soldiers=kingdom["soldiers"] - PUNISHMENT_SOLDIER_COST)
    members = await get_vassal_members(vassal_id)
    for m in members:
        try:
            await bot.send_message(
                m["telegram_id"],
                f"💀 <b>{vassal['name']}</b> oilasi Qirol buyrug'i bilan yo'q qilindi!"
            )
        except Exception:
            pass

    # Remove vassal & reassign members
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET vassal_id=NULL WHERE vassal_id=$1", vassal_id)
        await conn.execute("DELETE FROM vassals WHERE id=$1", vassal_id)

    await state.clear()
    await call.message.edit_text(
        f"⚔️ <b>{vassal['name']}</b> oilasi yo'q qilindi! {PUNISHMENT_SOLDIER_COST} askar sarflandi.",
        reply_markup=king_main_kb()
    )
    await add_chronicle(
        "punishment", "Oila yo'q qilindi",
        f"{kingdom['name']} Qiroli {vassal['name']} oilasini yo'q qildi",
        actor_id=call.from_user.id
    )


# ── Diplomacy ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "king_diplomacy")
async def cb_diplomacy(call: CallbackQuery, db_user: dict):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    await call.message.edit_text("🤝 <b>Diplomatiya</b>", reply_markup=diplomacy_kb())


# war.py da ishlov beriladi
# @router.callback_query(F.data == "king_declare_war")
async def cb_declare_war(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    all_kingdoms = await get_all_kingdoms()
    others = [k for k in all_kingdoms if k["id"] != kingdom["id"]]
    await state.set_state(KingStates.waiting_war_target)
    await call.message.edit_text(
        "⚔️ Qaysi qirollikka urush e'lon qilasiz?",
        reply_markup=kingdoms_select_kb(others, "war_target")
    )


# @router.callback_query(F.data.startswith("war_target_"), KingStates.waiting_war_target)
async def cb_war_target(call: CallbackQuery, state: FSMContext, bot: Bot, db_user: dict):
    target_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom_by_king(call.from_user.id)
    target = await get_kingdom(target_id)
    diplo = await create_diplomacy(kingdom["id"], target_id, "war")

    if target["king_id"]:
        try:
            await bot.send_message(
                target["king_id"],
                f"⚔️ <b>URUSH E'LONI!</b>\n\n"
                f"{kingdom['sigil']} <b>{kingdom['name']}</b> sizga urush e'lon qildi!",
                reply_markup=diplomacy_respond_kb(diplo["id"])
            )
        except Exception:
            pass

    await state.clear()
    await call.message.edit_text(
        f"⚔️ <b>{target['sigil']} {target['name']}</b> ga urush e'lon qilindi!",
        reply_markup=king_main_kb()
    )
    await add_chronicle(
        "war", "Urush e'loni!",
        f"{kingdom['name']} → {target['name']} urush e'lon qildi",
        actor_id=call.from_user.id
    )


@router.callback_query(F.data == "king_alliance")
async def cb_alliance(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    all_kingdoms = await get_all_kingdoms()
    others = [k for k in all_kingdoms if k["id"] != kingdom["id"]]
    await state.set_state(KingStates.waiting_alliance_target)
    await call.message.edit_text(
        "🤝 Qaysi qirollik bilan ittifoq tuzmoqchisiz?",
        reply_markup=kingdoms_select_kb(others, "alliance_target")
    )


@router.callback_query(F.data.startswith("alliance_target_"), KingStates.waiting_alliance_target)
async def cb_alliance_target(call: CallbackQuery, state: FSMContext, bot: Bot, db_user: dict):
    target_id = int(call.data.split("_")[-1])
    kingdom = await get_kingdom_by_king(call.from_user.id)
    target = await get_kingdom(target_id)
    diplo = await create_diplomacy(kingdom["id"], target_id, "alliance")

    if target["king_id"]:
        try:
            await bot.send_message(
                target["king_id"],
                f"🤝 <b>Ittifoq taklifi</b>\n\n"
                f"{kingdom['sigil']} <b>{kingdom['name']}</b> ittifoq tuzishni taklif qilmoqda!",
                reply_markup=diplomacy_respond_kb(diplo["id"])
            )
        except Exception:
            pass

    await state.clear()
    await call.message.edit_text(
        f"✅ Ittifoq taklifi {target['sigil']} {target['name']}ga yuborildi!",
        reply_markup=king_main_kb()
    )


@router.callback_query(F.data == "king_pending_offers")
async def cb_pending_offers(call: CallbackQuery, db_user: dict):
    if not is_king(db_user):
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    offers = await get_pending_diplomacy(kingdom["id"])
    if not offers:
        await call.message.edit_text("📭 Kutilayotgan takliflar yo'q.", reply_markup=back_kb("king_diplomacy"))
        return
    text = "📨 <b>Kelgan takliflar:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for o in offers:
        otype = "⚔️ Urush" if o["offer_type"] == "war" else "🤝 Ittifoq"
        text += f"{o['from_sigil']} {o['from_name']} → {otype}\n"
        builder.row(
            InlineKeyboardButton(text=f"✅ {o['from_name']}", callback_data=f"diplo_accept_{o['id']}"),
            InlineKeyboardButton(text="❌ Rad", callback_data=f"diplo_reject_{o['id']}")
        )
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_diplomacy"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("diplo_accept_"))
async def cb_diplo_accept(call: CallbackQuery, db_user: dict, bot: Bot):
    diplo_id = int(call.data.split("_")[-1])
    await update_diplomacy(diplo_id, "accepted")
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM diplomacy WHERE id=$1", diplo_id)
    if row:
        from_k = await get_kingdom(row["from_kingdom_id"])
        otype = "urush" if row["offer_type"] == "war" else "ittifoq"
        await add_chronicle(
            row["offer_type"],
            f"{otype.capitalize()} qabul qilindi",
            f"Diplomatik {otype}: {from_k['name']}",
            actor_id=call.from_user.id
        )
    await call.message.edit_text("✅ Taklif qabul qilindi!", reply_markup=king_main_kb())


@router.callback_query(F.data.startswith("diplo_reject_"))
async def cb_diplo_reject(call: CallbackQuery, db_user: dict):
    diplo_id = int(call.data.split("_")[-1])
    await update_diplomacy(diplo_id, "rejected")
    await call.message.edit_text("❌ Taklif rad etildi.", reply_markup=king_main_kb())
