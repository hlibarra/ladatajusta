"""
Control Server for Scraper Service
Provides HTTP API for monitoring and controlling the scraper.

Endpoints:
- GET /status - Current scraper status
- GET /logs - Stream logs via SSE
- POST /restart - Trigger service restart
- POST /stop - Stop the service
- POST /run-now - Run scraping immediately
- GET /config - Get current configuration
- PUT /config - Update configuration
"""

import asyncio
import json
from datetime import datetime
from collections import deque
from pathlib import Path
from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

# Config file path
CONFIG_FILE = Path(__file__).parent / "config.json"


class ScraperController:
    """Controls and monitors the scraper service"""

    def __init__(self):
        # Service state
        self.status = "starting"  # starting, running, paused, stopped
        self.last_scrape_time = None
        self.last_ai_time = None
        self.last_curate_time = None
        self.next_scrape_time = None
        self.next_ai_time = None
        self.next_curate_time = None
        self.current_task = None  # What's running now
        self.current_source = None  # Current source being scraped
        self.items_processed = {"scraped": 0, "ai_processed": 0, "prepared": 0, "curated": 0}

        # Load configuration from file (or use defaults)
        self.config = self._load_config()

        # Log buffer (last 1000 lines)
        self.log_buffer = deque(maxlen=1000)
        self.log_subscribers = []

        # Control signals
        self.restart_requested = False
        self.stop_requested = False
        self.run_now_requested = False
        self.run_source_ids = None  # List of source IDs to scrape (None = all active)
        self.run_user_id = None  # User ID who triggered manual run
        self.process_ai_requested = False
        self.auto_prepare_requested = False
        self.auto_publish_requested = False
        self.curate_now_requested = False
        self.curate_dry_run = False  # If true, only simulate curation

        # Start time
        self.start_time = datetime.now()

    def _load_config(self) -> dict:
        """Load configuration from file or return defaults"""
        default_config = {
            # Enable/Disable automatic services
            "scrape_enabled": True,
            "ai_process_enabled": True,
            "auto_prepare_enabled": True,
            "auto_publish_enabled": True,
            # Intervals
            "scrape_interval_minutes": 60,
            "ai_process_interval_minutes": 30,
            "prepare_hours_ago": 24,
            "selected_source_ids": None,
            # Curator configuration
            "curator_enabled": False,
            "curator_interval_minutes": 120,
            "curator_target_count": 12,
            "curator_max_per_category": 3,
            "curator_max_per_source": 3,
        }

        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    saved_config = json.load(f)
                    # Merge with defaults to handle new fields
                    default_config.update(saved_config)
                    print(f"[CONFIG] Loaded configuration from {CONFIG_FILE}")
            else:
                # Save default config
                self._save_config(default_config)
                print(f"[CONFIG] Created default configuration at {CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Error loading config: {e}, using defaults")

        return default_config

    def _save_config(self, config: dict = None):
        """Save configuration to file"""
        try:
            config_to_save = config if config is not None else self.config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            print(f"[CONFIG] Saved configuration to {CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Error saving config: {e}")

    def add_log(self, message: str, level: str = "INFO"):
        """Add a log entry and notify subscribers"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.log_buffer.append(log_entry)

        # Notify SSE subscribers
        for queue in self.log_subscribers:
            try:
                queue.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass  # Skip if queue is full

    def get_status(self) -> dict:
        """Get current service status"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "status": self.status,
            "uptime_seconds": int(uptime),
            "current_task": self.current_task,
            "current_source": self.current_source,
            "last_scrape": self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            "last_ai_process": self.last_ai_time.isoformat() if self.last_ai_time else None,
            "last_curate": self.last_curate_time.isoformat() if self.last_curate_time else None,
            "next_scrape": self.next_scrape_time.isoformat() if self.next_scrape_time else None,
            "next_ai_process": self.next_ai_time.isoformat() if self.next_ai_time else None,
            "next_curate": self.next_curate_time.isoformat() if self.next_curate_time else None,
            "items_processed": self.items_processed,
            "config": self.config,
        }

    def get_logs(self, limit: int = 100) -> list:
        """Get recent logs"""
        logs = list(self.log_buffer)
        return logs[-limit:] if limit else logs

    def request_restart(self):
        """Request service restart"""
        self.restart_requested = True
        self.add_log("Restart requested via API", "WARN")

        # Notify via Telegram
        try:
            from telegram_notifier import get_notifier
            notifier = get_notifier()
            if notifier:
                import asyncio
                asyncio.create_task(notifier.notify_restart_requested())
        except Exception:
            pass  # Silently fail if Telegram not available

    def request_stop(self):
        """Request service stop"""
        self.stop_requested = True
        self.add_log("Stop requested via API", "WARN")

    def request_run_now(self, source_ids: list = None, user_id: str = None):
        """Request immediate scraping run"""
        self.run_now_requested = True
        self.run_source_ids = source_ids
        self.run_user_id = user_id
        if source_ids:
            self.add_log(f"Immediate run requested for {len(source_ids)} source(s)", "INFO")
        else:
            self.add_log("Immediate run requested for all active sources", "INFO")

    def request_process_ai(self):
        """Request AI processing only"""
        self.process_ai_requested = True
        self.add_log("AI processing requested via API", "INFO")

    def request_auto_prepare(self):
        """Request auto-prepare only"""
        self.auto_prepare_requested = True
        self.add_log("Auto-prepare requested via API", "INFO")

    def request_auto_publish(self):
        """Request auto-publish only"""
        self.auto_publish_requested = True
        self.add_log("Auto-publish requested via API", "INFO")

    def request_curate(self, dry_run: bool = False):
        """Request news curation (intelligent selection and publish)"""
        self.curate_now_requested = True
        self.curate_dry_run = dry_run
        mode = "dry run" if dry_run else "publish"
        self.add_log(f"News curation requested ({mode})", "INFO")

    def update_config(self, new_config: dict):
        """Update configuration and save to file"""
        for key, value in new_config.items():
            if key in self.config:
                self.config[key] = value

        # Save to file
        self._save_config()

        self.add_log(f"Configuration updated: {new_config}", "INFO")

        # Notify via Telegram
        try:
            from telegram_notifier import get_notifier
            notifier = get_notifier()
            if notifier:
                import asyncio
                asyncio.create_task(notifier.notify_config_changed(new_config))
        except Exception:
            pass  # Silently fail if Telegram not available


# Global controller instance
controller = ScraperController()


# --- HTTP Handlers ---

async def handle_status(request):
    """GET /status - Return current status"""
    return web.json_response(controller.get_status())


async def handle_logs(request):
    """GET /logs - Return recent logs or stream via SSE"""
    # Check if SSE requested
    accept = request.headers.get('Accept', '')
    if 'text/event-stream' in accept:
        return await handle_logs_stream(request)

    # Return JSON logs
    limit = int(request.query.get('limit', 100))
    logs = controller.get_logs(limit)
    return web.json_response({"logs": logs})


async def handle_logs_stream(request):
    """Stream logs via Server-Sent Events"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    await response.prepare(request)

    # Create a queue for this subscriber
    queue = asyncio.Queue(maxsize=100)
    controller.log_subscribers.append(queue)

    try:
        # Send existing logs first
        for log in controller.get_logs(50):
            data = json.dumps(log)
            await response.write(f"data: {data}\n\n".encode('utf-8'))

        # Stream new logs
        while True:
            try:
                log = await asyncio.wait_for(queue.get(), timeout=30.0)
                data = json.dumps(log)
                await response.write(f"data: {data}\n\n".encode('utf-8'))
            except asyncio.TimeoutError:
                # Send keepalive
                await response.write(b": keepalive\n\n")
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError, ClientConnectionResetError):
        # Client disconnected - this is normal
        pass
    except Exception:
        # Catch any other connection errors silently
        pass
    finally:
        if queue in controller.log_subscribers:
            controller.log_subscribers.remove(queue)

    return response


async def handle_restart(request):
    """POST /restart - Restart the service"""
    controller.request_restart()
    return web.json_response({"success": True, "message": "Restart requested"})


async def handle_stop(request):
    """POST /stop - Stop the service"""
    controller.request_stop()
    return web.json_response({"success": True, "message": "Stop requested"})


async def handle_run_now(request):
    """POST /run-now - Run scraping immediately, optionally for specific sources"""
    source_ids = None
    user_id = None
    try:
        data = await request.json()
        source_ids = data.get('source_ids')
        user_id = data.get('user_id')
    except Exception:
        pass  # No JSON body or invalid JSON, run all sources

    controller.request_run_now(source_ids, user_id)
    if source_ids:
        return web.json_response({"success": True, "message": f"Immediate run requested for {len(source_ids)} source(s)"})
    return web.json_response({"success": True, "message": "Immediate run requested for all sources"})


async def handle_process_ai(request):
    """POST /process-ai - Run AI processing only"""
    controller.request_process_ai()
    return web.json_response({"success": True, "message": "AI processing requested"})


async def handle_auto_prepare(request):
    """POST /auto-prepare - Run auto-prepare only"""
    controller.request_auto_prepare()
    return web.json_response({"success": True, "message": "Auto-prepare requested"})


async def handle_auto_publish(request):
    """POST /auto-publish - Run auto-publish only"""
    controller.request_auto_publish()
    return web.json_response({"success": True, "message": "Auto-publish requested"})


async def handle_curate(request):
    """POST /curate - Run news curation (select and publish best items)"""
    dry_run = False
    try:
        data = await request.json()
        dry_run = data.get('dry_run', False)
    except Exception:
        pass  # No JSON body, use defaults

    controller.request_curate(dry_run=dry_run)
    mode = "simulación" if dry_run else "publicación"
    return web.json_response({"success": True, "message": f"Curación de noticias solicitada ({mode})"})


async def handle_get_config(request):
    """GET /config - Get current configuration"""
    return web.json_response(controller.config)


async def handle_put_config(request):
    """PUT /config - Update configuration"""
    try:
        data = await request.json()
        controller.update_config(data)
        return web.json_response({"success": True, "config": controller.config})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


async def handle_telegram_status(request):
    """GET /telegram/status - Get Telegram notification status"""
    try:
        from telegram_notifier import get_notifier
        notifier = get_notifier()

        if not notifier:
            return web.json_response({
                "enabled": False,
                "reason": "Not configured"
            })

        return web.json_response({
            "enabled": notifier.enabled,
            "queue_size": notifier.message_queue.qsize(),
            "last_send_time": notifier.last_send_time.isoformat() if notifier.last_send_time else None,
            "stats": notifier.stats
        })
    except Exception as e:
        return web.json_response({
            "enabled": False,
            "error": str(e)
        }, status=500)


async def handle_telegram_test(request):
    """POST /telegram/test - Send test notification"""
    try:
        from telegram_notifier import get_notifier
        notifier = get_notifier()

        if not notifier:
            return web.json_response({
                "success": False,
                "error": "Telegram not configured"
            }, status=400)

        await notifier.send_test_message()
        return web.json_response({
            "success": True,
            "message": "Test notification sent"
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


async def handle_cors_preflight(request):
    """Handle CORS preflight requests"""
    return web.Response(headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Accept',
    })


def create_app() -> web.Application:
    """Create the aiohttp application"""
    app = web.Application()

    # Add CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            return await handle_cors_preflight(request)
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    app.middlewares.append(cors_middleware)

    # Add routes
    app.router.add_get('/status', handle_status)
    app.router.add_get('/logs', handle_logs)
    app.router.add_post('/restart', handle_restart)
    app.router.add_post('/stop', handle_stop)
    app.router.add_post('/run-now', handle_run_now)
    app.router.add_post('/process-ai', handle_process_ai)
    app.router.add_post('/auto-prepare', handle_auto_prepare)
    app.router.add_post('/auto-publish', handle_auto_publish)
    app.router.add_post('/curate', handle_curate)
    app.router.add_get('/config', handle_get_config)
    app.router.add_put('/config', handle_put_config)
    app.router.add_get('/telegram/status', handle_telegram_status)
    app.router.add_post('/telegram/test', handle_telegram_test)
    app.router.add_options('/{path:.*}', handle_cors_preflight)

    return app


async def start_control_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the control server"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    controller.add_log(f"Control server started on {host}:{port}", "INFO")
    return runner
