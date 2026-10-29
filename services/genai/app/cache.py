from __future__ import annotations

import hashlib
import json
from typing import Any

from medbal_common.logging import get_logger

log = get_logger("genai.cache")


def make_cache_key(prompt_id: str, version: int, model: str, input_data: dict[str, Any]) -> str:
    canonical = json.dumps(input_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    raw = f"{prompt_id}@v{version}+{model}+{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()


class LLMCache:
    """Redis-backed LLM response cache with DEMO_MODE support."""

    PREFIX = "llm:cache:"
    TTL = 86400 * 7  # 7 days

    def __init__(self, redis_client: Any | None = None):
        self._redis = redis_client

    def get(self, key: str) -> dict[str, Any] | None:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(self.PREFIX + key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            log.warning("cache_get_error", key=key[:12], error=str(e))
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            self._redis.set(self.PREFIX + key, json.dumps(value, default=str), ex=self.TTL)
        except Exception as e:
            log.warning("cache_set_error", key=key[:12], error=str(e))
