"""
Lord (Vassal) handlers — Orders, Elections, Defection
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.queries import (
    get_vassal_by_lord, get_vassal, get_vassal_members, update_vassal,
    get_kingdom, add_chronicle, get_user, cast_vote, get_votes,
    get_election_winner, get_all_kingdoms, update_kingdom
)
from keyboards.kb import lord_main_kb, back_kb, vassals_select_kb, kingdoms_select_kb
from config import MIN_VASSAL_MEMBERS

router = Router()


class LordStates(StatesGroup):
    waiting_defect_kingdom = State()


def is_lord(db_user: dict) -> bool:
    return db_user.get("role") == "lord"


@router.callback_query(F.data == "lord_main")
async def cb_lord_main(call: CallbackQuery, db_user: dict):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    vassal = await get_vassal_by_lord(call.from_user.id)
    if not vassal:
        await call.answer("❌ Siz Lord emassiz!")
        return
    await call.message.edit_text(
        f"🛡️ <b>{vassal['name']} Lord Paneli</b>",
        reply_markup=lord_main_kb()
    )


@router.callback_query(F.data == "lord_family_status")
async def cb_family_status(call: CallbackQuery, db_user: dict):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    vassal = await get_vassal_by_lord(call.from_user.id)
    if not vassal:
        await call.answer("❌ Vassal topilmadi!")
        return
    members = await get_vassal_members(vassal["id"])
    kingdom = await get_kingdom(vassal["kingdom_id"])

    text = f"🏠 <b>{vassal['name']} Oila Holati</b>\n\n"
    text += f"🏰 Qirollik: {kingdom['sigil']} {kingdom['name']}\n"
    text += f"💰 Oila oltini: {vassal['gold']}\n"
    text += f"⚔️ Qo'shin: {vassal['soldiers']}\n"
    text += f"👥 A'zolar ({len(members)}):\n"
    for m in members:
        role_mark = "👑" if m["telegram_id"] == vassal["lord_id"] else "⚔️"
        text += f"  {role_mark} {m['full_name']} | 💰 {m['gold']}\n"

    await call.message.edit_text(text, reply_markup=back_kb("lord_main"))


# ── Order response ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("order_accept_"))
async def cb_order_accept(call: CallbackQuery, db_user: dict, bot: Bot):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    parts = call.data.replace("order_accept_", "").split("_")
    rtype, amount, vassal_id = parts[0], int(parts[1]), int(parts[2])

    vassal = await get_vassal(vassal_id)
    if not vassal:
        await call.answer("❌ Vassal topilmadi!")
        return

    # Transfer resources from vassal to kingdom
    kingdom = await get_kingdom(vassal["kingdom_id"])
    label = "oltin" if rtype == "gold" else "qo'shin"

    if rtype == "gold":
        if vassal["gold"] < amount:
            await call.message.edit_text(
                f"❌ Yetarli oltin yo'q! Sizda: {vassal['gold']}, Talab: {amount}",
                reply_markup=back_kb("lord_main")
            )
            return
        await update_vassal(vassal_id, gold=vassal["gold"] - amount)
        await update_kingdom(kingdom["id"], gold=kingdom["gold"] + amount)
    else:
        if vassal["soldiers"] < amount:
            await call.message.edit_text(
                f"❌ Yetarli qo'shin yo'q! Sizda: {vassal['soldiers']}, Talab: {amount}",
                reply_markup=back_kb("lord_main")
            )
            return
        await update_vassal(vassal_id, soldiers=vassal["soldiers"] - amount)
        await update_kingdom(kingdom["id"], soldiers=kingdom["soldiers"] + amount)

    # Notify king
    if kingdom["king_id"]:
        try:
            await bot.send_message(
                kingdom["king_id"],
                f"✅ <b>{vassal['name']}</b> Lordi {amount} {label} yubordi!"
            )
        except Exception:
            pass

    await call.message.edit_text(
        f"✅ {amount} {label} Qirolga yuborildi!", reply_markup=lord_main_kb()
    )
    await add_chronicle(
        "tribute", "Soliq to'landi",
        f"{vassal['name']} → {kingdom['name']}: {amount} {label}",
        actor_id=call.from_user.id
    )


@router.callback_query(F.data.startswith("order_reject_"))
async def cb_order_reject(call: CallbackQuery, db_user: dict, bot: Bot):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    vassal = await get_vassal_by_lord(call.from_user.id)
    if not vassal:
        return
    kingdom = await get_kingdom(vassal["kingdom_id"])

    # Warn king about refusal
    if kingdom["king_id"]:
        try:
            await bot.send_message(
                kingdom["king_id"],
                f"⚠️ <b>{vassal['name']}</b> Lordi sizning talabingizni RAD ETDI!\n"
                f"Jazo choralarini ko'rishingiz mumkin."
            )
        except Exception:
            pass

    await call.message.edit_text(
        "❌ Talab rad etildi. Qirolga xabar yuborildi.", reply_markup=lord_main_kb()
    )
    await add_chronicle(
        "defiance", "Talabga qarshi chiqish",
        f"{vassal['name']} Lordi Qirol talabini rad etdi",
        actor_id=call.from_user.id
    )


# ── Election ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "lord_election")
async def cb_election(call: CallbackQuery, db_user: dict):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    vassal = await get_vassal_by_lord(call.from_user.id)
    if not vassal:
        return
    members = await get_vassal_members(vassal["id"])
    if len(members) < MIN_VASSAL_MEMBERS:
        await call.message.edit_text(
            f"❌ Saylov uchun kamida {MIN_VASSAL_MEMBERS} a'zo kerak. "
            f"Hozir: {len(members)}",
            reply_markup=back_kb("lord_main")
        )
        return

    votes = await get_votes(vassal["id"])
    text = f"🗳️ <b>{vassal['name']} Saylov Natijalari</b>\n\n"
    for v in votes:
        user = await get_user(v["candidate_id"])
        name = user["full_name"] if user else str(v["candidate_id"])
        text += f"  👤 {name}: {v['votes']} ovoz\n"
    if not votes:
        text += "Hali ovoz berilmagan.\n"
    text += f"\nJami a'zolar: {len(members)}"

    await call.message.edit_text(text, reply_markup=back_kb("lord_main"))


# ── Defection (panoh so'rash) ─────────────────────────────────────────────────

@router.callback_query(F.data == "lord_defect")
async def cb_defect(call: CallbackQuery, db_user: dict, state: FSMContext):
    if not is_lord(db_user):
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    all_kingdoms = await get_all_kingdoms()
    vassal = await get_vassal_by_lord(call.from_user.id)
    others = [k for k in all_kingdoms if k["id"] != vassal["kingdom_id"]]
    await state.set_state(LordStates.waiting_defect_kingdom)
    await call.message.edit_text(
        "🚀 <b>Panoh so'rash</b>\n\nQaysi Qirollik panohiga o'tmoqchisiz?",
        reply_markup=kingdoms_select_kb(others, "defect_to")
    )


@router.callback_query(F.data.startswith("defect_to_"), LordStates.waiting_defect_kingdom)
async def cb_defect_to(call: CallbackQuery, state: FSMContext, db_user: dict, bot: Bot):
    target_id = int(call.data.split("_")[-1])
    vassal = await get_vassal_by_lord(call.from_user.id)
    target_kingdom = await get_kingdom(target_id)
    old_kingdom = await get_kingdom(vassal["kingdom_id"])

    # Notify old king
    if old_kingdom["king_id"]:
        try:
            await bot.send_message(
                old_kingdom["king_id"],
                f"⚠️ <b>XIYONAT!</b>\n\n"
                f"<b>{vassal['name']}</b> Lordi {target_kingdom['sigil']} "
                f"{target_kingdom['name']} qirolligiga o'tmoqchi!"
            )
        except Exception:
            pass

    # Notify target king
    if target_kingdom["king_id"]:
        try:
            await bot.send_message(
                target_kingdom["king_id"],
                f"📨 <b>{vassal['name']}</b> Lordi sizning qirolligingizga panoh so'ramoqda!\n"
                f"Qabul qilish uchun admin bilan bog'laning."
            )
        except Exception:
            pass

    await update_vassal(vassal["id"], kingdom_id=target_id)
    # Update all vassal members
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET kingdom_id=$1 WHERE vassal_id=$2",
            target_id, vassal["id"]
        )

    await state.clear()
    await call.message.edit_text(
        f"✅ Siz {target_kingdom['sigil']} <b>{target_kingdom['name']}</b> qirolligiga o'tdingiz!",
        reply_markup=lord_main_kb()
    )
    await add_chronicle(
        "defection", "Xiyonat!",
        f"{vassal['name']} {old_kingdom['name']}dan {target_kingdom['name']}ga o'tdi",
        actor_id=call.from_user.id
    )
