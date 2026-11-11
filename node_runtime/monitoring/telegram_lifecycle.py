"""
AWARESPAN — Telegram Source Lifecycle & Offline Queue Notifier
Dispatches formatted source connection/disconnection events with resilient offline SQLite queueing.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType
from node_runtime.monitoring.telegram_notify import send_message
from shared.config.settings import get_settings
from shared.logging.logger import get_logger

log = get_logger("node_runtime.telegram_lifecycle")


class TelegramLifecycleNotifier:
    """Manages Telegram source lifecycle notifications with offline queueing."""

    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.node_name = "Raspberry Pi 5"
        self.db_path = db_path or getattr(settings, "telegram_queue_path", "state/telegram_queue.db")

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._init_db()

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_offline_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        chat_id TEXT,
                        created_at REAL NOT NULL,
                        retries INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'pending'
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_telegram_queue_status ON telegram_offline_queue(status, id)"
                )
                conn.commit()

    def start(self) -> None:
        """Start the background queue processor."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._queue_worker_loop, name="TelegramQueueWorker", daemon=True)
        self._worker_thread.start()
        log.info("TelegramLifecycleNotifier started with queue at %s", self.db_path)

    def stop(self) -> None:
        """Stop background worker."""
        if not self._is_running:
            return
        self._is_running = False
        self._stop_event.set()
        self._wake_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        log.info("TelegramLifecycleNotifier stopped.")

    def format_source_label(self, source: MediaSource) -> str:
        """Determine human-readable source label: Camera, Microphone, or Camera + Microphone."""
        if source.camera_active and source.mic_active:
            return "Camera + Microphone"
        if source.camera_active:
            return "Camera"
        if source.mic_active:
            return "Microphone"

        if source.source_type == SourceType.COMBINED:
            return "Camera + Microphone"
        if source.source_type == SourceType.CAMERA:
            return "Camera"
        if source.source_type == SourceType.MICROPHONE:
            return "Microphone"

        return "Media Source"

    def format_device_name(self, source: MediaSource) -> str:
        """Return friendly device name or source id."""
        return source.friendly_name or source.source_id

    def notify_connection(self, source: MediaSource) -> None:
        """Format and dispatch connection notification."""
        label = self.format_source_label(source)
        device = self.format_device_name(source)
        now_str = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"<b>AWARESPAN | SOURCE CONNECTED</b>\n"
            f"Node: {self.node_name}\n"
            f"Source: {label}\n"
            f"Device: {device}\n"
            f"Status: Active\n"
            f"Time: {now_str}"
        )
        self.dispatch_or_queue(msg)

    def notify_disconnection(self, source: MediaSource, reason: str = "") -> None:
        """Format and dispatch disconnection notification."""
        label = self.format_source_label(source)
        device = self.format_device_name(source)
        now_str = datetime.now().strftime("%H:%M:%S")

        msg = (
            f"<b>AWARESPAN | SOURCE DISCONNECTED</b>\n"
            f"Node: {self.node_name}\n"
            f"Source: {label}\n"
            f"Device: {device}\n"
            f"Status: Disconnected\n"
            f"Time: {now_str}"
        )
        self.dispatch_or_queue(msg)

    def on_source_transition(
        self,
        source: MediaSource,
        old_state: SourceState,
        new_state: SourceState,
        reason: str = "",
    ) -> None:
        """Listener hook for SourceStateMachine transitions."""
        if new_state == SourceState.ACTIVE and old_state != SourceState.ACTIVE:
            self.notify_connection(source)
        elif new_state in (SourceState.DISCONNECTED, SourceState.EXPIRED, SourceState.REJECTED):
            if old_state in (SourceState.ACTIVE, SourceState.DEGRADED, SourceState.CONNECTING):
                self.notify_disconnection(source, reason=reason)

    def dispatch_or_queue(self, text: str, chat_id: Optional[str] = None) -> bool:
        """Attempt immediate delivery; enqueue to SQLite if offline/failure."""
        # Check if queue has pending items first; if so, must preserve order
        pending_count = self.get_pending_count()
        if pending_count == 0:
            try:
                success = send_message(text, chat_id)
                if success:
                    log.info("Telegram notification delivered directly")
                    return True
            except Exception as exc:
                log.warning("Telegram direct send failed: %s; queueing locally", exc)

        # Enqueue for offline delivery
        self._enqueue(text, chat_id)
        log.info("Telegram notification queued for offline delivery (queue depth: %d)", pending_count + 1)
        self._wake_event.set()
        return False

    def _enqueue(self, text: str, chat_id: Optional[str] = None) -> int:
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO telegram_offline_queue (text, chat_id, created_at, retries, status)
                    VALUES (?, ?, ?, 0, 'pending')
                    """,
                    (text, chat_id, time.time()),
                )
                conn.commit()
                return cur.lastrowid

    def get_pending_count(self) -> int:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM telegram_offline_queue WHERE status = 'pending'"
                ).fetchone()
                return row["count"] if row else 0

    def _queue_worker_loop(self) -> None:
        """Background thread draining queued messages when online with backoff and rate-limiting."""
        backoff_sec = 2.0
        max_backoff = 60.0

        while not self._stop_event.is_set():
            # Wait until signaled or 10s periodic check
            self._wake_event.wait(timeout=10.0)
            self._wake_event.clear()

            if self._stop_event.is_set():
                break

            # Fetch pending items in chronological order
            items = []
            with self._lock:
                with self._get_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT id, text, chat_id, retries, created_at
                        FROM telegram_offline_queue
                        WHERE status = 'pending'
                        ORDER BY id ASC
                        LIMIT 10
                        """
                    ).fetchall()
                    items = [dict(r) for r in rows]

            if not items:
                continue

            # Process items sequentially
            delivered_any = False
            for item in items:
                if self._stop_event.is_set():
                    break

                item_id = item["id"]
                text = item["text"]
                chat_id = item.get("chat_id")
                retries = item.get("retries", 0)

                try:
                    success = send_message(text, chat_id)
                except Exception as exc:
                    log.debug("Worker send error: %s", exc)
                    success = False

                if success:
                    delivered_any = True
                    backoff_sec = 2.0  # reset backoff on success
                    with self._lock:
                        with self._get_connection() as conn:
                            conn.execute(
                                "DELETE FROM telegram_offline_queue WHERE id = ?",
                                (item_id,),
                            )
                            conn.commit()
                    log.info("Drained queued Telegram notification (id=%d)", item_id)
                    # Rate-limit between deliveries (1.0 second pause to avoid flood/Telegram limits)
                    time.sleep(1.0)
                else:
                    # Still offline or rate limited; update retries and pause
                    with self._lock:
                        with self._get_connection() as conn:
                            conn.execute(
                                "UPDATE telegram_offline_queue SET retries = retries + 1 WHERE id = ?",
                                (item_id,),
                            )
                            conn.commit()
                    log.debug("Offline queue delivery failed (id=%d); backing off %.1fs", item_id, backoff_sec)
                    time.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 1.5, max_backoff)
                    break  # Stop processing remainder of batch; connection appears down
