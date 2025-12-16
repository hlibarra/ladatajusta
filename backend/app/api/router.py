from fastapi import APIRouter

from app.api.routes import auth, feeds, publications, scrape, stats

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(publications.router, prefix="/publications", tags=["publications"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
api_router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
