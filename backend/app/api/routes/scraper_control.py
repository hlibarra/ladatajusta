"""
Scraper Control API Routes
Proxies requests to the scraper's internal control server.
"""

import os
import httpx
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# Scraper control server URL
SCRAPER_CONTROL_URL = os.getenv("SCRAPER_CONTROL_URL", "http://scraper:8080")


class RunNowRequest(BaseModel):
    source_ids: Optional[List[str]] = None


class ConfigUpdate(BaseModel):
    scrape_interval_minutes: Optional[int] = None
    ai_process_interval_minutes: Optional[int] = None
    prepare_hours_ago: Optional[int] = None
    selected_source_ids: Optional[List[str]] = None


async def proxy_get(path: str):
    """Make GET request to scraper control server"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{SCRAPER_CONTROL_URL}{path}")
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Scraper service unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to scraper: {str(e)}"
        )


async def proxy_post(path: str, data: dict = None):
    """Make POST request to scraper control server"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if data:
                response = await client.post(f"{SCRAPER_CONTROL_URL}{path}", json=data)
            else:
                response = await client.post(f"{SCRAPER_CONTROL_URL}{path}")
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Scraper service unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to scraper: {str(e)}"
        )


async def proxy_put(path: str, data: dict):
    """Make PUT request to scraper control server"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(f"{SCRAPER_CONTROL_URL}{path}", json=data)
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Scraper service unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to scraper: {str(e)}"
        )


@router.get("/status")
async def get_scraper_status():
    """Get current scraper status"""
    return await proxy_get("/status")


@router.get("/logs")
async def get_scraper_logs(limit: int = 100):
    """Get recent scraper logs"""
    return await proxy_get(f"/logs?limit={limit}")


@router.get("/logs/stream")
async def stream_scraper_logs(request: Request):
    """Stream scraper logs via SSE"""
    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "GET",
                    f"{SCRAPER_CONTROL_URL}/logs",
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    async for chunk in response.aiter_bytes():
                        if await request.is_disconnected():
                            break
                        yield chunk
        except httpx.ConnectError:
            yield b"data: {\"error\": \"Scraper service unavailable\"}\n\n"
        except Exception as e:
            error_msg = str(e).replace('"', '\\"')
            yield f"data: {{\"error\": \"{error_msg}\"}}\n\n".encode()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/restart")
async def restart_scraper():
    """Restart the scraper service loop"""
    return await proxy_post("/restart")


@router.post("/stop")
async def stop_scraper():
    """Stop the scraper service"""
    return await proxy_post("/stop")


@router.post("/run-now")
async def run_scraper_now(request: RunNowRequest = Body(default=None)):
    """Trigger immediate scraping run, optionally for specific sources"""
    data = None
    if request and request.source_ids:
        data = {"source_ids": request.source_ids}
    return await proxy_post("/run-now", data)


@router.post("/process-ai")
async def process_ai_now():
    """Trigger AI processing only (without scraping)"""
    return await proxy_post("/process-ai")


@router.post("/auto-prepare")
async def auto_prepare_now():
    """Trigger auto-prepare only"""
    return await proxy_post("/auto-prepare")


@router.get("/config")
async def get_scraper_config():
    """Get current scraper configuration"""
    return await proxy_get("/config")


@router.put("/config")
async def update_scraper_config(config: ConfigUpdate):
    """Update scraper configuration"""
    # Use exclude_unset to only include fields that were explicitly provided
    # This allows sending null for selected_source_ids while not affecting other fields
    data = config.model_dump(exclude_unset=True)
    return await proxy_put("/config", data)
