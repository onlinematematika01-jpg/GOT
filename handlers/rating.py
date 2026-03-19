"""
Global Reyting tizimi
Qirolliklar va Vassallar bitta umumiy ro'yxatda
Ko'rsatkichlar: Oltin, Qo'shin, Ajdar, Umumiy kuch, Urush g'alabalari
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.queries import (
    get_all_kingdoms, get_all_vassals, get_artifacts, get_kingdom_vassals
)
from keyboards.kb import back_kb

router = Router()

# Kuch koeffitsientlari
DRAGON_A_POWER = 100
DRAGON_B_POWER = 50
DRAGON_C_POWER = 25
GOLD_POWER     = 0.1   # 10 oltin = 1 kuch
SOLDIER_POWER  = 1     # 1 askar = 1 kuch

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def rating_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Umumiy kuch", callback_data="rating_power"))
    builder.row(
        InlineKeyboardButton(text="💰 Oltin", callback_data="rating_gold"),
        InlineKeyboardButton(text="⚔️ Qo'shin", callback_data="rating_soldiers"),
    )
    builder.row(
        InlineKeyboardButton(text="🐉 Ajdarlar", callback_data="rating_dragons"),
        InlineKeyboardButton(text="🏆 G'alabalar", callback_data="rating_wins"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="main_menu"))
    return builder.as_markup()


async def _collect_all_entities():
    """Barcha qirolliklar va vassallar ma'lumotlarini yig'ish"""
    entities = []

    # Qirolliklar
    kingdoms = await get_all_kingdoms()
    for k in kingdoms:
        arts = await get_artifacts("kingdom", k["id"])

        # Vassal artefaktlarini ham qo'shish
        vassals = await get_kingdom_vassals(k["id"])
        vassal_arts = []
        for v in vassals:
            vassal_arts += await get_artifacts("vassal", v["id"])

        all_arts = list(arts) + vassal_arts
        da = sum(1 for a in all_arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "A")
        db = sum(1 for a in all_arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "B")
        dc = sum(1 for a in all_arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "C")
        total_dragons = da + db + dc
        dragon_power = da * DRAGON_A_POWER + db * DRAGON_B_POWER + dc * DRAGON_C_POWER
        total_power = int(
            k["gold"] * GOLD_POWER +
            k["soldiers"] * SOLDIER_POWER +
            dragon_power
        )

        entities.append({
            "type": "kingdom",
            "name": f"{k['sigil']} {k['name']}",
            "gold": k["gold"],
            "soldiers": k["soldiers"],
            "dragons": total_dragons,
            "dragon_power": dragon_power,
            "power": total_power,
            "wins": 0,  # Quyida hisoblanadi
            "id": k["id"],
        })

    # Vassallar
    vassals = await get_all_vassals()
    for v in vassals:
        arts = await get_artifacts("vassal", v["id"])
        da = sum(1 for a in arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "A")
        db = sum(1 for a in arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "B")
        dc = sum(1 for a in arts if a["artifact"] == "🐉 Ajdar" and a["tier"] == "C")
        total_dragons = da + db + dc
        dragon_power = da * DRAGON_A_POWER + db * DRAGON_B_POWER + dc * DRAGON_C_POWER
        total_power = int(
            v["gold"] * GOLD_POWER +
            v["soldiers"] * SOLDIER_POWER +
            dragon_power
        )

        entities.append({
            "type": "vassal",
            "name": f"🛡️ {v['name']}",
            "gold": v["gold"],
            "soldiers": v["soldiers"],
            "dragons": total_dragons,
            "dragon_power": dragon_power,
            "power": total_power,
            "wins": 0,
            "id": v["id"],
        })

    # Urush g'alabalarini hisoblash
    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        wins_rows = await conn.fetch(
            """SELECT winner_id, COUNT(*) as wins
               FROM wars WHERE status='finished' AND winner_id IS NOT NULL
               GROUP BY winner_id"""
        )
    wins_map = {r["winner_id"]: r["wins"] for r in wins_rows}
    for e in entities:
        if e["type"] == "kingdom":
            e["wins"] = wins_map.get(e["id"], 0)

    return entities


def _build_rating_text(entities: list, sort_key: str, label: str, emoji: str) -> str:
    sorted_list = sorted(entities, key=lambda x: x[sort_key], reverse=True)
    text = f"{emoji} <b>GLOBAL REYTING — {label}</b>\n\n"
    for i, e in enumerate(sorted_list[:20], 1):
        medal = MEDALS.get(i, f"{i}.")
        type_mark = "🏰" if e["type"] == "kingdom" else "🛡️"
        value = e[sort_key]
        text += f"{medal} {e['name']}\n"
        text += f"   {emoji} {value:,}\n"
    return text


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "global_rating")
async def cb_rating_main(call: CallbackQuery):
    await call.message.edit_text(
        "🏆 <b>GLOBAL REYTING</b>\n\n"
        "Qirolliklar va Vassallar umumiy reytingda!\n"
        "Ko'rsatkichni tanlang:",
        reply_markup=rating_kb()
    )


@router.callback_query(F.data == "rating_power")
async def cb_rating_power(call: CallbackQuery):
    await call.answer("⏳ Hisoblanmoqda...")
    entities = await _collect_all_entities()
    text = _build_rating_text(entities, "power", "UMUMIY KUCH", "⚡")
    text += (
        "\n<i>Hisoblash: 💰×0.1 + ⚔️×1 + 🐉A×100 + 🐉B×50 + 🐉C×25</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "rating_gold")
async def cb_rating_gold(call: CallbackQuery):
    await call.answer("⏳ Hisoblanmoqda...")
    entities = await _collect_all_entities()
    text = _build_rating_text(entities, "gold", "OLTIN", "💰")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "rating_soldiers")
async def cb_rating_soldiers(call: CallbackQuery):
    await call.answer("⏳ Hisoblanmoqda...")
    entities = await _collect_all_entities()
    text = _build_rating_text(entities, "soldiers", "QO'SHIN", "⚔️")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "rating_dragons")
async def cb_rating_dragons(call: CallbackQuery):
    await call.answer("⏳ Hisoblanmoqda...")
    entities = await _collect_all_entities()
    text = _build_rating_text(entities, "dragons", "AJDARLAR", "🐉")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "rating_wins")
async def cb_rating_wins(call: CallbackQuery):
    await call.answer("⏳ Hisoblanmoqda...")
    entities = await _collect_all_entities()
    # Faqat g'alabasi borlarni ko'rsatish
    winners = [e for e in entities if e["wins"] > 0]
    if not winners:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
        await call.message.edit_text(
            "🏆 <b>G'ALABALAR REYTINGI</b>\n\n"
            "Hali hech qanday urush tugamagan.",
            reply_markup=builder.as_markup()
        )
        return
    text = _build_rating_text(winners, "wins", "G'ALABALAR", "🏆")
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="global_rating"))
    await call.message.edit_text(text, reply_markup=builder.as_markup())
