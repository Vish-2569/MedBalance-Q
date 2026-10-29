from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis

from medbal_common.settings import settings


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish(stream: str, data: dict[str, Any]) -> str:
    r = get_redis()
    return r.xadd(stream, {"data": json.dumps(data)})


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
