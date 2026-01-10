from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentOut
from app.db.models import Agent
from app.db.session import get_db

router = APIRouter()


@router.get("", response_model=list[AgentOut])
async def get_agents(db: AsyncSession = Depends(get_db)) -> list[AgentOut]:
    """Get all agents"""
    query = select(Agent).order_by(Agent.name)
    result = await db.scalars(query)
    agents = result.all()

    return [
        AgentOut(
            id=agent.id,
            name=agent.name,
            slug=agent.slug,
            description=agent.description,
            specialization=agent.specialization,
            avatar_url=agent.avatar_url,
        )
        for agent in agents
    ]
