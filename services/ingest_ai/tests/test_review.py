"""Tests for the pharmacist review store."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.review import add_review, list_reviews, resolve_review, get_aliases, clear_store


@pytest.fixture(autouse=True)
def _clean():
    clear_store()
    yield
    clear_store()


SAMPLE_EXTRACTION = {
    "drug_name_raw": "Paracetamol",
    "drug_code": "PCM",
    "batch_no": "B001",
    "expiry": "2027-06-01",
    "qty": 100,
    "unit": "tablet",
    "confidence": 0.95,
    "flags": [],
}


def _add_sample(report_id: str = "rpt-1", **overrides) -> str:
    kwargs = {
        "report_id": report_id,
        "facility_code": "H1",
        "item_index": 0,
        "extraction": {**SAMPLE_EXTRACTION, **overrides.pop("extraction_override", {})},
        "anomaly_rules": ["low_confidence"],
        "explanation": "Test explanation",
    }
    kwargs.update(overrides)
    return add_review(**kwargs)


class TestAddAndList:
    def test_add_returns_id(self):
        rid = _add_sample()
        assert isinstance(rid, str) and len(rid) > 0

    def test_list_returns_added(self):
        _add_sample()
        reviews = list_reviews()
        assert len(reviews) == 1
        assert reviews[0]["status"] == "needs_review"

    def test_filter_by_status(self):
        _add_sample()
        assert len(list_reviews(status="needs_review")) == 1
        assert len(list_reviews(status="accepted")) == 0

    def test_filter_by_facility(self):
        _add_sample(facility_code="H1")
        _add_sample(facility_code="H2")
        assert len(list_reviews(facility="H1")) == 1

    def test_filter_by_drug_code(self):
        _add_sample()
        _add_sample(extraction_override={"drug_code": "INSULIN"})
        assert len(list_reviews(drug_code="PCM")) == 1


class TestResolve:
    @pytest.mark.asyncio
    async def test_accept_upserts(self):
        rid = _add_sample()

        with patch("app.review.httpx.AsyncClient") as mock_cls:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"upserted": 1}

            client = AsyncMock()
            client.post = AsyncMock(return_value=resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await resolve_review(rid, "accept")

        assert result["status"] == "accepted"
        assert result["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_reject_no_upsert(self):
        rid = _add_sample()

        result = await resolve_review(rid, "reject")
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_correct_captures_alias(self):
        rid = _add_sample(
            extraction_override={"drug_code": None, "drug_name_raw": "paracetomol"}
        )

        with patch("app.review.httpx.AsyncClient") as mock_cls:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"upserted": 1}

            client = AsyncMock()
            client.post = AsyncMock(return_value=resp)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await resolve_review(
                rid, "correct",
                corrected_values={"drug_code": "PCM", "batch_no": "B001", "expiry": "2027-06-01", "qty": 100},
            )

        assert result["status"] == "corrected"
        aliases = get_aliases()
        assert len(aliases) == 1
        assert aliases[0]["drug_code"] == "PCM"
        assert aliases[0]["alias"] == "paracetomol"

    @pytest.mark.asyncio
    async def test_not_found(self):
        result = await resolve_review("nonexistent", "accept")
        assert result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_double_resolve(self):
        rid = _add_sample()
        await resolve_review(rid, "reject")
        result = await resolve_review(rid, "accept")
        assert result["error"] == "already_resolved"

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        rid = _add_sample()
        result = await resolve_review(rid, "invalid")
        assert result["error"] == "invalid_action"
