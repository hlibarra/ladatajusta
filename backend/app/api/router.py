from fastapi import APIRouter

from app.api.routes import auth, feeds, publications, scrape, stats, preferences
from app.api.routes.agents import router as agents_router
from app.api.routes.scraping_items import router as scraping_items_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(publications.router, prefix="/publications", tags=["publications"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
api_router.include_router(scraping_items_router, prefix="/scraping-items", tags=["scraping-items"])
api_router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(preferences.router, prefix="/user", tags=["preferences"])
