from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis

from medbal_common.settings import settings

_log = logging.getLogger("medbal.bus")

MAX_CONNECT_RETRIES = 10
RETRY_BACKOFF_BASE = 1.5

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL, decode_responses=True,
            socket_connect_timeout=5, socket_timeout=5,
        )
    return _redis_client


def wait_for_redis(retries: int = MAX_CONNECT_RETRIES) -> redis.Redis:
    """Get Redis with startup retry/backoff."""
    r = get_redis()
    for attempt in range(1, retries + 1):
        try:
            r.ping()
            _log.info("Redis ready (attempt %d)", attempt)
            return r
        except Exception as exc:
            delay = min(RETRY_BACKOFF_BASE ** attempt, 15)
            _log.warning("Redis not ready (attempt %d/%d): %s — retrying in %.1fs",
                         attempt, retries, exc, delay)
            if attempt < retries:
                time.sleep(delay)
    _log.error("Redis unreachable after %d attempts", retries)
    return r


def publish(stream: str, data: dict[str, Any]) -> str | None:
    try:
        r = get_redis()
        return r.xadd(stream, {"data": json.dumps(data)})
    except Exception as exc:
        _log.warning("publish failed on %s: %s", stream, exc)
        return None


def consume(
    stream: str,
    group: str,
    consumer: str,
    handler: Callable[[dict[str, Any]], None],
    *,
    block_ms: int = 5000,
) -> None:
    r = get_redis()
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass

    while True:
        entries = r.xreadgroup(group, consumer, {stream: ">"}, count=10, block=block_ms)
        if not entries:
            continue
        for _stream_name, messages in entries:
            for msg_id, fields in messages:
                try:
                    payload = json.loads(fields.get("data", "{}"))
                    handler(payload)
                except Exception:
                    pass
                r.xack(stream, group, msg_id)


@asynccontextmanager
async def stream_lifespan(
    stream: str,
    group: str,
    consumer: str,
    handler: Callable[[dict[str, Any]], None],
) -> AsyncGenerator[None, None]:
    stop = threading.Event()
    loop = asyncio.get_running_loop()

    def _run() -> None:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            r.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.exceptions.ResponseError:
            pass

        while not stop.is_set():
            entries = r.xreadgroup(group, consumer, {stream: ">"}, count=10, block=2000)
            if not entries:
                continue
            for _stream_name, messages in entries:
                for msg_id, fields in messages:
                    try:
                        payload = json.loads(fields.get("data", "{}"))
                        handler(payload)
                    except Exception:
                        pass
                    r.xack(stream, group, msg_id)

    thread = await loop.run_in_executor(None, lambda: threading.Thread(target=_run, daemon=True))
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)
