"""Tests for the anomaly gate."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters import ExtractionItem
from app.gate import run_gate, GateResult
from app.review import clear_store, list_reviews


@pytest.fixture(autouse=True)
def _clean_review_store():
    clear_store()
    yield
    clear_store()


def _item(**kwargs) -> ExtractionItem:
    defaults = {
        "drug_name_raw": "Paracetamol",
        "drug_code": "PCM",
        "batch_no": "B001",
        "expiry": "2027-06-01",
        "qty": 100,
        "unit": "tablet",
        "confidence": 0.95,
    }
    defaults.update(kwargs)
    return ExtractionItem(**defaults)


def _mock_context_response():
    """Mock core-api returning empty positions/lots."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = []
    return resp


def _mock_upsert_response(count: int = 1):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"upserted": count}
    return resp


def _mock_genai_response(explanation: str = "Test explanation"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"output": {"explanation": explanation}}
    return resp


class TestGateCleanItems:
    @pytest.mark.asyncio
    async def test_clean_items_forwarded(self):
        items = [_item()]
        call_log = []

        async def fake_post(url, json=None, **kw):
            call_log.append(("POST", url))
            return _mock_upsert_response(1)

        async def fake_get(url, **kw):
            return _mock_context_response()

        with patch("app.gate.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = fake_get
            client.post = fake_post
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with patch("app.gate._get_today", return_value=date(2026, 10, 29)):
                with patch("app.gate._publish_event"):
                    result = await run_gate(
                        "rpt-1", items, "H1",
                        core_api_url="http://fake:8001",
                        genai_url="http://fake:8003",
                    )

        assert result.clean_count == 1
        assert result.flagged_count == 0
        assert result.upserted == 1

    @pytest.mark.asyncio
    async def test_items_missing_fields_skip_upsert(self):
        items = [_item(batch_no=None)]

        async def fake_get(url, **kw):
            return _mock_context_response()

        with patch("app.gate.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = fake_get
            client.post = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with patch("app.gate._get_today", return_value=date(2026, 10, 29)):
                with patch("app.gate._publish_event"):
                    result = await run_gate(
                        "rpt-2", items, "H1",
                        core_api_url="http://fake:8001",
                        genai_url="http://fake:8003",
                    )

        assert result.clean_count == 1
        assert result.upserted == 0


class TestGateFlaggedItems:
    @pytest.mark.asyncio
    async def test_flagged_items_go_to_review(self):
        items = [_item(drug_code=None)]

        async def fake_get(url, **kw):
            return _mock_context_response()

        with patch("app.gate.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = fake_get
            client.post = AsyncMock(return_value=_mock_genai_response())
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with patch("app.gate._get_today", return_value=date(2026, 10, 29)):
                with patch("app.gate._publish_event"):
                    result = await run_gate(
                        "rpt-3", items, "H1",
                        core_api_url="http://fake:8001",
                        genai_url="http://fake:8003",
                    )

        assert result.flagged_count == 1
        assert len(result.review_ids) == 1
        reviews = list_reviews()
        assert len(reviews) == 1
        assert "unknown_drug" in reviews[0]["anomaly_rules"]


class TestGateResilience:
    @pytest.mark.asyncio
    async def test_core_api_failure_doesnt_crash(self):
        items = [_item()]

        with patch("app.gate.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=Exception("connection refused"))
            client.post = AsyncMock(side_effect=Exception("connection refused"))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with patch("app.gate._get_today", return_value=date(2026, 10, 29)):
                with patch("app.gate._publish_event"):
                    result = await run_gate(
                        "rpt-4", items, "H1",
                        core_api_url="http://fake:8001",
                        genai_url="http://fake:8003",
                    )

        assert result.clean_count == 1
        assert result.upserted == 0

    @pytest.mark.asyncio
    async def test_mixed_clean_and_flagged(self):
        items = [_item(), _item(drug_code=None, drug_name_raw="mystery")]

        async def fake_get(url, **kw):
            return _mock_context_response()

        with patch("app.gate.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get = fake_get
            client.post = AsyncMock(return_value=_mock_upsert_response(1))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            with patch("app.gate._get_today", return_value=date(2026, 10, 29)):
                with patch("app.gate._publish_event"):
                    result = await run_gate(
                        "rpt-5", items, "H1",
                        core_api_url="http://fake:8001",
                        genai_url="http://fake:8003",
                    )

        assert result.clean_count == 1
        assert result.flagged_count == 1
