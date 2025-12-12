from __future__ import annotations

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.db import models as _models  # noqa: F401


async def init_db() -> None:
    # Ensure pgvector extension exists (safe if already created)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
