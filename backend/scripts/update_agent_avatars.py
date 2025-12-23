"""
Script para actualizar las URLs de avatar de los agentes con DiceBear avatars.
Ejecutar: python -m scripts.update_agent_avatars
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Agent
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


async def update_avatars():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent))).all()

        if not agents:
            print("No hay agentes en la base de datos.")
            return

        print(f"Actualizando avatares para {len(agents)} agentes...\n")

        # Avatar URLs using DiceBear API
        avatar_mapping = {
            "ana-datos": "https://api.dicebear.com/7.x/avataaars/svg?seed=Ana&backgroundColor=3b82f6",
            "roberto-investigador": "https://api.dicebear.com/7.x/avataaars/svg?seed=Roberto&backgroundColor=8b5cf6",
            "carmen-economia": "https://api.dicebear.com/7.x/avataaars/svg?seed=Carmen&backgroundColor=10b981",
            "diego-ambiente": "https://api.dicebear.com/7.x/avataaars/svg?seed=Diego&backgroundColor=14b8a6",
            "maria-salud": "https://api.dicebear.com/7.x/avataaars/svg?seed=Maria&backgroundColor=f59e0b",
        }

        for agent in agents:
            if agent.slug in avatar_mapping:
                old_url = agent.avatar_url
                agent.avatar_url = avatar_mapping[agent.slug]
                print(f"[OK] {agent.name}")
                print(f"  Anterior: {old_url}")
                print(f"  Nueva: {agent.avatar_url}\n")

        await db.commit()

        print(f"Avatares actualizados exitosamente para {len(agents)} agentes!")


if __name__ == "__main__":
    asyncio.run(update_avatars())
