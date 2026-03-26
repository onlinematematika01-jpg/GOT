"""
Suiqasd (Fitna) tizimi — to'liq qayta yozilgan

Qoidalar:
  Lord:         3 ta ketma-ket muvaffaqiyatli suiqasd → o'ladi
  Qirol:        15 ta suiqasd  YOKI  5 ta Lord suiqasdidan → o'ladi
  Targaryen:    3 ta Qirol     YOKI  50 ta Lord suiqasdidan → o'ladi

  Muvaffaqiyatsiz → xronikada SUIQASDCHI ISMI oshkor bo'ladi
  Muvaffaqiyatli  → xronikada faqat "Qirol" yoki "Lord" lavozimi ko'rinadi
  Random tizim yo'q — har bir suiqasd hisoblanadi
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.queries import (
    get_user, update_user, get_vassal, get_vassal_by_lord,
    get_kingdom_by_king, get_kingdom, update_kingdom, update_vassal,
    add_chronicle, get_all_lords, get_all_kings,
    add_assassination_hit, count_assassination_hits,
    count_lord_hits, count_king_hits, get_assassination_attackers,
    reset_assassination_hits, has_assassinated_today
)
from keyboards.kb import back_kb, member_main_kb

router = Router()

# ── Thresholds ────────────────────────────────────────────────────────────────
LORD_DEATH_HITS       = 3    # Lord o'lish uchun ketma-ket suiqasd soni
KING_DEATH_HITS       = 15   # Qirol o'lish uchun umumiy suiqasd
KING_LORD_HITS        = 5    # Qirol o'lish uchun Lord suiqasd soni
TARGARYEN_KING_HITS   = 3    # Targaryen o'lish uchun Qirol suiqasd
TARGARYEN_LORD_HITS   = 50   # Targaryen o'lish uchun Lord suiqasd

TARGARYEN_KINGDOM = "Targaryen"


# ═════════════════════════════════════════════════════════════════════════════
#  SUIQASD MENYUSI
# ═════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "assassination")
async def cb_assassination_menu(call: CallbackQuery, db_user: dict):
    role               = db_user.get("role", "member")
    attacker_id        = call.from_user.id
    attacker_kingdom   = db_user.get("kingdom_id")
    attacker_vassal    = db_user.get("vassal_id")

    lords = await get_all_lords()
    kings = await get_all_kings()
    targets = []

    if role == "member":
        # Member → faqat O'Z Lord va Qiroli
        for l in lords:
            if l.get("vassal_id") == attacker_vassal and l["telegram_id"] != attacker_id:
                targets.append(("lord", l))
        for k in kings:
            if k.get("kingdom_id") == attacker_kingdom and k["telegram_id"] != attacker_id:
                targets.append(("king", k))

    elif role == "lord":
        # Lord → o'z Qiroli + boshqa qirollik Lord va Qirollari
        for k in kings:
            if k.get("kingdom_id") == attacker_kingdom and k["telegram_id"] != attacker_id:
                targets.append(("king", k))
        for l in lords:
            if l.get("kingdom_id") != attacker_kingdom and l["telegram_id"] != attacker_id:
                targets.append(("lord", l))
        for k in kings:
            if k.get("kingdom_id") != attacker_kingdom and k["telegram_id"] != attacker_id:
                targets.append(("king", k))

    elif role == "king":
        # King → o'z qirolligidagi HAMMA + boshqa qirollik Lord va Qirollari
        from database.queries import get_kingdom_members
        own_members = await get_kingdom_members(attacker_kingdom)
        for m in own_members:
            if m["telegram_id"] == attacker_id:
                continue
            if m["role"] in ("lord", "king", "member"):
                targets.append((m["role"], dict(m)))
        for l in lords:
            if l.get("kingdom_id") != attacker_kingdom and l["telegram_id"] != attacker_id:
                targets.append(("lord", l))
        for k in kings:
            if k.get("kingdom_id") != attacker_kingdom and k["telegram_id"] != attacker_id:
                targets.append(("king", k))

    if not targets:
        await call.message.edit_text(
            "🗡️ Hozircha suiqasd qilish mumkin bo'lgan nishon yo'q.",
            reply_markup=back_kb("market_main")
        )
        return

    builder = InlineKeyboardBuilder()
    seen = set()
    for target_role, t in targets:
        tid = t["telegram_id"]
        if tid in seen:
            continue
        seen.add(tid)

        role_emoji   = "👑" if target_role == "king" else ("🛡️" if target_role == "lord" else "⚔️")
        kingdom_info = f"{t.get('sigil','')}{t.get('kingdom_name','')}"
        vassal_info  = f" • {t.get('vassal_name','')}" if target_role == "lord" else ""
        name         = t.get("full_name") or t.get("username") or str(tid)

        # Hit progress — faqat Lord va King uchun (member uchun yo'q)
        if target_role == "lord":
            hits     = await count_assassination_hits(tid)
            progress = f"[{hits}/{LORD_DEATH_HITS}]"
        elif target_role == "king":
            hits     = await count_assassination_hits(tid)
            k_info   = await get_kingdom_by_king(tid)
            if k_info and k_info["name"] == TARGARYEN_KINGDOM:
                k_hits   = await count_king_hits(tid)
                l_hits   = await count_lord_hits(tid)
                progress = f"[👑{k_hits}/{TARGARYEN_KING_HITS} | 🛡️{l_hits}/{TARGARYEN_LORD_HITS}]"
            else:
                l_hits   = await count_lord_hits(tid)
                progress = f"[{hits}/{KING_DEATH_HITS} | 🛡️{l_hits}/{KING_LORD_HITS}]"
        else:
            progress = ""

        used_today = await has_assassinated_today(call.from_user.id, tid)
        used_mark  = " ✅" if used_today else ""
        builder.row(InlineKeyboardButton(
            text=f"{role_emoji} {name} • {kingdom_info}{vassal_info} {progress}{used_mark}",
            callback_data=f"assassinate_{tid}"
        ))

    # Rol bo'yicha izoh matni
    if role == "member":
        hint = "⚔️ Siz faqat <b>o'z Lord va Qirolingizga</b> suiqasd qila olasiz."
    elif role == "lord":
        hint = "🛡️ Siz <b>o'z Qirolingiz</b> va <b>boshqa qirollik Lord/Qirollariga</b> suiqasd qila olasiz."
    else:
        hint = "👑 Siz <b>o'z qirolligingizdagi hamma</b> va <b>boshqa qirollik Lord/Qirollariga</b> suiqasd qila olasiz."

    builder.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="market_main"))
    await call.message.edit_text(
        "🗡️ <b>Suiqasd — Nishonni tanlang</b>\n\n"
        f"{hint}\n\n"
        "🛡️ Lord: <code>[bosgan/3]</code>\n"
        "👑 Qirol: <code>[umumiy/15 | Lord/5]</code>\n"
        "🐉 Targaryen: <code>[Qirol/3 | Lord/50]</code>\n\n"
        "⏳ Har bir nishonga kuniga <b>1 marta</b> suiqasd qilish mumkin\n"
        "✅ — bugun allaqachon ishlatilgan\n\n"
        "⚠️ Muvaffaqiyatsiz bo'lsa — ismingiz oshkor bo'ladi!",
        reply_markup=builder.as_markup()
    )


# ═════════════════════════════════════════════════════════════════════════════
#  SUIQASD AMALGA OSHIRISH
# ═════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("assassinate_"))
async def cb_do_assassination(call: CallbackQuery, db_user: dict, bot: Bot):
    target_id = int(call.data.split("_")[1])
    attacker   = db_user
    attacker_role = attacker.get("role", "member")

    target = await get_user(target_id)
    if not target:
        await call.answer("❌ Nishon topilmadi!", show_alert=True)
        return

    target_role      = target.get("role")
    attacker_role    = db_user.get("role", "member")
    attacker_kingdom = db_user.get("kingdom_id")
    attacker_vassal  = db_user.get("vassal_id")
    target_kingdom   = target.get("kingdom_id")
    target_vassal    = target.get("vassal_id")
    same_kingdom     = attacker_kingdom and target_kingdom and attacker_kingdom == target_kingdom

    allowed = False

    if attacker_role == "member":
        # Faqat o'z Lord va Qiroli
        own_lord  = target_role == "lord" and target_vassal == attacker_vassal
        own_king  = target_role == "king" and same_kingdom
        allowed   = own_lord or own_king

    elif attacker_role == "lord":
        # O'z Qiroli + boshqa qirollik Lord va Qirollari
        own_king      = target_role == "king" and same_kingdom
        foreign_lord  = target_role == "lord" and not same_kingdom
        foreign_king  = target_role == "king" and not same_kingdom
        allowed       = own_king or foreign_lord or foreign_king

    elif attacker_role == "king":
        # O'z qirolligidagi hamma + boshqa qirollik Lord va Qirollari
        own_anyone    = same_kingdom
        foreign_lord  = target_role == "lord" and not same_kingdom
        foreign_king  = target_role == "king" and not same_kingdom
        allowed       = own_anyone or foreign_lord or foreign_king

    if not allowed:
        await call.answer("❌ Sizning rolingiz bu nishonga suiqasd qila olmaydi!", show_alert=True)
        return

    if target_role not in ("lord", "king", "member"):
        await call.answer("❌ Bu shaxsga suiqasd qilib bo'lmaydi!", show_alert=True)
        return

    # ── Kunlik limit tekshiruvi ───────────────────────────────────────────────
    if await has_assassinated_today(call.from_user.id, target_id):
        await call.answer(
            "⏳ Siz bugun bu nishonga allaqachon suiqasd qildingiz!\n"
            "Ertaga qayta urinib ko'ring.",
            show_alert=True
        )
        return

    attacker_name = attacker.get("full_name") or attacker.get("username") or str(call.from_user.id)
    target_name   = target.get("full_name") or target.get("username") or str(target_id)

    # Suiqasdni DB ga yozish
    await add_assassination_hit(target_id, call.from_user.id, attacker_role)

    # Hisoblarni olish
    total_hits = await count_assassination_hits(target_id)
    lord_hits  = await count_lord_hits(target_id)
    king_hits  = await count_king_hits(target_id)

    # ── O'lim shartini tekshirish ─────────────────────────────────────────────
    is_dead = False
    death_reason = ""

    if target_role == "member":
        # King o'z a'zosiga suiqasd qilsa — bir zarbada o'ladi
        is_dead = True
        death_reason = "Qirol farmoni"

    elif target_role == "lord":
        if total_hits >= LORD_DEATH_HITS:
            is_dead = True
            death_reason = f"{LORD_DEATH_HITS} ta suiqasd"

    elif target_role == "king":
        k_info = await get_kingdom_by_king(target_id)
        is_targaryen = k_info and k_info["name"] == TARGARYEN_KINGDOM

        if is_targaryen:
            if king_hits >= TARGARYEN_KING_HITS:
                is_dead = True
                death_reason = f"{TARGARYEN_KING_HITS} ta Qirol suiqasdi"
            elif lord_hits >= TARGARYEN_LORD_HITS:
                is_dead = True
                death_reason = f"{TARGARYEN_LORD_HITS} ta Lord suiqasdi"
        else:
            if total_hits >= KING_DEATH_HITS:
                is_dead = True
                death_reason = f"{KING_DEATH_HITS} ta suiqasd"
            elif lord_hits >= KING_LORD_HITS:
                is_dead = True
                death_reason = f"{KING_LORD_HITS} ta Lord suiqasdi"

    # ── Natija ────────────────────────────────────────────────────────────────
    if is_dead:
        await _execute_death(
            bot, call, target, target_role, target_name,
            attacker_name, attacker_role, death_reason, total_hits, lord_hits, king_hits
        )
    else:
        await _register_hit(
            bot, call, target, target_role, target_name,
            attacker_name, attacker_role, total_hits, lord_hits, king_hits
        )


async def _register_hit(bot, call, target, target_role, target_name,
                        attacker_name, attacker_role, total_hits, lord_hits, king_hits):
    """Suiqasd hisoblandi, lekin hali o'lmadi."""
    target_id = target["telegram_id"]

    # Progress hisoblash
    if target_role == "lord":
        remaining = LORD_DEATH_HITS - total_hits
        progress_text = f"📊 Holat: {total_hits}/{LORD_DEATH_HITS} suiqasd | Qoldi: {remaining}"
    else:
        k_info = await get_kingdom_by_king(target_id)
        is_targaryen = k_info and k_info["name"] == TARGARYEN_KINGDOM
        if is_targaryen:
            progress_text = (
                f"📊 Holat: 👑 {king_hits}/{TARGARYEN_KING_HITS} Qirol | "
                f"🛡️ {lord_hits}/{TARGARYEN_LORD_HITS} Lord"
            )
        else:
            progress_text = (
                f"📊 Holat: {total_hits}/{KING_DEATH_HITS} umumiy | "
                f"🛡️ {lord_hits}/{KING_LORD_HITS} Lord"
            )

    role_label = {
        "king":   "👑 Qirol",
        "lord":   "🛡️ Lord",
        "member": "⚔️ A'zo",
    }.get(target_role, "⚔️ A'zo")

    # Nishonga xabar — suiqasdchi ismi oshkor
    try:
        await bot.send_message(
            target_id,
            f"⚠️ <b>SUIQASD URINISHI!</b>\n\n"
            f"🗡️ <b>{attacker_name}</b> ({attacker_role}) sizga suiqasd uyushtirdi!\n\n"
            f"{progress_text}"
        )
    except Exception:
        pass

    # Xronikada ismi oshkor
    await add_chronicle(
        "assassination_attempt",
        f"Suiqasd urinishi — {role_label}",
        f"🗡️ {attacker_name} → {target_name} ({role_label})\n{progress_text}",
        actor_id=call.from_user.id,
        target_id=target_id
    )

    await call.message.edit_text(
        f"🗡️ <b>Suiqasd hisoblandi!</b>\n\n"
        f"Nishon: {role_label} <b>{target_name}</b>\n\n"
        f"{progress_text}\n\n"
        f"⚠️ Ismingiz nishonga va xronikaga oshkor bo'ldi!",
        reply_markup=back_kb("assassination")
    )


async def _execute_death(bot, call, target, target_role, target_name,
                         attacker_name, attacker_role, death_reason,
                         total_hits, lord_hits, king_hits):
    """Nishon o'ldi — lavozimdan tushiriladi yoki boshqa qirollikka o'tkaziladi."""
    target_id  = target["telegram_id"]
    role_label = {
        "king":   "👑 Qirol",
        "lord":   "🛡️ Lord",
        "member": "⚔️ A'zo",
    }.get(target_role, "⚔️ A'zo")

    transfer_text = ""

    if target_role == "lord":
        vassal = await get_vassal_by_lord(target_id)
        if vassal:
            await update_vassal(vassal["id"], lord_id=None)
        await update_user(target_id, role="member")

    elif target_role == "king":
        kingdom = await get_kingdom_by_king(target_id)
        if kingdom:
            await update_kingdom(kingdom["id"], king_id=None)
        await update_user(target_id, role="member")

    elif target_role == "member":
        # Qirol farmoni — boshqa qirollikka o'tkaziladi
        from database.queries import get_all_vassals, get_vassal_members, get_all_kingdoms
        from config import MAX_VASSAL_MEMBERS
        attacker_kingdom_id = target.get("kingdom_id")

        # Boshqa qirollikdagi bo'sh vassal topish
        all_vassals = await get_all_vassals()
        new_vassal  = None
        for v in all_vassals:
            if v["kingdom_id"] == attacker_kingdom_id:
                continue
            count = len(await get_vassal_members(v["id"]))
            if count < MAX_VASSAL_MEMBERS:
                new_vassal = v
                break

        if new_vassal:
            await update_user(target_id,
                kingdom_id=new_vassal["kingdom_id"],
                vassal_id=new_vassal["id"]
            )
            new_k = await get_kingdom(new_vassal["kingdom_id"])
            transfer_text = f"🔀 {new_k['sigil']} {new_k['name']} — {new_vassal['name']} oilasiga o'tkazildi."
        else:
            # Bo'sh vassal topilmadi — vassalsiz boshqa qirollikka
            all_kingdoms = await get_all_kingdoms()
            new_kingdom  = next(
                (k for k in all_kingdoms if k["id"] != attacker_kingdom_id), None
            )
            if new_kingdom:
                await update_user(target_id, kingdom_id=new_kingdom["id"], vassal_id=None)
                transfer_text = f"🔀 {new_kingdom['sigil']} {new_kingdom['name']} qirolligiga o'tkazildi (vassalsiz)."
            else:
                transfer_text = "⚠️ Bo'sh joy topilmadi."

    # Suiqasd hisobini tozalash (member uchun hits bo'lmaydi lekin zararı yo'q)
    await reset_assassination_hits(target_id)

    # Nishonga xabar
    if target_role == "member":
        victim_msg = (
            f"💀 <b>Siz Qirol farmoni bilan o'ldirildingiз!</b>\n\n"
            f"{transfer_text}"
        )
    else:
        victim_msg = (
            f"💀 <b>Siz suiqasd qurboni bo'ldingiz!</b>\n\n"
            f"Jami {death_reason} natijasida lavozimingizdan tushirildingiz.\n"
            f"Endi oddiy a'zo sifatida davom etasiz."
        )
    try:
        await bot.send_message(target_id, victim_msg)
    except Exception:
        pass

    # Xronikaga yozish
    if target_role == "member":
        # Qirol farmoni — xronikada ko'rinadi (bu ochiq qatl)
        await add_chronicle(
            "assassination_success",
            f"💀 Qirol farmoni — {target_name}",
            f"👑 Qirol farmoni bilan ⚔️ {target_name} o'ldirildi.\n{transfer_text}",
            actor_id=None,
            target_id=target_id
        )
    else:
        # Suiqasd — suiqasdchi yashirin
        await add_chronicle(
            "assassination_success",
            f"💀 {role_label} halok bo'ldi!",
            f"{role_label} <b>{target_name}</b> suiqasd natijasida lavozimdan tushdi.\n"
            f"Sabab: {death_reason}",
            actor_id=None,
            target_id=target_id
        )

    # Hammaga e'lon
    from database.queries import get_kingdom_members
    notify_ids = set()
    if target_role == "king":
        kingdom = await get_kingdom_by_king(target_id)
        if kingdom:
            members = await get_kingdom_members(kingdom["id"])
            notify_ids = {m["telegram_id"] for m in members}
    elif target_role == "lord":
        vassal = await get_vassal_by_lord(target_id)
        if vassal:
            from database.queries import get_vassal_members
            members = await get_vassal_members(vassal["id"])
            notify_ids = {m["telegram_id"] for m in members}
    elif target_role == "member":
        # Faqat o'sha qirollik a'zolariga xabar
        kingdom_id = target.get("kingdom_id")
        if kingdom_id:
            members = await get_kingdom_members(kingdom_id)
            notify_ids = {m["telegram_id"] for m in members}

    for uid in notify_ids:
        if uid == target_id:
            continue
        try:
            await bot.send_message(
                uid,
                f"💀 <b>{role_label} {target_name} halok bo'ldi!</b>\n\n"
                f"Sabab: {death_reason}\n"
                + (f"Yangi {role_label} saylash kerak bo'ladi." if target_role != "member" else transfer_text)
            )
        except Exception:
            pass

    # Suiqasdchi uchun natija xabari
    if target_role == "member":
        result_text = (
            f"💀 <b>{target_name} o'ldirildi!</b>\n\n"
            f"{transfer_text}\n\n"
            f"📜 Qirol farmoni xronikaga yozildi."
        )
    else:
        result_text = (
            f"💀 <b>{role_label} HALOK BO'LDI!</b>\n\n"
            f"Nishon: <b>{target_name}</b>\n"
            f"Sabab: {death_reason}\n\n"
            f"📜 Xronikada faqat lavozimi ko'rinadi — sizning ismingiz yashirin qoldi."
        )
    await call.message.edit_text(result_text, reply_markup=back_kb("assassination"))
