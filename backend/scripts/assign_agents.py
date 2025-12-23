"""
Script para asignar agentes a las publicaciones existentes.
Ejecutar: python -m scripts.assign_agents
"""
import asyncio
import sys
from pathlib import Path

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Agent, Publication
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


async def assign_agents():
    async with AsyncSessionLocal() as db:
        # Get all agents
        agents = (await db.scalars(select(Agent).order_by(Agent.created_at))).all()
        if not agents:
            print("No hay agentes en la base de datos. Ejecuta scripts.create_agents primero.")
            return

        print(f"Encontrados {len(agents)} agentes:")
        for agent in agents:
            print(f"  - {agent.name} ({agent.specialization})")

        # Get all publications without agent
        publications = (
            await db.scalars(select(Publication).where(Publication.agent_id.is_(None)))
        ).all()

        if not publications:
            print("\nTodas las publicaciones ya tienen un agente asignado.")
            return

        print(f"\nEncontradas {len(publications)} publicaciones sin agente.")

        # Assign agents in a round-robin fashion
        for i, pub in enumerate(publications):
            agent = agents[i % len(agents)]
            pub.agent_id = agent.id
            print(f"  - '{pub.title[:50]}...' -> {agent.name}")

        await db.commit()

        print(f"\nSe asignaron agentes a {len(publications)} publicaciones!")


if __name__ == "__main__":
    asyncio.run(assign_agents())
