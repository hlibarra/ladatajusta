"""
Telegram notification service for scraper events
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from telegram_config import (
    MessageTemplates,
    format_timestamp,
    format_duration,
    format_uptime
)


class TelegramNotifier:
    """
    Async Telegram notification service with rate limiting and graceful error handling.
    Never raises exceptions to avoid breaking the scraper.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
        min_interval_seconds: int = 10
    ):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.enabled = enabled
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self.last_send_time = datetime.min
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.is_running = False
        self.processor_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "sent": 0,
            "failed": 0,
            "queued": 0,
            "dropped": 0
        }

    async def start(self):
        """Start the notification service and message processor"""
        if not self.enabled:
            return

        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_queue())
        print(f"[Telegram] Notification service started (chat_id: {self.chat_id})")

    async def stop(self):
        """Gracefully shutdown the notification service"""
        if not self.is_running:
            return

        self.is_running = False

        # Process remaining messages with timeout
        try:
            await asyncio.wait_for(self.message_queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass

        print(f"[Telegram] Notification service stopped (sent: {self.stats['sent']}, failed: {self.stats['failed']})")

    async def _process_queue(self):
        """Background task to process message queue with rate limiting"""
        while self.is_running:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )

                # Check rate limit
                elapsed = datetime.now() - self.last_send_time
                if elapsed < self.min_interval:
                    wait_time = (self.min_interval - elapsed).total_seconds()
                    await asyncio.sleep(wait_time)

                # Send message
                success = await self._send_message_safe(
                    message["text"],
                    message.get("parse_mode", "HTML")
                )

                if success:
                    self.stats["sent"] += 1
                    self.last_send_time = datetime.now()
                else:
                    self.stats["failed"] += 1

                self.message_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[Telegram] Queue processor error: {e}")
                await asyncio.sleep(1)

    async def _send_message_safe(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send message with error handling.
        Returns True if successful, False otherwise.
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            print(f"[Telegram] Send error: {e}")
            return False
        except Exception as e:
            print(f"[Telegram] Unexpected error: {e}")
            return False

    async def send_notification(
        self,
        message: str,
        priority: str = "normal",
        parse_mode: str = "HTML"
    ):
        """
        Queue a notification for sending.

        Args:
            message: Message text (can include HTML formatting)
            priority: "high" (immediate) or "normal" (queued)
            parse_mode: Telegram parse mode ("HTML" or "Markdown")
        """
        if not self.enabled:
            return

        try:
            if priority == "high":
                # High priority: send immediately (bypass queue)
                await self._send_message_safe(message, parse_mode)
                self.stats["sent"] += 1
            else:
                # Normal priority: add to queue
                if self.message_queue.full():
                    self.stats["dropped"] += 1
                    print(f"[Telegram] Message queue full, dropping message")
                else:
                    await self.message_queue.put({
                        "text": message,
                        "parse_mode": parse_mode
                    })
                    self.stats["queued"] += 1
        except Exception as e:
            print(f"[Telegram] Failed to queue notification: {e}")

    # Convenience methods for specific event types

    async def notify_service_start(
        self,
        scrape_interval: int,
        ai_interval: int,
        control_url: str,
        scrape_enabled: bool = True,
        ai_enabled: bool = True,
        auto_prepare_enabled: bool = True,
        auto_publish_enabled: bool = True
    ):
        """Notify when scraper service starts"""
        # Format services status
        def status_icon(enabled: bool) -> str:
            return "✅" if enabled else "❌"

        services_status = "\n".join([
            f"  {status_icon(scrape_enabled)} Scraping Automático",
            f"  {status_icon(ai_enabled)} Procesamiento IA",
            f"  {status_icon(auto_prepare_enabled)} Auto-Preparar",
            f"  {status_icon(auto_publish_enabled)} Auto-Publicar",
        ])

        message = MessageTemplates.SERVICE_START.format(
            scrape_interval=scrape_interval,
            ai_interval=ai_interval,
            services_status=services_status,
            control_url=control_url,
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def notify_service_stop(
        self,
        uptime_seconds: int,
        items_scraped: int,
        items_ai_processed: int
    ):
        """Notify when scraper service stops"""
        message = MessageTemplates.SERVICE_STOP.format(
            uptime=format_uptime(uptime_seconds),
            items_scraped=items_scraped,
            items_ai_processed=items_ai_processed,
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def notify_scrape_start(
        self,
        source_count: int,
        mode: str = "scheduled",
        source_names: list = None,
        user_email: str = None
    ):
        """Notify when scraping starts"""
        # Format source list
        if source_names:
            source_list = "\n".join([f"  • {name}" for name in source_names])
        else:
            source_list = "  • Todas las activas"

        # Format user info
        user_info = f"\n👤 Usuario: {user_email}" if user_email else ""

        message = MessageTemplates.SCRAPE_START.format(
            source_count=source_count,
            source_list=source_list,
            mode=mode,
            user_info=user_info,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_scrape_complete(
        self,
        total_items: int,
        sources_processed: int,
        duration_seconds: float
    ):
        """Notify when scraping completes"""
        message = MessageTemplates.SCRAPE_COMPLETE.format(
            total_items=total_items,
            sources_processed=sources_processed,
            duration=format_duration(duration_seconds),
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_source_error(
        self,
        source_name: str,
        error_message: str,
        consecutive_errors: int
    ):
        """Notify when a source encounters an error"""
        # Truncate long error messages
        error_short = error_message[:200] + "..." if len(error_message) > 200 else error_message

        message = MessageTemplates.SOURCE_ERROR.format(
            source_name=source_name,
            error_message=error_short,
            consecutive_errors=consecutive_errors,
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def notify_source_disabled(self, source_name: str, error_count: int):
        """Notify when a source is auto-disabled"""
        message = MessageTemplates.SOURCE_DISABLED.format(
            source_name=source_name,
            count=error_count,
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def notify_ai_start(self, pending_count: int, mode: str = "automático"):
        """Notify when AI processing starts"""
        message = MessageTemplates.AI_START.format(
            pending_count=pending_count,
            mode=mode,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_ai_complete(
        self,
        processed: int,
        failed: int,
        duration_seconds: float
    ):
        """Notify when AI processing completes"""
        message = MessageTemplates.AI_COMPLETE.format(
            processed=processed,
            failed=failed,
            duration=format_duration(duration_seconds),
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_auto_prepare_start(self, pending_count: int, mode: str = "automático"):
        """Notify when auto-prepare starts"""
        message = MessageTemplates.AUTO_PREPARE_START.format(
            pending_count=pending_count,
            mode=mode,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_auto_prepare(
        self,
        ready: int,
        duplicates: int,
        quality_failed: int
    ):
        """Notify when auto-prepare completes"""
        message = MessageTemplates.AUTO_PREPARE.format(
            ready=ready,
            duplicates=duplicates,
            quality_failed=quality_failed,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_auto_publish_start(self, pending_count: int, mode: str = "automático"):
        """Notify when auto-publish starts"""
        message = MessageTemplates.AUTO_PUBLISH_START.format(
            pending_count=pending_count,
            mode=mode,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_auto_publish(self, published: int):
        """Notify when auto-publish completes"""
        message = MessageTemplates.AUTO_PUBLISH.format(
            published=published,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_curator_complete(
        self,
        published: int,
        available: int,
        selected: int
    ):
        """Notify when news curation completes"""
        message = MessageTemplates.CURATOR_COMPLETE.format(
            published=published,
            available=available,
            selected=selected,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_error(self, task_name: str, error_message: str):
        """Notify when a task encounters an error"""
        # Truncate long error messages
        error_short = error_message[:300] + "..." if len(error_message) > 300 else error_message

        message = MessageTemplates.TASK_ERROR.format(
            task_name=task_name,
            error_message=error_short,
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def notify_config_changed(self, changes: dict):
        """Notify when configuration is updated"""
        changes_text = "\n".join([f"• {key}: {value}" for key, value in changes.items()])

        message = MessageTemplates.CONFIG_CHANGED.format(
            changes=changes_text,
            timestamp=format_timestamp()
        )
        await self.send_notification(message)

    async def notify_restart_requested(self):
        """Notify when service restart is requested"""
        message = MessageTemplates.RESTART_REQUESTED.format(
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")

    async def send_test_message(self):
        """Send a test notification"""
        message = MessageTemplates.TEST_MESSAGE.format(
            timestamp=format_timestamp()
        )
        await self.send_notification(message, priority="high")


# Singleton pattern
_notifier_instance: Optional[TelegramNotifier] = None


def get_notifier() -> Optional[TelegramNotifier]:
    """
    Get singleton notifier instance.
    Returns None if Telegram notifications are not configured.
    """
    global _notifier_instance

    if _notifier_instance is None:
        enabled = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() == "true"
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        min_interval = int(os.getenv("TELEGRAM_MIN_INTERVAL_SECONDS", "10"))

        if enabled and bot_token and chat_id:
            _notifier_instance = TelegramNotifier(
                bot_token=bot_token,
                chat_id=chat_id,
                enabled=enabled,
                min_interval_seconds=min_interval
            )
        else:
            if enabled:
                print("[Telegram] Notifications enabled but missing configuration (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
            return None

    return _notifier_instance
