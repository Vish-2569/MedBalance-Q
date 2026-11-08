"""SSE endpoint: fan-out Redis Streams to browsers."""
from __future__ import annotations

import asyncio
import json

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

async def _event_generator():
    stream_ids = {stream: "$" for stream in ALL_STREAMS}
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        while True:
            try:
                entries = await asyncio.to_thread(
                    r.xread, stream_ids, count=20, block=2000,
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
                        stream_ids[stream_name] = msg_id
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
