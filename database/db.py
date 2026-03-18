"""
Database layer — PostgreSQL with asyncpg
"""
import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # ── Kingdoms ──────────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kingdoms (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) UNIQUE NOT NULL,
                sigil       VARCHAR(10)  DEFAULT '⚔️',
                king_id     BIGINT       UNIQUE,
                gold        INTEGER      DEFAULT 1000,
                soldiers    INTEGER      DEFAULT 500,
                dragons     INTEGER      DEFAULT 0,
                created_at  TIMESTAMP    DEFAULT NOW()
            )
        """)

        # ── Vassal families ───────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vassals (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                kingdom_id  INTEGER REFERENCES kingdoms(id) ON DELETE CASCADE,
                lord_id     BIGINT       UNIQUE,
                gold        INTEGER      DEFAULT 0,
                soldiers    INTEGER      DEFAULT 0,
                created_at  TIMESTAMP    DEFAULT NOW()
            )
        """)

        # ── Users ─────────────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id     BIGINT   PRIMARY KEY,
                username        VARCHAR(100),
                full_name       VARCHAR(200),
                role            VARCHAR(20)  DEFAULT 'member',
                kingdom_id      INTEGER      REFERENCES kingdoms(id),
                vassal_id       INTEGER      REFERENCES vassals(id),
                gold            INTEGER      DEFAULT 0,
                last_farm       TIMESTAMP,
                joined_at       TIMESTAMP    DEFAULT NOW()
            )
        """)

        # ── Chronicles (event log) ────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chronicles (
                id          SERIAL PRIMARY KEY,
                event_type  VARCHAR(50) NOT NULL,
                title       VARCHAR(200),
                description TEXT,
                actor_id    BIGINT,
                target_id   BIGINT,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)

        # ── Diplomacy ─────────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS diplomacy (
                id              SERIAL PRIMARY KEY,
                from_kingdom_id INTEGER REFERENCES kingdoms(id),
                to_kingdom_id   INTEGER REFERENCES kingdoms(id),
                offer_type      VARCHAR(20) NOT NULL,  -- 'war' | 'alliance'
                status          VARCHAR(20) DEFAULT 'pending',
                created_at      TIMESTAMP DEFAULT NOW()
            )
        """)

        # ── Lord elections ────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS elections (
                id          SERIAL PRIMARY KEY,
                vassal_id   INTEGER REFERENCES vassals(id),
                candidate_id BIGINT,
                voter_id    BIGINT,
                created_at  TIMESTAMP DEFAULT NOW(),
                UNIQUE(vassal_id, voter_id)
            )
        """)

        # ── Artifacts ─────────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id          SERIAL PRIMARY KEY,
                owner_type  VARCHAR(20),   -- 'kingdom' | 'vassal' | 'user'
                owner_id    INTEGER,
                artifact    VARCHAR(50),
                tier        VARCHAR(5),
                purchased_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # ── Queue tracking ────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS queue_state (
                id          INTEGER PRIMARY KEY DEFAULT 1,
                phase       INTEGER DEFAULT 1,
                current_vassal_index INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            INSERT INTO queue_state (id, phase, current_vassal_index)
            VALUES (1, 1, 0)
            ON CONFLICT (id) DO NOTHING
        """)

    logger.info("Database initialized successfully")
