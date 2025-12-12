from fastapi import APIRouter

from app.api.routes import publications, scrape

api_router = APIRouter(prefix="/api")
api_router.include_router(publications.router, prefix="/publications", tags=["publications"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
