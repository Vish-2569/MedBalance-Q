
"""Hospital report adapters: deterministic parsers for FHIR/CSV, raw storage for Chat/Text."""
from __future__ import annotations

import csv
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from medbal_common import clock


@dataclass
class ExtractionItem:
    drug_name_raw: str
    drug_code: str | None = None
    batch_no: str | None = None
    expiry: str | None = None
    qty: int | None = None
    unit: str | None = None
    confidence: float = 1.0
    flags: list[str] = field(default_factory=list)

    grounding_score: int = 0
    grounding_method: str = ""
    extraction_method: str = "genai"

    def to_dict(self) -> dict:
        d = {
            "drug_name_raw": self.drug_name_raw,
            "drug_code": self.drug_code,
            "batch_no": self.batch_no,
            "expiry": self.expiry,
            "qty": self.qty,
            "unit": self.unit,
            "confidence": self.confidence,
            "flags": self.flags,
            "extraction_method": self.extraction_method,
        }
        if self.grounding_score:
            d["grounding_score"] = self.grounding_score
            d["grounding_method"] = self.grounding_method
        return d


@dataclass
class StockReport:
    facility_code: str
    reported_at: str
    format: str
    items: list[ExtractionItem]
    raw_text: str | None = None
    extraction_method: str | None = None
    extraction_warning: str | None = None

    def to_dict(self) -> dict:
        report = {
            "facility_code": self.facility_code,
            "reported_at": self.reported_at,
            "format": self.format,
            "raw_text": self.raw_text,
            "items": [i.to_dict() for i in self.items],
        }
        if self.extraction_method:
            report["extraction_method"] = self.extraction_method
        if self.extraction_warning:
            report["extraction_warning"] = self.extraction_warning
        return report


class ReportAdapter(ABC):
    @abstractmethod
    def parse(self, facility_code: str, payload: dict | str) -> StockReport:
        ...


class FhirAdapter(ReportAdapter):
    """Deterministic parser for FHIR R5 InventoryReport JSON (H1)."""

    def parse(self, facility_code: str, payload: dict | str) -> StockReport:
        if isinstance(payload, str):
            import json
            payload = json.loads(payload)

        reported_at = payload.get("reportedDateTime", clock.now().isoformat())
        items: list[ExtractionItem] = []

        for listing in payload.get("inventoryListing", []):
            for item in listing.get("items", []):
                code_block = item.get("code", {})
                codings = code_block.get("coding", [])
                drug_code = codings[0].get("code") if codings else None
                display = codings[0].get("display", "") if codings else ""

                quantity = item.get("quantity", {})
                qty_val = quantity.get("value")
                unit = quantity.get("unit")

                batch_no = item.get("lot")
                expiry = item.get("expiry")

                items.append(ExtractionItem(
                    drug_name_raw=display,
                    drug_code=drug_code,
                    batch_no=batch_no,
                    expiry=expiry,
                    qty=int(qty_val) if qty_val is not None else None,
                    unit=unit,
                    confidence=1.0,
                    flags=[],
                ))

        return StockReport(
            facility_code=facility_code,
            reported_at=reported_at,
            format="fhir",
            items=items,
        )


class CsvAdapter(ReportAdapter):
    """Deterministic parser for e-Aushadhi CSV reports (H2)."""

    def parse(self, facility_code: str, payload: dict | str) -> StockReport:
        if not isinstance(payload, str):
            raise ValueError("CsvAdapter expects a CSV string payload")

        reader = csv.DictReader(io.StringIO(payload))
        items: list[ExtractionItem] = []

        for row in reader:
            drug_name = row.get("Drug Name", "").strip()
            batch_no = row.get("Batch No", "").strip() or None
            exp_raw = row.get("Exp Date", "").strip()
            qty_raw = row.get("Qty", "").strip()
            unit = row.get("Unit", "").strip()

            expiry = _parse_csv_expiry(exp_raw)

            qty: int | None = None
            if qty_raw:
                try:
                    qty = int(qty_raw)
                except ValueError:
                    qty = None

            flags: list[str] = []
            if unit == "strip":
                flags.append("unit_conversion_needed")

            items.append(ExtractionItem(
                drug_name_raw=drug_name,
                drug_code=None,
                batch_no=batch_no,
                expiry=expiry,
                qty=qty,
                unit=unit,
                confidence=0.9,
                flags=flags,
            ))

        return StockReport(
            facility_code=facility_code,
            reported_at=clock.now().isoformat(),
            format="csv",
            items=items,
            raw_text=payload,
        )


class ChatAdapter(ReportAdapter):
    """Raw storage for Kannada+English chat messages (H3). LLM extraction in P08b."""

    def parse(self, facility_code: str, payload: dict | str) -> StockReport:
        if isinstance(payload, dict):
            raw = str(payload.get("body") or "")
            reported_at = str(payload.get("date") or clock.now().isoformat())
        else:
            raw = payload
            reported_at = clock.now().isoformat()
        return StockReport(
            facility_code=facility_code,
            reported_at=reported_at,
            format="chat",
            items=[],
            raw_text=_repair_utf8_mojibake(raw),
        )


class TextAdapter(ReportAdapter):
    """Raw storage for messy English text reports (H4). LLM extraction in P08b."""

    def parse(self, facility_code: str, payload: dict | str) -> StockReport:
        if isinstance(payload, dict):
            raw = str(payload.get("body") or "")
            reported_at = str(payload.get("date") or clock.now().isoformat())
        else:
            raw = payload
            reported_at = clock.now().isoformat()
        return StockReport(
            facility_code=facility_code,
            reported_at=reported_at,
            format="text",
            items=[],
            raw_text=_repair_utf8_mojibake(raw),
        )


def _repair_utf8_mojibake(raw: str) -> str:
    if "à²" not in raw and "à³" not in raw:
        return raw
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


ADAPTER_REGISTRY: dict[str, ReportAdapter] = {
    "fhir": FhirAdapter(),
    "csv": CsvAdapter(),
    "chat": ChatAdapter(),
    "text": TextAdapter(),
}

FACILITY_STYLE: dict[str, str] = {
    "H1": "fhir",
    "H2": "csv",
    "H3": "chat",
    "H4": "text",
}


def get_adapter(facility_code: str) -> ReportAdapter:
    style = FACILITY_STYLE.get(facility_code)
    if style and style in ADAPTER_REGISTRY:
        return ADAPTER_REGISTRY[style]
    raise ValueError(f"No adapter registered for facility {facility_code}")


def _parse_csv_expiry(raw: str) -> str | None:
    """Convert MM/YYYY to YYYY-MM-01, pass through YYYY-MM-DD as-is."""
    if not raw:
        return None
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 2:
            month, year = parts
            try:
                return f"{year}-{int(month):02d}-01"
            except ValueError:
                return None
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return None
