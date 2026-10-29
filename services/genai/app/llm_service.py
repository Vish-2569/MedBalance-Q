from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import os

from medbal_common.logging import get_logger
from medbal_common.settings import settings

from . import prompt_registry
from .cache import LLMCache, make_cache_key
from .providers import LLMProvider, LLMResult
from .validation import validate_output

log = get_logger("genai.service")

TIMEOUT_FAST = 20.0
TIMEOUT_SMART = 45.0
MAX_RETRIES = 2


class LLMService:
    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMCache,
        *,
        db_engine: Any | None = None,
        concurrency: int = 4,
    ):
        self._provider = provider
        self._cache = cache
        self._engine = db_engine
        self._semaphore = asyncio.Semaphore(concurrency)

    def _resolve_model(self, tier: str) -> str:
        if tier == "smart":
            return settings.LLM_MODEL_SMART
        return settings.LLM_MODEL_FAST

    def _timeout_for(self, tier: str) -> float:
        return TIMEOUT_SMART if tier == "smart" else TIMEOUT_FAST

    def _log_call(
        self,
        purpose: str,
        prompt_id: str,
        version: int,
        model: str,
        input_data: dict[str, Any],
        output: Any,
        confidence: float,
        cached: bool,
        fallback: bool,
        latency_ms: int,
        cache_key: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        ok: bool = True,
        error: str | None = None,
    ) -> None:
        if self._engine is None:
            return
        try:
            from sqlalchemy import text

            output_payload = {
                "data": output,
                "provider": self._provider.name(),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "ok": ok,
            }
            if error:
                output_payload["error"] = error

            with self._engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO llm_call "
                        "(purpose, prompt_id, version, model, input, output, "
                        "confidence, cached, fallback, latency_ms, cache_key) "
                        "VALUES (:purpose, :prompt_id, :version, :model, "
                        ":input::jsonb, :output::jsonb, :confidence, :cached, "
                        ":fallback, :latency_ms, :cache_key)"
                    ),
                    {
                        "purpose": purpose,
                        "prompt_id": prompt_id,
                        "version": version,
                        "model": model,
                        "input": json.dumps(input_data, default=str),
                        "output": json.dumps(output_payload, default=str),
                        "confidence": confidence,
                        "cached": cached,
                        "fallback": fallback,
                        "latency_ms": latency_ms,
                        "cache_key": cache_key,
                    },
                )
                conn.commit()
        except Exception as e:
            log.warning("log_call_error", error=str(e))

    async def complete(
        self,
        purpose: str,
        prompt_id: str,
        version: int,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        spec = prompt_registry.get(prompt_id, version)
        if spec is None:
            return {
                "output": None,
                "model": "",
                "prompt_ref": f"{prompt_id}@v{version}",
                "confidence": 0.0,
                "cached": False,
                "fallback": True,
                "ok": False,
                "error": f"Prompt {prompt_id}@v{version} not found",
            }

        model = self._resolve_model(spec.model)
        timeout = self._timeout_for(spec.model)
        cache_key = make_cache_key(prompt_id, version, model, input_data)
        demo_mode = os.environ.get("DEMO_MODE", settings.DEMO_MODE)

        if demo_mode in ("live", "replay"):
            cached_resp = self._cache.get(cache_key)
            if cached_resp is not None:
                self._log_call(
                    purpose=purpose, prompt_id=prompt_id, version=version,
                    model=model, input_data=input_data, output=cached_resp.get("output"),
                    confidence=cached_resp.get("confidence", 1.0),
                    cached=True, fallback=False, latency_ms=0, cache_key=cache_key,
                )
                return {
                    "output": cached_resp.get("output"),
                    "model": model,
                    "prompt_ref": spec.ref,
                    "confidence": cached_resp.get("confidence", 1.0),
                    "cached": True,
                    "fallback": False,
                    "ok": True,
                }

        if demo_mode == "replay":
            self._log_call(
                purpose=purpose, prompt_id=prompt_id, version=version,
                model=model, input_data=input_data, output=None,
                confidence=0.0, cached=False, fallback=True,
                latency_ms=0, cache_key=cache_key, ok=False,
                error="replay cache miss",
            )
            return {
                "output": None,
                "model": model,
                "prompt_ref": spec.ref,
                "confidence": 0.0,
                "cached": False,
                "fallback": True,
                "ok": False,
                "error": "replay cache miss",
            }

        messages = [
            {"role": "system", "content": spec.system},
            {"role": "user", "content": spec.render_user(input_data)},
        ]

        last_error: str | None = None
        for attempt in range(1 + MAX_RETRIES):
            t0 = time.monotonic()
            try:
                async with self._semaphore:
                    result: LLMResult = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self._provider.complete(
                                messages,
                                schema=spec.json_schema,
                                tools=spec.tools,
                                model=model,
                                temperature=spec.temperature,
                                max_tokens=spec.max_tokens,
                                timeout=timeout,
                            ),
                        ),
                        timeout=timeout + 5,
                    )
            except (asyncio.TimeoutError, Exception) as e:
                latency = int((time.monotonic() - t0) * 1000)
                last_error = f"{type(e).__name__}: {e}"
                log.warning("provider_error", attempt=attempt, error=last_error)
                continue

            latency = int((time.monotonic() - t0) * 1000)

            if spec.json_schema and result.output is not None:
                validated, err = validate_output(result.output, spec.json_schema)
                if err:
                    last_error = err
                    log.warning("validation_error", attempt=attempt, error=err[:200])
                    messages.append({"role": "assistant", "content": json.dumps(result.output)})
                    messages.append({"role": "user", "content": f"Validation error: {err}\nPlease fix and try again."})
                    continue
                result_output = validated
            else:
                result_output = result.output

            if demo_mode in ("live", "record"):
                self._cache.set(cache_key, {
                    "output": result_output,
                    "confidence": result.confidence,
                })

            self._log_call(
                purpose=purpose, prompt_id=prompt_id, version=version,
                model=model, input_data=input_data, output=result_output,
                confidence=result.confidence, cached=False, fallback=False,
                latency_ms=latency, cache_key=cache_key,
                tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            )

            resp: dict[str, Any] = {
                "output": result_output,
                "model": model,
                "prompt_ref": spec.ref,
                "confidence": result.confidence,
                "cached": False,
                "fallback": False,
                "ok": True,
            }
            if result.tool_calls:
                resp["tool_calls"] = result.tool_calls
            return resp

        latency = int((time.monotonic() - t0) * 1000) if "t0" in dir() else 0
        self._log_call(
            purpose=purpose, prompt_id=prompt_id, version=version,
            model=model, input_data=input_data, output=None,
            confidence=0.0, cached=False, fallback=True,
            latency_ms=latency, cache_key=cache_key,
            ok=False, error=last_error,
        )
        return {
            "output": None,
            "model": model,
            "prompt_ref": spec.ref,
            "confidence": 0.0,
            "cached": False,
            "fallback": True,
            "ok": False,
            "error": last_error,
        }

    def get_health_stats(self) -> dict[str, Any]:
        if self._engine is None:
            return {"status": "no_db", "calls_24h": 0}
        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT "
                    "  COUNT(*) AS total, "
                    "  COUNT(*) FILTER (WHERE cached) AS cached, "
                    "  COUNT(*) FILTER (WHERE fallback) AS fallbacks, "
                    "  COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) "
                    "    FILTER (WHERE NOT cached), 0) AS p50, "
                    "  COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) "
                    "    FILTER (WHERE NOT cached), 0) AS p95 "
                    "FROM llm_call WHERE created_at > now() - interval '24 hours'"
                )).mappings().one()

                total = row["total"]
                cached = row["cached"]

                purpose_rows = conn.execute(text(
                    "SELECT purpose, COUNT(*) AS cnt, "
                    "  COUNT(*) FILTER (WHERE cached) AS cached, "
                    "  COUNT(*) FILTER (WHERE fallback) AS fallbacks "
                    "FROM llm_call WHERE created_at > now() - interval '24 hours' "
                    "GROUP BY purpose ORDER BY cnt DESC"
                )).mappings().all()

                return {
                    "calls_24h": total,
                    "cache_hit_rate": round(cached / total, 3) if total > 0 else 0.0,
                    "p50_ms": round(float(row["p50"])),
                    "p95_ms": round(float(row["p95"])),
                    "fallbacks": row["fallbacks"],
                    "schema_failures": 0,
                    "firewall_blocks": 0,
                    "by_purpose": {
                        r["purpose"]: {
                            "count": r["cnt"],
                            "cached": r["cached"],
                            "fallbacks": r["fallbacks"],
                        }
                        for r in purpose_rows
                    },
                }
        except Exception as e:
            log.warning("health_stats_error", error=str(e))
            return {"status": "error", "error": str(e), "calls_24h": 0}
