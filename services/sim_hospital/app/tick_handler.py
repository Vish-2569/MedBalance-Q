"""Handler for clock.tick Redis stream events."""
from __future__ import annotations

import logging
import os

from . import consumption, stock_db
from .hospital_config import HOSPITAL_CONFIGS

logger = logging.getLogger(__name__)
_seed = int(os.environ.get("SIM_SEED", "42"))


def _check_bad_data() -> bool:
    try:
        from medbal_common.bus import get_redis
        r = get_redis()
        val = r.get("sim:scenario:bad_data")
        return val is not None and val not in (b"0", b"false", b"")
    except Exception:
        return False


def handle_tick(payload: dict) -> None:
    date_str = payload["date"]
    day_index = payload["day_index"]

    consumption.process_tick(date_str, day_index)

    # Update day_index for pull endpoints
    try:
        from .routers.reports import set_day_index
        set_day_index(day_index)
    except Exception:
        pass

    facility_id = stock_db.get_facility_id()
    config = HOSPITAL_CONFIGS.get(facility_id, {})

    if config.get("channel") != "push":
        return

    lots = stock_db.get_all_lots()
    text: str | None = None

    if config["style"] == "chat":
        from .reporters import chat_kn
        text = chat_kn.generate(facility_id, date_str, lots, _seed, day_index)
    elif config["style"] == "text":
        bad_data = _check_bad_data()
        from .reporters import text_messy
        text = text_messy.generate(
            facility_id, date_str, lots, _seed, day_index, bad_data=bad_data,
        )

    if text and config.get("push_url"):
        try:
            import httpx
            httpx.post(
                config["push_url"],
                json={
                    "facility_id": facility_id,
                    "date": date_str,
                    "day_index": day_index,
                    "format": config["style"],
                    "body": text,
                },
                timeout=3.0,
            )
            logger.info("Pushed %s report for %s day %d", config["style"], facility_id, day_index)
        except Exception as exc:
            logger.warning("Failed to push report for %s: %s", facility_id, exc)
