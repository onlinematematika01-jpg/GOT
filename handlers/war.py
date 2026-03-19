"""
Urush tizimi — to'liq
Vaqt: 20:00 - 22:00 (UTC+5) urush e'lon qilish
      22:00 - 00:00 → ertasi 20:00 da boshlanadi
Raundlar: 3 ta
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import asyncio
import logging

from database.queries import (
    get_kingdom_by_king, get_kingdom, get_all_kingdoms,
    update_kingdom, get_kingdom_members, get_vassal_members,
    get_kingdom_vassals, get_vassal, update_vassal,
    add_chronicle, get_artifacts,
    create_war, get_war, update_war, get_active_war,
    add_war_support, get_war_support, create_tribute, get_active_tributes
)
from keyboards.kb import back_kb, king_main_kb

router = Router()
logger = logging.getLogger(__name__)

# ── Konstantalar ──────────────────────────────────────────────────────────────
WAR_START_HOUR   = 20   # UTC+5
WAR_CUTOFF_HOUR  = 22   # Bu vaqtdan keyin ertaga
WAR_END_HOUR     = 23
ROUND_DELAY      = 30   # Raundlar orasidagi soniya (test uchun 30s, real uchun 300s)

# Kuch hisoblash
DRAGON_A_POWER   = 100
DRAGON_B_POWER   = 50
DRAGON_C_POWER   = 25
SCORPION_POWER   = 1

# Chayon effekti
SCORPION_KILL_A  = 3    # 3 chayon → Ajdar A o'ladi
SCORPION_SKIP_A  = 2    # 2 chayon → Ajdar A 1 raund o'tkazib yuboradi
SCORPION_KILL_C  = 1    # 1 chayon → Ajdar C o'ladi

# ── Vaqt yordamchilari ────────────────────────────────────────────────────────

def now_uz():
    """UTC+5 hozirgi vaqt"""
    return datetime.utcnow() + timedelta(hours=5)


def get_war_start_time() -> datetime:
    """Urush qachon boshlanishini hisoblash"""
    now = now_uz()
    hour = now.hour
    if WAR_START_HOUR <= hour < WAR_CUTOFF_HOUR:
        # Bugun 1 soatdan keyin
        start = now + timedelta(hours=1)
        return start.replace(second=0, microsecond=0)
    elif WAR_CUTOFF_HOUR <= hour <= 23:
        # Ertaga 20:00
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=WAR_START_HOUR, minute=0, second=0, microsecond=0)
    else:
        # 00:00 - 20:00 oralig'i — e'lon qilib bo'lmaydi
        return None


def can_declare_war() -> bool:
    hour = now_uz().hour
    return WAR_START_HOUR <= hour <= 23


# ── Urush e'lon qilish ────────────────────────────────────────────────────────

class WarStates(StatesGroup):
    waiting_target = State()
    waiting_support_type = State()
    waiting_support_gold = State()
    waiting_support_soldiers = State()
    waiting_support_scorpions = State()


@router.callback_query(F.data == "king_declare_war")
async def cb_declare_war(call: CallbackQuery, db_user: dict, state: FSMContext):
    if db_user.get("role") != "king":
        await call.answer("👑 Faqat Qirollar uchun!")
        return

    if not can_declare_war():
        now = now_uz()
        await call.message.edit_text(
            f"⏰ <b>Urush e'lon qilish vaqti emas!</b>\n\n"
            f"Urushlar faqat <b>20:00 — 00:00</b> oralig'ida e'lon qilinadi.\n"
            f"Hozirgi vaqt: {now.strftime('%H:%M')} (UTC+5)",
            reply_markup=back_kb("king_diplomacy")
        )
        return

    my_kingdom = await get_kingdom_by_king(call.from_user.id)
    active = await get_active_war(my_kingdom["id"])
    if active:
        await call.message.edit_text(
            "❌ Siz allaqachon urushdasiz!",
            reply_markup=back_kb("king_diplomacy")
        )
        return

    kingdoms = await get_all_kingdoms()
    others = [k for k in kingdoms if k["id"] != my_kingdom["id"]]

    builder = InlineKeyboardBuilder()
    for k in others:
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']} | 💰{k['gold']} ⚔️{k['soldiers']}",
            callback_data=f"war_target_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_diplomacy"))

    start_time = get_war_start_time()
    now = now_uz()
    if now.hour >= WAR_CUTOFF_HOUR:
        time_text = f"⏰ Urush ertaga <b>20:00</b> da boshlanadi"
    else:
        time_text = f"⏰ Urush <b>1 soatdan</b> keyin boshlanadi ({start_time.strftime('%H:%M')})"

    await state.set_state(WarStates.waiting_target)
    await call.message.edit_text(
        f"⚔️ <b>Urush e'lon qilish</b>\n\n"
        f"{time_text}\n\n"
        f"Qaysi qirollikka urush ochasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("war_target_"), WarStates.waiting_target)
async def cb_war_target(call: CallbackQuery, state: FSMContext, db_user: dict, bot: Bot):
    target_id = int(call.data.split("_")[-1])
    my_kingdom = await get_kingdom_by_king(call.from_user.id)
    target = await get_kingdom(target_id)

    start_time = get_war_start_time()
    # UTC ga qaytarish (DB uchun)
    start_utc = start_time - timedelta(hours=5)

    war = await create_war(my_kingdom["id"], target_id, start_utc)

    now = now_uz()
    if now.hour >= WAR_CUTOFF_HOUR:
        time_text = f"ertaga soat 20:00 da"
    else:
        time_text = f"{start_time.strftime('%H:%M')} da (1 soatdan keyin)"

    # ── Mudofaa qirolligiga ogohlantirish ────────────────────────────────────
    defender_members = await get_kingdom_members(target_id)
    warning_text = (
        f"🚨 <b>URUSH E'LONI! XAVF!</b> 🚨\n\n"
        f"⚔️ {my_kingdom['sigil']} <b>{my_kingdom['name']}</b> qirolligi\n"
        f"sizning {target['sigil']} <b>{target['name']}</b> qirolligingizga\n"
        f"<b>URUSH E'LON QILDI!</b>\n\n"
        f"⏰ Urush {time_text} boshlanadi!\n\n"
        f"🛡️ Vassallar — Qirolingizga yordam yuboring!\n"
        f"👑 Qirol — Ittifoqchilardan yordam so'rang!"
    )
    for m in defender_members:
        try:
            await bot.send_message(m["telegram_id"], warning_text)
        except Exception:
            pass

    # ── Qirolga taslim/qabul tugmalari ───────────────────────────────────────
    if target["king_id"]:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⚔️ Urushni qabul qilaman", callback_data=f"war_accept_{war['id']}"),
            InlineKeyboardButton(text="🏳️ Taslim bo'laman", callback_data=f"war_surrender_{war['id']}")
        )
        kb.row(InlineKeyboardButton(text="📨 Yordam so'rash", callback_data=f"war_request_help_{war['id']}"))
        try:
            await bot.send_message(
                target["king_id"],
                f"👑 <b>Qirol, qaror qabul qiling!</b>\n\n"
                f"⚔️ {my_kingdom['sigil']} {my_kingdom['name']} urush e'lon qildi!\n"
                f"⏰ {time_text} boshlanadi",
                reply_markup=kb.as_markup()
            )
        except Exception:
            pass

    # ── Hujumchi qirolligiga xabar ────────────────────────────────────────────
    attacker_members = await get_kingdom_members(my_kingdom["id"])
    for m in attacker_members:
        try:
            await bot.send_message(
                m["telegram_id"],
                f"⚔️ <b>{my_kingdom['sigil']} {my_kingdom['name']}</b> qirolligi\n"
                f"{target['sigil']} <b>{target['name']}</b> ga urush e'lon qildi!\n"
                f"⏰ Urush {time_text} boshlanadi!"
            )
        except Exception:
            pass

    await state.clear()
    await call.message.edit_text(
        f"✅ <b>{target['sigil']} {target['name']}</b> ga urush e'lon qilindi!\n"
        f"⏰ Boshlanish vaqti: {time_text}",
        reply_markup=king_main_kb()
    )
    await add_chronicle(
        "war", f"⚔️ Urush e'loni!",
        f"{my_kingdom['name']} → {target['name']} | Boshlanish: {time_text}",
        actor_id=call.from_user.id
    )

    # Scheduler o'rniga — kutish vazifasini background da ishga tushirish
    delay_seconds = (start_utc - datetime.utcnow()).total_seconds()
    if delay_seconds > 0:
        asyncio.create_task(_wait_and_start_war(bot, war["id"], delay_seconds))


# ── Taslim bo'lish ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("war_surrender_"))
async def cb_war_surrender(call: CallbackQuery, db_user: dict, bot: Bot):
    war_id = int(call.data.split("_")[-1])
    war = await get_war(war_id)
    if not war or war["status"] == "finished":
        await call.answer("❌ Bu urush allaqachon tugagan!")
        return

    defender = await get_kingdom(war["defender_id"])
    attacker = await get_kingdom(war["attacker_id"])

    if not (db_user.get("role") == "king" and defender["king_id"] == call.from_user.id):
        await call.answer("👑 Faqat mudofaa Qiroli taslim bo'la oladi!")
        return

    await _process_surrender(bot, war, attacker, defender)
    await call.message.edit_text(
        f"🏳️ Siz taslim bo'ldingiz.\n"
        f"💰 Resurslarning 50% {attacker['sigil']} {attacker['name']}ga o'tkazildi.\n"
        f"📅 Har shanba boyligingizning 10% tribute sifatida o'tadi.",
        reply_markup=king_main_kb()
    )


async def _process_surrender(bot: Bot, war, attacker, defender):
    """Taslim bo'lish — resurs o'tkazish + tribute"""
    # 50% resurs o'tkazish
    gold_transfer = defender["gold"] // 2
    soldiers_transfer = defender["soldiers"] // 2

    await update_kingdom(attacker["id"],
        gold=attacker["gold"] + gold_transfer,
        soldiers=attacker["soldiers"] + soldiers_transfer
    )
    await update_kingdom(defender["id"],
        gold=defender["gold"] - gold_transfer,
        soldiers=defender["soldiers"] - soldiers_transfer
    )

    # Qirolni ag'darish
    await update_kingdom(defender["id"], king_id=None)
    from database.queries import update_user
    await update_user(defender["king_id"], role="member")

    # Tribute yoqish
    await create_tribute(war["id"], defender["id"], attacker["id"])
    await update_war(war["id"], status="finished", surrender=True,
                     winner_id=attacker["id"], tribute_active=True)

    # Xabar
    chronicle_text = (
        f"🏳️ {defender['name']} taslim bo'ldi!\n"
        f"💰 {gold_transfer} oltin + {soldiers_transfer} askar {attacker['name']}ga o'tdi\n"
        f"📅 Har shanba tribute: 10%"
    )
    await add_chronicle("war_end", f"🏳️ Taslim!", chronicle_text, bot=bot)

    # Barcha a'zolarga xabar
    all_members = (
        await get_kingdom_members(attacker["id"]) +
        await get_kingdom_members(defender["id"])
    )
    for m in all_members:
        try:
            await bot.send_message(
                m["telegram_id"],
                f"🐦‍⬛ <b>QARG'A XABARI</b>\n\n"
                f"🏳️ {defender['sigil']} <b>{defender['name']}</b> taslim bo'ldi!\n\n"
                f"💰 {gold_transfer} oltin\n"
                f"⚔️ {soldiers_transfer} askar\n"
                f"{attacker['sigil']} <b>{attacker['name']}</b> qo'liga o'tdi!\n\n"
                f"📅 Har shanba tribute: 10%\n"
                f"👑 {defender['name']} Qiroli taxtdan ag'darildi!"
            )
        except Exception:
            pass


# ── Urush qabul qilish ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("war_accept_"))
async def cb_war_accept(call: CallbackQuery, db_user: dict, bot: Bot):
    war_id = int(call.data.split("_")[-1])
    war = await get_war(war_id)
    defender = await get_kingdom(war["defender_id"])

    if not (db_user.get("role") == "king" and defender["king_id"] == call.from_user.id):
        await call.answer("👑 Faqat mudofaa Qiroli!")
        return

    await call.message.edit_text(
        "⚔️ Urush qabul qilindi! Tayyorgarlik davom etmoqda...",
        reply_markup=king_main_kb()
    )
    await bot.send_message(
        call.from_user.id,
        "⚔️ Urushni qabul qildingiz! Vassallaringiz yordam yuborishi mumkin."
    )


# ── Yordam so'rash (boshqa qirollardan) ──────────────────────────────────────

@router.callback_query(F.data.startswith("war_request_help_"))
async def cb_request_help(call: CallbackQuery, db_user: dict, bot: Bot):
    war_id = int(call.data.split("_")[-1])
    war = await get_war(war_id)
    defender = await get_kingdom(war["defender_id"])
    attacker = await get_kingdom(war["attacker_id"])

    kingdoms = await get_all_kingdoms()
    others = [k for k in kingdoms
              if k["id"] not in (war["attacker_id"], war["defender_id"])
              and k["king_id"]]

    if not others:
        await call.answer("❌ Yordam so'rab bo'ladigan qirollik yo'q!", show_alert=True)
        return

    for k in others:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(
                text="⚔️ Askar yuborish",
                callback_data=f"help_soldiers_{war_id}_{defender['id']}"
            ),
            InlineKeyboardButton(
                text="💰 Oltin yuborish",
                callback_data=f"help_gold_{war_id}_{defender['id']}"
            )
        )
        kb.row(InlineKeyboardButton(
            text="❌ Rad etaman", callback_data=f"help_reject_{war_id}"
        ))
        try:
            await bot.send_message(
                k["king_id"],
                f"📨 <b>Yordam so'rovi!</b>\n\n"
                f"{defender['sigil']} <b>{defender['name']}</b> Qiroli\n"
                f"{attacker['sigil']} {attacker['name']} ga qarshi urushda\n"
                f"sizdan yordam so'ramoqda!",
                reply_markup=kb.as_markup()
            )
        except Exception:
            pass

    await call.answer("✅ Yordam so'rovi yuborildi!", show_alert=True)


@router.callback_query(F.data.startswith("help_reject_"))
async def cb_help_reject(call: CallbackQuery):
    await call.message.edit_text("❌ Yordam so'rovi rad etildi.")


@router.callback_query(F.data.startswith("help_soldiers_"))
async def cb_help_soldiers(call: CallbackQuery, db_user: dict, state: FSMContext):
    parts = call.data.split("_")
    war_id, to_kingdom = int(parts[2]), int(parts[3])
    await state.update_data(help_war_id=war_id, help_to_kingdom=to_kingdom,
                             help_type="soldiers")
    await state.set_state(WarStates.waiting_support_soldiers)
    my_kingdom = await get_kingdom_by_king(call.from_user.id)
    await call.message.edit_text(
        f"⚔️ Nechta askar yuborasiz?\n(Sizda: {my_kingdom['soldiers']} askar)",
        reply_markup=back_kb()
    )


@router.callback_query(F.data.startswith("help_gold_"))
async def cb_help_gold(call: CallbackQuery, db_user: dict, state: FSMContext):
    parts = call.data.split("_")
    war_id, to_kingdom = int(parts[2]), int(parts[3])
    await state.update_data(help_war_id=war_id, help_to_kingdom=to_kingdom,
                             help_type="gold")
    await state.set_state(WarStates.waiting_support_gold)
    my_kingdom = await get_kingdom_by_king(call.from_user.id)
    await call.message.edit_text(
        f"💰 Nechta oltin yuborasiz?\n(Sizda: {my_kingdom['gold']} oltin)",
        reply_markup=back_kb()
    )


@router.message(WarStates.waiting_support_soldiers)
async def msg_support_soldiers(message: Message, state: FSMContext, db_user: dict, bot: Bot):
    try:
        amount = int(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Musbat son kiriting.")
        return
    data = await state.get_data()
    my_kingdom = await get_kingdom_by_king(message.from_user.id)
    if my_kingdom["soldiers"] < amount:
        await message.answer(f"❌ Yetarli askar yo'q! Sizda: {my_kingdom['soldiers']}")
        return
    await update_kingdom(my_kingdom["id"], soldiers=my_kingdom["soldiers"] - amount)
    await add_war_support(data["help_war_id"], "kingdom", my_kingdom["id"],
                          data["help_to_kingdom"], soldiers=amount)
    to_k = await get_kingdom(data["help_to_kingdom"])
    await update_kingdom(data["help_to_kingdom"], soldiers=to_k["soldiers"] + amount)
    await state.clear()
    await message.answer(
        f"✅ {amount} askar {to_k['sigil']} {to_k['name']}ga yuborildi!",
        reply_markup=king_main_kb()
    )


@router.message(WarStates.waiting_support_gold)
async def msg_support_gold(message: Message, state: FSMContext, db_user: dict, bot: Bot):
    try:
        amount = int(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Musbat son kiriting.")
        return
    data = await state.get_data()
    my_kingdom = await get_kingdom_by_king(message.from_user.id)
    if my_kingdom["gold"] < amount:
        await message.answer(f"❌ Yetarli oltin yo'q! Sizda: {my_kingdom['gold']}")
        return
    await update_kingdom(my_kingdom["id"], gold=my_kingdom["gold"] - amount)
    await add_war_support(data["help_war_id"], "kingdom", my_kingdom["id"],
                          data["help_to_kingdom"], gold=amount)
    to_k = await get_kingdom(data["help_to_kingdom"])
    await update_kingdom(data["help_to_kingdom"], gold=to_k["gold"] + amount)
    await state.clear()
    await message.answer(
        f"✅ {amount} oltin {to_k['sigil']} {to_k['name']}ga yuborildi!",
        reply_markup=king_main_kb()
    )


# ── Vassaldan yordam ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vassal_war_support_"))
async def cb_vassal_support(call: CallbackQuery, db_user: dict, state: FSMContext):
    war_id = int(call.data.split("_")[-1])
    await state.update_data(vassal_war_id=war_id)
    await state.set_state(WarStates.waiting_support_type)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💰 Oltin", callback_data="vsupport_gold"),
        InlineKeyboardButton(text="⚔️ Askar", callback_data="vsupport_soldiers"),
        InlineKeyboardButton(text="🦂 Chayon", callback_data="vsupport_scorpions"),
    )
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="lord_main"))
    await call.message.edit_text(
        "🛡️ Qirolingizga nima yuborasiz?",
        reply_markup=kb.as_markup()
    )


# ── Urush raundlarini hisoblash ───────────────────────────────────────────────

async def _wait_and_start_war(bot: Bot, war_id: int, delay: float):
    """Kutish va urushni boshlash"""
    await asyncio.sleep(delay)
    war = await get_war(war_id)
    if not war or war["status"] == "finished":
        return
    await _run_war_rounds(bot, war_id)


async def _run_war_rounds(bot: Bot, war_id: int):
    """3 raundli urush"""
    war = await get_war(war_id)
    attacker = await get_kingdom(war["attacker_id"])
    defender = await get_kingdom(war["defender_id"])

    # Boshlang'ich kuchlar (war_support ham hisobga olinadi)
    a_state = await _get_kingdom_forces(attacker, war_id)
    d_state = await _get_kingdom_forces(defender, war_id)

    all_members = (
        await get_kingdom_members(attacker["id"]) +
        await get_kingdom_members(defender["id"])
    )

    await _broadcast(bot, all_members,
        f"🐦‍⬛ <b>QARG'A XABARI — URUSH BOSHLANDI!</b>\n\n"
        f"⚔️ {attacker['sigil']} <b>{attacker['name']}</b> vs "
        f"{defender['sigil']} <b>{defender['name']}</b>\n\n"
        f"📊 Kuchlar:\n"
        f"{attacker['sigil']} {attacker['name']}: "
        f"🐉A×{a_state['da']} B×{a_state['db']} C×{a_state['dc']} "
        f"⚔️{a_state['soldiers']} 🦂{a_state['scorpions']}\n"
        f"{defender['sigil']} {defender['name']}: "
        f"🐉A×{d_state['da']} B×{d_state['db']} C×{d_state['dc']} "
        f"⚔️{d_state['soldiers']} 🦂{d_state['scorpions']}"
    )

    await update_war(war_id, status="round1")
    await asyncio.sleep(5)

    # ── RAUND 1: Chayonlar ajdarlarga ─────────────────────────────────────────
    r1_log = await _round1_scorpions(a_state, d_state, attacker, defender)
    await _broadcast(bot, all_members,
        f"🐦‍⬛ <b>QARG'A XABARI — 1-RAUND</b>\n\n"
        f"🦂 <b>Chayonlar ajdarlarga hujum!</b>\n\n"
        f"{r1_log}\n\n"
        f"📊 Holat:\n"
        f"{attacker['sigil']} {attacker['name']}: "
        f"🐉A×{a_state['da']} B×{a_state['db']} C×{a_state['dc']} ⚔️{a_state['soldiers']}\n"
        f"{defender['sigil']} {defender['name']}: "
        f"🐉A×{d_state['da']} B×{d_state['db']} C×{d_state['dc']} ⚔️{d_state['soldiers']}\n\n"
        f"⏳ 2-raund boshlanmoqda..."
    )

    await update_war(war_id, status="round2")
    await asyncio.sleep(ROUND_DELAY)

    # ── RAUND 2: Ajdarlar + askarlar ──────────────────────────────────────────
    r2_log = await _round2_dragons_soldiers(a_state, d_state, attacker, defender)
    await _broadcast(bot, all_members,
        f"🐦‍⬛ <b>QARG'A XABARI — 2-RAUND</b>\n\n"
        f"🐉 <b>Ajdarlar va askarlar to'qnashdi!</b>\n\n"
        f"{r2_log}\n\n"
        f"📊 Holat:\n"
        f"{attacker['sigil']} {attacker['name']}: "
        f"🐉A×{a_state['da']} B×{a_state['db']} C×{a_state['dc']} ⚔️{a_state['soldiers']}\n"
        f"{defender['sigil']} {defender['name']}: "
        f"🐉A×{d_state['da']} B×{d_state['db']} C×{d_state['dc']} ⚔️{d_state['soldiers']}\n\n"
        f"⏳ Yakuniy raund boshlanmoqda..."
    )

    await update_war(war_id, status="round3")
    await asyncio.sleep(ROUND_DELAY)

    # ── RAUND 3: Yakuniy jang ─────────────────────────────────────────────────
    r3_log, a_power, d_power = await _round3_final(a_state, d_state)

    # G'olib aniqlash (DB dan yangi ma'lumot)
    attacker = await get_kingdom(war["attacker_id"])
    defender = await get_kingdom(war["defender_id"])
    if a_power > d_power:
        winner, loser = attacker, defender
        winner_state, loser_state = a_state, d_state
    elif d_power > a_power:
        winner, loser = defender, attacker
        winner_state, loser_state = d_state, a_state
    else:
        # Teng kuch — hujumchi yutqazadi
        winner, loser = defender, attacker
        winner_state, loser_state = d_state, a_state

    # Resurs o'tkazish
    gold_transfer = loser["gold"] // 2
    soldiers_transfer = loser["soldiers"] // 2
    await update_kingdom(winner["id"],
        gold=winner["gold"] + gold_transfer,
        soldiers=winner["soldiers"] + soldiers_transfer
    )
    await update_kingdom(loser["id"],
        gold=loser["gold"] - gold_transfer,
        soldiers=loser["soldiers"] - soldiers_transfer
    )

    # Yutqazgan Qirolni ag'darish
    loser_fresh = await get_kingdom(loser["id"])
    if loser_fresh and loser_fresh["king_id"]:
        from database.queries import update_user
        await update_user(loser_fresh["king_id"], role="member")
        await update_kingdom(loser["id"], king_id=None)

    await update_war(war_id, status="finished",
                     winner_id=winner["id"],
                     finished_at=datetime.utcnow())

    # Yakuniy xabar
    await _broadcast(bot, all_members,
        f"🐦‍⬛ <b>QARG'A XABARI — URUSH YAKUNI!</b>\n\n"
        f"{r3_log}\n\n"
        f"{'🏆' if a_power >= d_power else '🏆'} "
        f"<b>{winner['sigil']} {winner['name']} G'ALABA QOZINDI!</b>\n\n"
        f"💰 {gold_transfer} oltin\n"
        f"⚔️ {soldiers_transfer} askar\n"
        f"{winner['sigil']} {winner['name']}ga o'tkazildi!\n\n"
        f"👑 {loser['name']} Qiroli taxtdan ag'darildi!\n"
        f"📜 Bu voqea tarixga kirdi..."
    )

    await add_chronicle(
        "war_end", f"⚔️ Urush yakuni!",
        f"🏆 {winner['name']} g'alaba! {loser['name']} yutqazdi. "
        f"{gold_transfer}💰 + {soldiers_transfer}⚔️ o'tkazildi.",
        bot=bot
    )


async def _get_kingdom_forces(kingdom: dict, war_id: int = None) -> dict:
    """Qirollikning barcha kuchlarini hisoblash (war_support ham qo'shiladi)"""
    # Qirollik artefaktlari
    arts = await get_artifacts("kingdom", kingdom["id"])
    da = db = dc = scorpions = 0
    for a in arts:
        if a["artifact"] == "🐉 Ajdar":
            if a["tier"] == "A": da += 1
            elif a["tier"] == "B": db += 1
            elif a["tier"] == "C": dc += 1
        elif "Chayon" in a["artifact"]:
            scorpions += 1

    # Vassal artefaktlarini ham hisoblash
    vassals = await get_kingdom_vassals(kingdom["id"])
    for v in vassals:
        v_arts = await get_artifacts("vassal", v["id"])
        for a in v_arts:
            if a["artifact"] == "🐉 Ajdar":
                if a["tier"] == "A": da += 1
                elif a["tier"] == "B": db += 1
                elif a["tier"] == "C": dc += 1
            elif "Chayon" in a["artifact"]:
                scorpions += 1

    soldiers = kingdom["soldiers"]

    # War support dan qo'shimcha resurslar
    if war_id:
        support = await get_war_support(war_id, kingdom["id"])
        if support:
            soldiers += support["total_soldiers"] or 0
            scorpions += support["total_scorpions"] or 0

    return {
        "da": da, "db": db, "dc": dc,
        "soldiers": soldiers,
        "scorpions": scorpions,
        "skipped_a": 0,
    }


async def _round1_scorpions(a: dict, d: dict, ak: dict, dk: dict) -> str:
    """Raund 1: Chayonlar ajdarlarga"""
    log = []

    # Hujumchi chayonlari mudofaa ajdarlariga
    _apply_scorpions(a, d, ak["sigil"], dk["sigil"], log)
    # Mudofaa chayonlari hujumchi ajdarlariga
    _apply_scorpions(d, a, dk["sigil"], ak["sigil"], log)

    return "\n".join(log) if log else "🦂 Chayonlar harakat qilmadi"


def _apply_scorpions(attacker: dict, defender: dict,
                     a_sigil: str, d_sigil: str, log: list):
    sc = attacker["scorpions"]
    if sc <= 0:
        return

    # Ajdar A ga qarshi
    while sc >= SCORPION_KILL_A and defender["da"] > 0:
        defender["da"] -= 1
        sc -= SCORPION_KILL_A
        attacker["scorpions"] -= SCORPION_KILL_A
        log.append(f"🦂 {a_sigil} 3 chayon → {d_sigil} Ajdar A ni o'ldirdi!")

    while sc >= SCORPION_SKIP_A and defender["da"] > 0:
        defender["skipped_a"] += 1
        sc -= SCORPION_SKIP_A
        attacker["scorpions"] -= SCORPION_SKIP_A
        log.append(f"🦂 {a_sigil} 2 chayon → {d_sigil} Ajdar A ni 1 raund o'tkazib yuboradi!")

    # Ajdar C ga qarshi
    while sc >= SCORPION_KILL_C and defender["dc"] > 0:
        defender["dc"] -= 1
        sc -= SCORPION_KILL_C
        attacker["scorpions"] -= SCORPION_KILL_C
        log.append(f"🦂 {a_sigil} 1 chayon → {d_sigil} Ajdar C ni o'ldirdi!")


async def _round2_dragons_soldiers(a: dict, d: dict,
                                    ak: dict, dk: dict) -> str:
    log = []

    # Ajdar A (skip bo'lmaganlar)
    a_da_active = max(0, a["da"] - a["skipped_a"])
    d_da_active = max(0, d["da"] - d["skipped_a"])

    # Hujumchi ajdarlari
    if a_da_active > 0:
        dmg = a_da_active * DRAGON_A_POWER
        d["soldiers"] = max(0, d["soldiers"] - dmg)
        log.append(f"🐉 {ak['sigil']} {a_da_active}×Ajdar A → {dk['sigil']} {dmg} askar halok!")
    if a["db"] > 0:
        dmg = a["db"] * DRAGON_B_POWER
        d["soldiers"] = max(0, d["soldiers"] - dmg)
        log.append(f"🐉 {ak['sigil']} {a['db']}×Ajdar B → {dk['sigil']} {dmg} askar halok!")
    if a["dc"] > 0:
        dmg = a["dc"] * DRAGON_C_POWER
        d["soldiers"] = max(0, d["soldiers"] - dmg)
        log.append(f"🐉 {ak['sigil']} {a['dc']}×Ajdar C → {dk['sigil']} {dmg} askar halok!")

    # Mudofaa ajdarlari
    if d_da_active > 0:
        dmg = d_da_active * DRAGON_A_POWER
        a["soldiers"] = max(0, a["soldiers"] - dmg)
        log.append(f"🐉 {dk['sigil']} {d_da_active}×Ajdar A → {ak['sigil']} {dmg} askar halok!")
    if d["db"] > 0:
        dmg = d["db"] * DRAGON_B_POWER
        a["soldiers"] = max(0, a["soldiers"] - dmg)
        log.append(f"🐉 {dk['sigil']} {d['db']}×Ajdar B → {ak['sigil']} {dmg} askar halok!")
    if d["dc"] > 0:
        dmg = d["dc"] * DRAGON_C_POWER
        a["soldiers"] = max(0, a["soldiers"] - dmg)
        log.append(f"🐉 {dk['sigil']} {d['dc']}×Ajdar C → {ak['sigil']} {dmg} askar halok!")

    # Skip bo'lganlar keyingi raundga
    a["skipped_a"] = 0
    d["skipped_a"] = 0

    return "\n".join(log) if log else "🐉 Ajdarlar hujum qilmadi"


async def _round3_final(a: dict, d: dict) -> tuple:
    """Yakuniy kuch hisoblash"""
    log = []

    a_power = (
        a["da"] * DRAGON_A_POWER +
        a["db"] * DRAGON_B_POWER +
        a["dc"] * DRAGON_C_POWER +
        a["soldiers"]
    )
    d_power = (
        d["da"] * DRAGON_A_POWER +
        d["db"] * DRAGON_B_POWER +
        d["dc"] * DRAGON_C_POWER +
        d["soldiers"]
    )

    log.append(f"⚔️ Yakuniy kuchlar:")
    log.append(f"Hujumchi: {a_power} kuch")
    log.append(f"Mudofaa: {d_power} kuch")

    return "\n".join(log), a_power, d_power


async def _broadcast(bot: Bot, members: list, text: str):
    """Barcha a'zolarga xabar yuborish"""
    sent_ids = set()
    for m in members:
        uid = m["telegram_id"]
        if uid in sent_ids:
            continue
        sent_ids.add(uid)
        try:
            await bot.send_message(uid, text)
        except Exception:
            pass


# ── Haftalik tribute (scheduler tomonidan chaqiriladi) ───────────────────────

async def process_weekly_tributes(bot: Bot):
    """Har shanba ishga tushadi"""
    tributes = await get_active_tributes()
    for t in tributes:
        loser = await get_kingdom(t["from_kingdom"])
        winner = await get_kingdom(t["to_kingdom"])
        if not loser or not winner:
            continue
        tribute_gold = loser["gold"] * t["percent"] // 100
        tribute_soldiers = loser["soldiers"] * t["percent"] // 100
        if tribute_gold <= 0 and tribute_soldiers <= 0:
            continue
        await update_kingdom(loser["id"],
            gold=loser["gold"] - tribute_gold,
            soldiers=loser["soldiers"] - tribute_soldiers
        )
        await update_kingdom(winner["id"],
            gold=winner["gold"] + tribute_gold,
            soldiers=winner["soldiers"] + tribute_soldiers
        )
        members = (
            await get_kingdom_members(loser["id"]) +
            await get_kingdom_members(winner["id"])
        )
        await _broadcast(bot, members,
            f"🐦‍⬛ <b>QARG'A XABARI — HAFTALIK TRIBUTE</b>\n\n"
            f"{loser['sigil']} <b>{loser['name']}</b> →\n"
            f"{winner['sigil']} <b>{winner['name']}</b>\n\n"
            f"💰 {tribute_gold} oltin\n"
            f"⚔️ {tribute_soldiers} askar tribute sifatida o'tkazildi!"
        )
        await add_chronicle(
            "tribute", "Haftalik tribute",
            f"{loser['name']} → {winner['name']}: "
            f"{tribute_gold}💰 + {tribute_soldiers}⚔️"
        )


# ── Urush holati (Qirol paneli) ───────────────────────────────────────────────

@router.callback_query(F.data == "king_war_status")
async def cb_king_war_status(call: CallbackQuery, db_user: dict):
    if db_user.get("role") != "king":
        await call.answer("👑 Faqat Qirollar uchun!")
        return
    kingdom = await get_kingdom_by_king(call.from_user.id)
    war = await get_active_war(kingdom["id"])
    if not war:
        await call.message.edit_text(
            "☮️ Hozircha faol urush yo'q.",
            reply_markup=back_kb("king_main")
        )
        return
    attacker = await get_kingdom(war["attacker_id"])
    defender = await get_kingdom(war["defender_id"])
    is_attacker = war["attacker_id"] == kingdom["id"]
    enemy = defender if is_attacker else attacker

    from datetime import timezone
    starts_at = war["starts_at"]
    if starts_at:
        starts_uz = starts_at + timedelta(hours=5)
        time_text = starts_uz.strftime("%d.%m %H:%M")
    else:
        time_text = "?"

    status_labels = {
        "pending": "⏳ Kutilmoqda",
        "round1": "⚔️ 1-Raund",
        "round2": "⚔️ 2-Raund",
        "round3": "⚔️ 3-Raund",
        "finished": "✅ Tugagan"
    }

    text = (
        f"⚔️ <b>Urush Holati</b>\n\n"
        f"{'🗡️ Hujum' if is_attacker else '🛡️ Mudofaa'}\n"
        f"Dushman: {enemy['sigil']} <b>{enemy['name']}</b>\n"
        f"Holat: {status_labels.get(war['status'], war['status'])}\n"
        f"Boshlanish: {time_text}\n\n"
    )

    support = await get_war_support(war["id"], kingdom["id"])
    if support:
        text += (
            f"📦 Kelgan yordam:\n"
            f"💰 {support['total_gold']} oltin\n"
            f"⚔️ {support['total_soldiers']} askar\n"
            f"🦂 {support['total_scorpions']} chayon"
        )

    builder = InlineKeyboardBuilder()
    if war["status"] == "pending" and not is_attacker:
        builder.row(
            InlineKeyboardButton(text="⚔️ Qabul qilish", callback_data=f"war_accept_{war['id']}"),
            InlineKeyboardButton(text="🏳️ Taslim bo'lish", callback_data=f"war_surrender_{war['id']}")
        )
        builder.row(InlineKeyboardButton(
            text="📨 Yordam so'rash",
            callback_data=f"war_request_help_{war['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_main"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


# ── Lord urushga yordam (vassal paneli) ───────────────────────────────────────

@router.callback_query(F.data == "lord_war_support")
async def cb_lord_war_support(call: CallbackQuery, db_user: dict):
    if db_user.get("role") != "lord":
        await call.answer("🛡️ Faqat Lordlar uchun!")
        return
    from database.queries import get_vassal_by_lord
    vassal = await get_vassal_by_lord(call.from_user.id)
    if not vassal:
        await call.answer("❌ Vassal topilmadi!")
        return
    war = await get_active_war(vassal["kingdom_id"])
    if not war:
        await call.message.edit_text(
            "☮️ Hozircha faol urush yo'q.",
            reply_markup=back_kb("lord_main")
        )
        return

    kingdom = await get_kingdom(vassal["kingdom_id"])
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Oltin yuborish", callback_data=f"vsupport_gold_{war['id']}"),
        InlineKeyboardButton(text="⚔️ Askar yuborish", callback_data=f"vsupport_soldiers_{war['id']}"),
    )
    builder.row(InlineKeyboardButton(
        text="🦂 Chayon yuborish",
        callback_data=f"vsupport_scorpions_{war['id']}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="lord_main"))

    attacker = await get_kingdom(war["attacker_id"])
    defender = await get_kingdom(war["defender_id"])
    enemy = defender if war["attacker_id"] == vassal["kingdom_id"] else attacker

    await call.message.edit_text(
        f"⚔️ <b>{kingdom['sigil']} {kingdom['name']}</b> urushda!\n\n"
        f"Dushman: {enemy['sigil']} <b>{enemy['name']}</b>\n\n"
        f"🛡️ Oilangiz resurslari:\n"
        f"💰 {vassal['gold']} oltin | ⚔️ {vassal['soldiers']} askar\n\n"
        f"Nima yuborasiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("vsupport_gold_"))
async def cb_vsupport_gold(call: CallbackQuery, state: FSMContext, db_user: dict):
    war_id = int(call.data.split("_")[-1])
    from database.queries import get_vassal_by_lord
    vassal = await get_vassal_by_lord(call.from_user.id)
    await state.update_data(
        vassal_war_id=war_id,
        vassal_id=vassal["id"],
        vsupport_type="gold",
        kingdom_id=vassal["kingdom_id"]
    )
    await state.set_state(WarStates.waiting_support_gold)
    await call.message.edit_text(
        f"💰 Nechta oltin yuborasiz?\n(Oilada: {vassal['gold']} oltin)",
        reply_markup=back_kb("lord_war_support")
    )


@router.callback_query(F.data.startswith("vsupport_soldiers_"))
async def cb_vsupport_soldiers(call: CallbackQuery, state: FSMContext, db_user: dict):
    war_id = int(call.data.split("_")[-1])
    from database.queries import get_vassal_by_lord
    vassal = await get_vassal_by_lord(call.from_user.id)
    await state.update_data(
        vassal_war_id=war_id,
        vassal_id=vassal["id"],
        vsupport_type="soldiers",
        kingdom_id=vassal["kingdom_id"]
    )
    await state.set_state(WarStates.waiting_support_soldiers)
    await call.message.edit_text(
        f"⚔️ Nechta askar yuborasiz?\n(Oilada: {vassal['soldiers']} askar)",
        reply_markup=back_kb("lord_war_support")
    )


@router.callback_query(F.data.startswith("vsupport_scorpions_"))
async def cb_vsupport_scorpions(call: CallbackQuery, state: FSMContext, db_user: dict):
    war_id = int(call.data.split("_")[-1])
    from database.queries import get_vassal_by_lord
    vassal = await get_vassal_by_lord(call.from_user.id)
    # Chayonlarni artefaktlardan hisoblash
    arts = await get_artifacts("vassal", vassal["id"])
    scorpions = sum(1 for a in arts if "Chayon" in a["artifact"])
    await state.update_data(
        vassal_war_id=war_id,
        vassal_id=vassal["id"],
        vsupport_type="scorpions",
        kingdom_id=vassal["kingdom_id"],
        max_scorpions=scorpions
    )
    await state.set_state(WarStates.waiting_support_scorpions)
    await call.message.edit_text(
        f"🦂 Nechta chayon yuborasiz?\n(Oilada: {scorpions} chayon)",
        reply_markup=back_kb("lord_war_support")
    )


@router.message(WarStates.waiting_support_scorpions)
async def msg_vassal_scorpions(message: Message, state: FSMContext, db_user: dict):
    try:
        amount = int(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("❌ Musbat son kiriting.")
        return
    data = await state.get_data()
    max_sc = data.get("max_scorpions", 0)
    if amount > max_sc:
        await message.answer(f"❌ Yetarli chayon yo'q! Sizda: {max_sc}")
        return
    kingdom = await get_kingdom(data["kingdom_id"])
    await add_war_support(
        data["vassal_war_id"], "vassal", data["vassal_id"],
        data["kingdom_id"], scorpions=amount
    )
    await state.clear()
    from keyboards.kb import lord_main_kb
    await message.answer(
        f"✅ {amount} ta 🦂 chayon {kingdom['sigil']} {kingdom['name']}ga yuborildi!",
        reply_markup=lord_main_kb()
    )
