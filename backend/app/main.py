from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.init_db import init_db


app = FastAPI(title="La Data Justa API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    if settings.app_env == "dev":
        await init_db()


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


app.include_router(api_router)
