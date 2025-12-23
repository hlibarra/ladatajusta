"""
Script para agregar la columna agent_id a la tabla publications.
Ejecutar: python -m scripts.add_agent_column
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.session import engine


async def add_agent_column():
    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='publications' AND column_name='agent_id'
            """)
        )
        if result.fetchone():
            print("La columna agent_id ya existe en la tabla publications.")
            return

        # Add agent_id column
        await conn.execute(
            text("""
                ALTER TABLE publications
                ADD COLUMN agent_id UUID REFERENCES agents(id) ON DELETE SET NULL
            """)
        )

        # Create index
        await conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS ix_publications_agent_id
                ON publications(agent_id)
            """)
        )

        print("Columna agent_id agregada exitosamente a la tabla publications!")
        print("Indice creado en agent_id!")


if __name__ == "__main__":
    asyncio.run(add_agent_column())
