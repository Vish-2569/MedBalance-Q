"""Tests for the browser event stream."""
from __future__ import annotations

import asyncio
import time

import pytest

from app.routers import events


@pytest.mark.asyncio
async def test_event_stream_does_not_block_other_api_work(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.calls = []
            self.sent_event = False

        def xread(self, stream_ids, *, count, block):
            self.calls.append(dict(stream_ids))
            time.sleep(0.05)
            if not self.sent_event:
                self.sent_event = True
                first_stream = next(iter(stream_ids))
                return [(first_stream, [("1-0", {"data": '{"ok": true}'})])]
            return []

        def close(self):
            pass

    clients = []

    def create_client(*args, **kwargs):
        client = FakeRedis()
        clients.append(client)
        return client

    monkeypatch.setattr(events.redis.Redis, "from_url", create_client)
    stream = events._event_generator()
    second_stream = events._event_generator()
    api_task_ran = asyncio.Event()

    async def concurrent_api_work():
        await asyncio.sleep(0.01)
        api_task_ran.set()

    task = asyncio.create_task(concurrent_api_work())
    try:
        first_event = await asyncio.wait_for(stream.__anext__(), timeout=0.2)
        await task
        assert first_event == 'event: report.received\ndata: {"ok": true}\n\n'
        assert api_task_ran.is_set()

        assert await second_stream.__anext__() == first_event
        await stream.__anext__()
        assert clients[0].calls[1]["report.received"] == "1-0"
    finally:
        await stream.aclose()
        await second_stream.aclose()
