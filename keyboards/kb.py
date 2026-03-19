"""
Keyboard builders for all roles
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── Admin keyboards ───────────────────────────────────────────────────────────

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏰 Standart 7 qirollik yaratish", callback_data="admin_create_kingdoms"))
    builder.row(InlineKeyboardButton(text="⚙️ Qirolliklar boshqaruvi", callback_data="admin_manage_kingdoms"))
    builder.row(InlineKeyboardButton(text="👑 Qirol tayinlash", callback_data="admin_assign_king"))
    builder.row(InlineKeyboardButton(text="🛡️ Vassal oila qo'shish", callback_data="admin_add_vassal"))
    builder.row(InlineKeyboardButton(text="🗑️ Vassal oila o'chirish", callback_data="admin_delete_house"))
    builder.row(InlineKeyboardButton(text="📜 Xronikaga yozish", callback_data="admin_write_chronicle"))
    builder.row(InlineKeyboardButton(text="📊 O'yin holati", callback_data="admin_game_status"))
    builder.row(InlineKeyboardButton(text="🔀 A'zoni ko'chirish", callback_data="admin_move_user"))
    builder.row(InlineKeyboardButton(text="📜 Xronika", callback_data="view_chronicles"))
    builder.row(InlineKeyboardButton(text="🏆 Global Reyting", callback_data="global_rating"))
    builder.row(InlineKeyboardButton(text="🏦 Temir Bank boshqaruvi", callback_data="admin_iron_bank"))
    builder.row(InlineKeyboardButton(text="⏸️ O'yinni to'xtatish", callback_data="admin_pause_game"))
    return builder.as_markup()


def admin_kingdoms_kb(kingdoms) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']}",
            callback_data=f"admin_kingdom_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    return builder.as_markup()


def admin_vassal_kingdom_kb(kingdoms) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']}",
            callback_data=f"admin_vassal_kingdom_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_main"))
    return builder.as_markup()


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_{action}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel")
    )
    return builder.as_markup()


# ── King keyboards ────────────────────────────────────────────────────────────

def king_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📣 Farmon chiqarish", callback_data="king_decree"))
    builder.row(InlineKeyboardButton(text="💰 Resurs talab qilish", callback_data="king_request_resources"))
    builder.row(InlineKeyboardButton(text="⚔️ Jazo berish", callback_data="king_punish"))
    builder.row(InlineKeyboardButton(text="🤝 Diplomatiya", callback_data="king_diplomacy"))
    builder.row(InlineKeyboardButton(text="📊 Qirollik holati", callback_data="king_status"))
    builder.row(InlineKeyboardButton(text="⚔️ Urush holati", callback_data="king_war_status"))
    builder.row(InlineKeyboardButton(text="🗡️ Suiqasd (Fitna)", callback_data="assassination"))
    builder.row(InlineKeyboardButton(text="🏆 Global Reyting", callback_data="global_rating"))
    builder.row(InlineKeyboardButton(text="📜 Xronika", callback_data="view_chronicles"))
    builder.row(InlineKeyboardButton(text="🏪 Iron Bank", callback_data="market_main"))
    return builder.as_markup()


def diplomacy_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Urush e'lon qilish", callback_data="king_declare_war"))
    builder.row(InlineKeyboardButton(text="🤝 Ittifoq taklifi", callback_data="king_alliance"))
    builder.row(InlineKeyboardButton(text="📨 Kelgan takliflar", callback_data="king_pending_offers"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_main"))
    return builder.as_markup()


def kingdoms_select_kb(kingdoms, callback_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for k in kingdoms:
        builder.row(InlineKeyboardButton(
            text=f"{k['sigil']} {k['name']}",
            callback_data=f"{callback_prefix}_{k['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_main"))
    return builder.as_markup()


def resource_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Oltin", callback_data="resource_gold"),
        InlineKeyboardButton(text="⚔️ Qo'shin", callback_data="resource_soldiers")
    )
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="king_main"))
    return builder.as_markup()


def vassals_select_kb(vassals, callback_prefix: str, back_cb: str = "king_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vassals:
        lord_mark = "👑 " if v["lord_id"] else ""
        builder.row(InlineKeyboardButton(
            text=f"{lord_mark}{v['name']}",
            callback_data=f"{callback_prefix}_{v['id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data=back_cb))
    return builder.as_markup()


def diplomacy_respond_kb(diplomacy_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Qabul", callback_data=f"diplo_accept_{diplomacy_id}"),
        InlineKeyboardButton(text="❌ Rad", callback_data=f"diplo_reject_{diplomacy_id}")
    )
    return builder.as_markup()


# ── Lord keyboards ────────────────────────────────────────────────────────────

def lord_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Qirol buyruqlari", callback_data="lord_orders"))
    builder.row(InlineKeyboardButton(text="🏠 Oila holati", callback_data="lord_family_status"))
    builder.row(InlineKeyboardButton(text="🗳️ Saylov o'tkazish", callback_data="lord_election"))
    builder.row(InlineKeyboardButton(text="🚀 Panoh so'rash", callback_data="lord_defect"))
    builder.row(InlineKeyboardButton(text="⚔️ Urushga yordam", callback_data="lord_war_support"))
    builder.row(InlineKeyboardButton(text="🗡️ Suiqasd (Fitna)", callback_data="assassination"))
    builder.row(InlineKeyboardButton(text="🏆 Global Reyting", callback_data="global_rating"))
    builder.row(InlineKeyboardButton(text="📜 Xronika", callback_data="view_chronicles"))
    builder.row(InlineKeyboardButton(text="🏪 Iron Bank", callback_data="market_main"))
    return builder.as_markup()


def order_respond_kb(order_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Bajaraman", callback_data=f"order_accept_{order_type}"),
        InlineKeyboardButton(text="❌ Rad etaman", callback_data=f"order_reject_{order_type}")
    )
    return builder.as_markup()


# ── Member keyboards ──────────────────────────────────────────────────────────

def member_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⛏️ Kunlik Farm", callback_data="daily_farm"))
    builder.row(InlineKeyboardButton(text="📜 Xronika", callback_data="view_chronicles"))
    builder.row(InlineKeyboardButton(text="🗳️ Ovoz berish", callback_data="vote_lord"))
    builder.row(InlineKeyboardButton(text="📊 Mening holatim", callback_data="my_status"))
    builder.row(InlineKeyboardButton(text="🏆 Global Reyting", callback_data="global_rating"))
    builder.row(InlineKeyboardButton(text="🏪 Iron Bank", callback_data="market_main"))
    return builder.as_markup()


# ── Market keyboards ──────────────────────────────────────────────────────────

def market_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🐉 Ajdar A (150💰)", callback_data="buy_dragon_a"),
        InlineKeyboardButton(text="🐉 Ajdar B (100💰)", callback_data="buy_dragon_b"),
        InlineKeyboardButton(text="🐉 Ajdar C (60💰)", callback_data="buy_dragon_c"),
    )
    builder.row(InlineKeyboardButton(text="🦂 Chayon (25💰)", callback_data="buy_scorpion"))
    builder.row(InlineKeyboardButton(text="💱 Oltin→Qo'shin", callback_data="exchange_gold"))
    builder.row(InlineKeyboardButton(text="🗡️ Suiqasd (Fitna)", callback_data="assassination"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="main_menu"))
    return builder.as_markup()


# ── Common keyboards ──────────────────────────────────────────────────────────

def back_kb(callback: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data=callback))
    return builder.as_markup()


def candidates_kb(candidates, vassal_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in candidates:
        name = c.get("full_name") or c.get("username") or str(c["telegram_id"])
        builder.row(InlineKeyboardButton(
            text=f"👤 {name}",
            callback_data=f"vote_{vassal_id}_{c['telegram_id']}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="main_menu"))
    return builder.as_markup()


def dynamic_market_kb(prices: dict) -> InlineKeyboardMarkup:
    """Narxlar DB dan keladi — admin o'zgartirsa yangilanadi"""
    builder = InlineKeyboardBuilder()
    items = {
        "dragon_a":  "buy_dragon_a",
        "dragon_b":  "buy_dragon_b",
        "dragon_c":  "buy_dragon_c",
        "scorpion":  "buy_scorpion",
    }
    for item, cb in items.items():
        info = prices.get(item, {})
        label = info.get("label", item)
        price = info.get("price", "?")
        builder.row(InlineKeyboardButton(
            text=f"{label} ({price}💰)",
            callback_data=cb
        ))
    builder.row(InlineKeyboardButton(text="💱 Oltin→Qo\'shin", callback_data="exchange_gold"))
    builder.row(InlineKeyboardButton(text="🗡️ Suiqasd (Fitna)", callback_data="assassination"))
    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="main_menu"))
    return builder.as_markup()
