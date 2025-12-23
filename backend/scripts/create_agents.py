"""
Script para crear la tabla de agentes y poblarla con agentes de ejemplo.
Ejecutar: python -m scripts.create_agents
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
from app.db.init_db import init_db


async def create_agents():
    # Initialize database tables first
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if agents already exist
        from sqlalchemy import select
        existing = await db.scalar(select(Agent).limit(1))

        if existing:
            print("Los agentes ya existen en la base de datos.")
            return

        # Sample AI agents
        agents_data = [
            {
                "name": "Ana Datos",
                "slug": "ana-datos",
                "description": "Especialista en análisis de datos gubernamentales y transparencia",
                "specialization": "Política y Transparencia",
                "avatar_url": "/agents/ana-datos.png",
                "bio": "Ana es una agente de IA especializada en desentrañar información compleja de datos gubernamentales. Con algoritmos avanzados de procesamiento de lenguaje natural, transforma documentos oficiales densos en reportajes claros y accesibles para todos los ciudadanos.",
            },
            {
                "name": "Roberto Investigador",
                "slug": "roberto-investigador",
                "description": "Experto en investigación periodística y verificación de hechos",
                "specialization": "Investigación",
                "avatar_url": "/agents/roberto-investigador.png",
                "bio": "Roberto combina técnicas de periodismo investigativo con machine learning para descubrir patrones sospechosos en contratos públicos y detectar posibles casos de corrupción. Su precisión y objetividad lo hacen ideal para investigaciones profundas.",
            },
            {
                "name": "Carmen Economía",
                "slug": "carmen-economia",
                "description": "Analista económica y experta en finanzas públicas",
                "specialization": "Economía",
                "avatar_url": "/agents/carmen-economia.png",
                "bio": "Carmen analiza indicadores económicos, presupuestos y estadísticas financieras con una claridad excepcional. Traduce jerga económica compleja en información comprensible que ayuda a los ciudadanos a entender cómo se manejan los recursos públicos.",
            },
            {
                "name": "Diego Ambiente",
                "slug": "diego-ambiente",
                "description": "Periodista especializado en medio ambiente y sostenibilidad",
                "specialization": "Medio Ambiente",
                "avatar_url": "/agents/diego-ambiente.png",
                "bio": "Diego monitorea políticas ambientales, proyectos de energía renovable y cambios en regulaciones ecológicas. Su enfoque basado en datos científicos hace que sus reportajes sean confiables y fundamentados.",
            },
            {
                "name": "María Salud",
                "slug": "maria-salud",
                "description": "Reportera de salud pública y políticas sanitarias",
                "specialization": "Salud",
                "avatar_url": "/agents/maria-salud.png",
                "bio": "María cubre temas de salud pública, desde la apertura de nuevos hospitales hasta análisis de políticas sanitarias. Su capacidad para procesar estudios médicos y datos epidemiológicos la hace una fuente confiable de información de salud.",
            },
        ]

        # Create agents
        for agent_data in agents_data:
            agent = Agent(**agent_data)
            db.add(agent)

        await db.commit()

        print(f"Se crearon {len(agents_data)} agentes de IA exitosamente!")
        print("\nAgentes creados:")
        for i, agent_data in enumerate(agents_data, 1):
            print(f"{i}. {agent_data['name']} - {agent_data['specialization']}")


if __name__ == "__main__":
    asyncio.run(create_agents())
