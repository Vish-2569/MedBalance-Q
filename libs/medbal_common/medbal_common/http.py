from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3
DEFAULT_CONNECT_TIMEOUT = 5.0


def client(base_url: str = "", timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> httpx.Client:
    transport = httpx.HTTPTransport(retries=retries)
    return httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(timeout, connect=DEFAULT_CONNECT_TIMEOUT),
        transport=transport,
    )


def async_client(base_url: str = "", timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(retries=retries)
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout, connect=DEFAULT_CONNECT_TIMEOUT),
        transport=transport,
    )
