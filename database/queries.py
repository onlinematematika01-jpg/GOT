"""
Database query helpers
"""
from database.db import get_pool
from config import (
    MAX_KINGDOM_MEMBERS, MIN_VASSAL_MEMBERS, MAX_VASSAL_MEMBERS,
    KINGDOMS_COUNT, KINGDOM_NAMES, KINGDOM_SIGILS
)
import logging

logger = logging.getLogger(__name__)


# ── User queries ──────────────────────────────────────────────────────────────

async def get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )


async def create_user(telegram_id: int, username: str, full_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO users (telegram_id, username, full_name)
               VALUES ($1, $2, $3) RETURNING *""",
            telegram_id, username, full_name
        )


async def update_user(telegram_id: int, **kwargs):
    pool = await get_pool()
    cols = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    vals = list(kwargs.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE users SET {cols} WHERE telegram_id = $1",
            telegram_id, *vals
        )


# ── Queue / placement system ──────────────────────────────────────────────────

async def assign_user_to_slot(telegram_id: int) -> dict:
    """
    Core queue algorithm:
    Phase 1: Fill 7 kingdoms × 7 members = 49 users
    Phase 2: Fill vassals one-by-one (4 each) for Lord elections
    Phase 3: Top up all vassals to 7 (random rotation)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        qs = await conn.fetchrow("SELECT * FROM queue_state WHERE id = 1")
        phase = qs["phase"]

        # ── PHASE 1: Fill kingdoms ────────────────────────────────────────────
        if phase == 1:
            for kname in KINGDOM_NAMES:
                kingdom = await conn.fetchrow(
                    "SELECT * FROM kingdoms WHERE name = $1", kname
                )
                if kingdom is None:
                    continue
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE kingdom_id = $1", kingdom["id"]
                )
                if count < MAX_KINGDOM_MEMBERS:
                    await conn.execute(
                        "UPDATE users SET kingdom_id=$1 WHERE telegram_id=$2",
                        kingdom["id"], telegram_id
                    )
                    return {"phase": 1, "kingdom": kname}

            # All kingdoms full → advance to phase 2
            await conn.execute(
                "UPDATE queue_state SET phase=2, current_vassal_index=0 WHERE id=1"
            )
            phase = 2

        # ── PHASE 2: Fill vassals (4 each) ────────────────────────────────────
        if phase == 2:
            idx = qs["current_vassal_index"]
            vassals = await conn.fetch("SELECT * FROM vassals ORDER BY id")
            if not vassals:
                return {"phase": 2, "error": "No vassals defined"}

            while idx < len(vassals):
                vassal = vassals[idx]
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE vassal_id = $1", vassal["id"]
                )
                if count < MIN_VASSAL_MEMBERS:
                    await conn.execute(
                        """UPDATE users SET kingdom_id=$1, vassal_id=$2
                           WHERE telegram_id=$3""",
                        vassal["kingdom_id"], vassal["id"], telegram_id
                    )
                    return {"phase": 2, "vassal": vassal["name"]}
                idx += 1

            # All vassals have 4 members → advance to phase 3
            await conn.execute(
                "UPDATE queue_state SET phase=3, current_vassal_index=0 WHERE id=1"
            )
            phase = 3

        # ── PHASE 3: Top up vassals to 7 (round-robin) ───────────────────────
        if phase == 3:
            idx = qs["current_vassal_index"]
            vassals = await conn.fetch("SELECT * FROM vassals ORDER BY id")
            loops = 0
            while loops < len(vassals):
                vassal = vassals[idx % len(vassals)]
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE vassal_id = $1", vassal["id"]
                )
                if count < MAX_VASSAL_MEMBERS:
                    await conn.execute(
                        """UPDATE users SET kingdom_id=$1, vassal_id=$2
                           WHERE telegram_id=$3""",
                        vassal["kingdom_id"], vassal["id"], telegram_id
                    )
                    await conn.execute(
                        "UPDATE queue_state SET current_vassal_index=$1 WHERE id=1",
                        (idx + 1) % len(vassals)
                    )
                    return {"phase": 3, "vassal": vassal["name"]}
                idx = (idx + 1) % len(vassals)
                loops += 1
            return {"phase": 3, "error": "All slots full"}

    return {"error": "Unknown phase"}


# ── Kingdom queries ───────────────────────────────────────────────────────────

async def get_all_kingdoms():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM kingdoms ORDER BY id")


async def get_kingdom(kingdom_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM kingdoms WHERE id = $1", kingdom_id
        )


async def get_kingdom_by_king(king_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM kingdoms WHERE king_id = $1", king_id
        )


async def create_kingdom(name: str):
    pool = await get_pool()
    sigil = KINGDOM_SIGILS.get(name, "⚔️")
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO kingdoms (name, sigil) VALUES ($1, $2)
               ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING *""",
            name, sigil
        )


async def update_kingdom(kingdom_id: int, **kwargs):
    pool = await get_pool()
    cols = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    vals = list(kwargs.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE kingdoms SET {cols} WHERE id = $1", kingdom_id, *vals
        )


async def get_kingdom_members(kingdom_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE kingdom_id = $1", kingdom_id
        )


# ── Vassal queries ────────────────────────────────────────────────────────────

async def get_all_vassals():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM vassals ORDER BY id")


async def get_vassal(vassal_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM vassals WHERE id = $1", vassal_id
        )


async def get_vassal_by_lord(lord_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM vassals WHERE lord_id = $1", lord_id
        )


async def get_kingdom_vassals(kingdom_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM vassals WHERE kingdom_id = $1", kingdom_id
        )


async def get_vassal_members(vassal_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE vassal_id = $1", vassal_id
        )


async def create_vassal(name: str, kingdom_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO vassals (name, kingdom_id) VALUES ($1, $2) RETURNING *""",
            name, kingdom_id
        )


async def update_vassal(vassal_id: int, **kwargs):
    pool = await get_pool()
    cols = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    vals = list(kwargs.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE vassals SET {cols} WHERE id = $1", vassal_id, *vals
        )


# ── Chronicle queries ─────────────────────────────────────────────────────────

async def add_chronicle(event_type: str, title: str, description: str,
                        actor_id: int = None, target_id: int = None,
                        bot=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO chronicles (event_type, title, description, actor_id, target_id)
               VALUES ($1, $2, $3, $4, $5)""",
            event_type, title, description, actor_id, target_id
        )

    # Kanalga post yuborish
    if bot is not None:
        await _post_to_channel(bot, event_type, title, description)


async def _post_to_channel(bot, event_type: str, title: str, description: str):
    """Voqeani kanal ga post qilish"""
    from config import CHRONICLE_CHANNEL_ID

    event_emojis = {
        "war":                "⚔️",
        "war_end":            "🏆",
        "assassination_success": "💀",
        "assassination_attempt": "🗡️",
        "coronation":         "👑",
        "election":           "🗳️",
        "alliance":           "🤝",
        "loan":               "🏦",
        "purchase":           "💰",
        "gm_event":           "🔮",
        "defection":          "🚀",
        "punishment":         "⚔️",
        "vassal_created":     "🛡️",
        "tribute":            "💸",
        "system":             "⚙️",
    }

    # Kanalga bormaydigan voqealar
    skip_types = {"join", "purchase"}
    if event_type in skip_types:
        return

    emoji = event_emojis.get(event_type, "📜")
    text = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{description}\n\n"
        f"<i>📜 Taxtlar O\'yini Xronikasi</i>"
    )
    try:
        await bot.send_message(CHRONICLE_CHANNEL_ID, text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Chronicle channel error: {e}")


async def get_chronicles(limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM chronicles ORDER BY created_at DESC LIMIT $1", limit
        )


# ── Election queries ──────────────────────────────────────────────────────────

async def cast_vote(vassal_id: int, candidate_id: int, voter_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """INSERT INTO elections (vassal_id, candidate_id, voter_id)
                   VALUES ($1, $2, $3)""",
                vassal_id, candidate_id, voter_id
            )
            return True
        except Exception:
            return False  # already voted


async def get_votes(vassal_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT candidate_id, COUNT(*) as votes
               FROM elections WHERE vassal_id = $1
               GROUP BY candidate_id ORDER BY votes DESC""",
            vassal_id
        )


async def get_election_winner(vassal_id: int) -> int | None:
    rows = await get_votes(vassal_id)
    if rows:
        return rows[0]["candidate_id"]
    return None


# ── Diplomacy queries ─────────────────────────────────────────────────────────

async def create_diplomacy(from_kingdom: int, to_kingdom: int, offer_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO diplomacy (from_kingdom_id, to_kingdom_id, offer_type)
               VALUES ($1, $2, $3) RETURNING *""",
            from_kingdom, to_kingdom, offer_type
        )


async def update_diplomacy(diplomacy_id: int, status: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE diplomacy SET status=$1 WHERE id=$2", status, diplomacy_id
        )


async def get_pending_diplomacy(to_kingdom_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT d.*, k.name as from_name, k.sigil as from_sigil
               FROM diplomacy d JOIN kingdoms k ON d.from_kingdom_id = k.id
               WHERE d.to_kingdom_id = $1 AND d.status = 'pending'""",
            to_kingdom_id
        )


# ── Artifact queries ──────────────────────────────────────────────────────────

async def buy_artifact(owner_type: str, owner_id: int, artifact: str, tier: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO artifacts (owner_type, owner_id, artifact, tier)
               VALUES ($1, $2, $3, $4)""",
            owner_type, owner_id, artifact, tier
        )


async def get_artifacts(owner_type: str, owner_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM artifacts WHERE owner_type=$1 AND owner_id=$2",
            owner_type, owner_id
        )


# ── Assassination queries ─────────────────────────────────────────────────────

async def add_assassination_hit(target_id: int, attacker_id: int, attacker_role: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO assassination_hits (target_id, attacker_id, attacker_role)
               VALUES ($1, $2, $3)""",
            target_id, attacker_id, attacker_role
        )


async def count_assassination_hits(target_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM assassination_hits WHERE target_id = $1",
            target_id
        )


async def count_lord_hits(target_id: int) -> int:
    """Count hits from Lords only (for king death threshold)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """SELECT COUNT(*) FROM assassination_hits
               WHERE target_id = $1 AND attacker_role = 'lord'""",
            target_id
        )


async def count_king_hits(target_id: int) -> int:
    """Count hits from Kings only (for Targaryen death threshold)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """SELECT COUNT(*) FROM assassination_hits
               WHERE target_id = $1 AND attacker_role = 'king'""",
            target_id
        )


async def get_assassination_attackers(target_id: int):
    """Get list of attackers for a target"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT attacker_id, attacker_role, COUNT(*) as hits
               FROM assassination_hits WHERE target_id = $1
               GROUP BY attacker_id, attacker_role
               ORDER BY hits DESC""",
            target_id
        )


async def reset_assassination_hits(target_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM assassination_hits WHERE target_id = $1",
            target_id
        )


async def get_all_lords():
    """Get all users with lord role"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT u.*, v.name as vassal_name, k.name as kingdom_name, k.sigil
               FROM users u
               LEFT JOIN vassals v ON u.vassal_id = v.id
               LEFT JOIN kingdoms k ON u.kingdom_id = k.id
               WHERE u.role = 'lord'
               ORDER BY k.name, v.name"""
        )


async def get_all_kings():
    """Get all users with king role"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT u.*, k.name as kingdom_name, k.sigil
               FROM users u
               LEFT JOIN kingdoms k ON u.kingdom_id = k.id
               WHERE u.role = 'king'
               ORDER BY k.name"""
        )


# ── Market prices queries ─────────────────────────────────────────────────────

async def get_all_prices():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM market_prices ORDER BY item")
        return {r["item"]: {"price": r["price"], "label": r["label"]} for r in rows}


async def get_price(item: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT price FROM market_prices WHERE item=$1", item)
        return row["price"] if row else 0


async def update_price(item: str, price: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE market_prices SET price=$1 WHERE item=$2",
            price, item
        )


# ── Loan queries ──────────────────────────────────────────────────────────────

async def create_loan(borrower_type: str, borrower_id: int,
                      amount: int, interest: int = 0, due_date=None):
    pool = await get_pool()
    total_due = amount + (amount * interest // 100)
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO loans
               (borrower_type, borrower_id, amount, interest, total_due, due_date)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            borrower_type, borrower_id, amount, interest, total_due, due_date
        )


async def get_loans(borrower_type: str, borrower_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT * FROM loans
               WHERE borrower_type=$1 AND borrower_id=$2
               ORDER BY created_at DESC""",
            borrower_type, borrower_id
        )


async def get_all_active_loans():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM loans WHERE status='active' ORDER BY created_at"
        )


async def repay_loan(loan_id: int, amount: int):
    """Qarzni to'lash — qisman yoki to'liq"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        loan = await conn.fetchrow("SELECT * FROM loans WHERE id=$1", loan_id)
        if not loan:
            return None
        new_paid = loan["paid"] + amount
        status = "paid" if new_paid >= loan["total_due"] else "active"
        return await conn.fetchrow(
            """UPDATE loans SET paid=$1, status=$2 WHERE id=$3 RETURNING *""",
            new_paid, status, loan_id
        )


async def get_loan(loan_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM loans WHERE id=$1", loan_id)


# ── War queries ───────────────────────────────────────────────────────────────

async def create_war(attacker_id: int, defender_id: int, starts_at) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO wars (attacker_id, defender_id, status, starts_at)
               VALUES ($1, $2, 'pending', $3) RETURNING *""",
            attacker_id, defender_id, starts_at
        )


async def get_war(war_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM wars WHERE id=$1", war_id)


async def get_active_war(kingdom_id: int):
    """Qirollikning joriy urushi"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT * FROM wars
               WHERE (attacker_id=$1 OR defender_id=$1)
               AND status NOT IN ('finished')
               ORDER BY declared_at DESC LIMIT 1""",
            kingdom_id
        )


async def update_war(war_id: int, **kwargs):
    pool = await get_pool()
    cols = ", ".join(f"{k}=${i+2}" for i, k in enumerate(kwargs))
    vals = list(kwargs.values())
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE wars SET {cols} WHERE id=$1", war_id, *vals
        )


async def get_pending_wars():
    """Boshlanishi kerak bo'lgan urushlar"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        from datetime import datetime
        return await conn.fetch(
            """SELECT * FROM wars
               WHERE status='pending' AND starts_at <= $1""",
            datetime.utcnow()
        )


async def add_war_support(war_id: int, from_type: str, from_id: int,
                          to_kingdom: int, gold: int = 0,
                          soldiers: int = 0, scorpions: int = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO war_support
               (war_id, from_type, from_id, to_kingdom, gold, soldiers, scorpions)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            war_id, from_type, from_id, to_kingdom, gold, soldiers, scorpions
        )


async def get_war_support(war_id: int, to_kingdom: int):
    """Biror qirollikka kelgan jami yordam"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT
               COALESCE(SUM(gold),0) as total_gold,
               COALESCE(SUM(soldiers),0) as total_soldiers,
               COALESCE(SUM(scorpions),0) as total_scorpions
               FROM war_support
               WHERE war_id=$1 AND to_kingdom=$2""",
            war_id, to_kingdom
        )


async def create_tribute(war_id: int, from_kingdom: int, to_kingdom: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tributes (war_id, from_kingdom, to_kingdom)
               VALUES ($1, $2, $3)""",
            war_id, from_kingdom, to_kingdom
        )


async def get_active_tributes():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM tributes WHERE active=TRUE"
        )


# ── Game settings ─────────────────────────────────────────────────────────────

async def get_game_active() -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM game_settings WHERE key='game_active'"
        )
        return row["value"] == "true" if row else True


async def set_game_active(active: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO game_settings (key, value) VALUES ('game_active', $1)
               ON CONFLICT (key) DO UPDATE SET value=$1""",
            "true" if active else "false"
        )
