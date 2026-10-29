from __future__ import annotations

import httpx


def client(base_url: str = "", timeout: float = 10.0, retries: int = 3) -> httpx.Client:
    transport = httpx.HTTPTransport(retries=retries)
    return httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
