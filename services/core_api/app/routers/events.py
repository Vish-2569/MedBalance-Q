"""SSE endpoint: fan-out Redis Streams to browsers."""
from __future__ import annotations

import asyncio
import json
import uuid

import redis

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from medbal_common.settings import settings

router = APIRouter()

ALL_STREAMS = [
    "report.received",
    "inventory.updated",
    "anomaly.flagged",
    "forecast.updated",
    "coldchain.alert",
    "plan.progress",
    "plan.completed",
    "plan.revised",
    "order.status",
    "custody.scanned",
]

SSE_GROUP = "sse"
HEARTBEAT_INTERVAL = 15


async def _event_generator():
    consumer_name = f"core-api-sse-{uuid.uuid4().hex[:8]}"
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    for stream in ALL_STREAMS:
        try:
            r.xgroup_create(stream, SSE_GROUP, id="0", mkstream=True)
        except redis.exceptions.ResponseError:
            pass

    stream_ids = {s: ">" for s in ALL_STREAMS}
    try:
        while True:
            try:
                entries = r.xreadgroup(
                    SSE_GROUP, consumer_name, stream_ids, count=20, block=2000
                )
            except redis.exceptions.ConnectionError:
                yield f"event: error\ndata: {json.dumps({'error': 'redis connection lost'})}\n\n"
                await asyncio.sleep(5)
                r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
                continue

            if entries:
                for stream_name, messages in entries:
                    for msg_id, fields in messages:
                        data = fields.get("data", "{}")
                        yield f"event: {stream_name}\ndata: {data}\n\n"
                        r.xack(stream_name, SSE_GROUP, msg_id)
            else:
                yield f"event: heartbeat\ndata: {json.dumps({'ts': __import__('time').time()})}\n\n"
                await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    finally:
        r.close()


@router.get("/events")
async def stream_events():
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
