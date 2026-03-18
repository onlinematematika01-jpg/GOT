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
                        actor_id: int = None, target_id: int = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO chronicles (event_type, title, description, actor_id, target_id)
               VALUES ($1, $2, $3, $4, $5)""",
            event_type, title, description, actor_id, target_id
        )


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
