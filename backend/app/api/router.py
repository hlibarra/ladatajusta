from fastapi import APIRouter

from app.api.routes import auth, feeds, publications, scrape, stats, preferences
from app.api.routes.agents import router as agents_router
from app.api.routes.scraping_items import router as scraping_items_router
from app.api.routes.scraping_sources import router as scraping_sources_router
from app.api.routes.sections import router as sections_router
from app.api.routes.config import router as config_router
from app.api.routes.users import router as users_router
from app.api.routes.scraper_control import router as scraper_control_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(publications.router, prefix="/publications", tags=["publications"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(sections_router, prefix="/sections", tags=["sections"])
api_router.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
api_router.include_router(scraping_items_router, prefix="/scraping-items", tags=["scraping-items"])
api_router.include_router(scraping_sources_router, prefix="/scraping-sources", tags=["scraping-sources"])
api_router.include_router(scraper_control_router, prefix="/scraper", tags=["scraper-control"])
api_router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(preferences.router, prefix="/user", tags=["preferences"])
api_router.include_router(config_router, prefix="/config", tags=["config"])
