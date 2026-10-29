"""Labelling helper for extraction golden set.

Pre-fills extraction labels from the current extractor so a human only
corrects mistakes. Works with reports saved in contracts/fixtures or
from sim-hospital outputs.

Usage:
    python -I evals/label_helper.py --input reports.jsonl --output evals/golden/extraction.json
    python -I evals/label_helper.py --generate  # generate from sim-hospital reporter code
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "libs" / "medbal_common"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ingest_ai"))

GOLDEN_DIR = PROJECT_ROOT / "evals" / "golden"
DRUGS_PATH = PROJECT_ROOT / "data" / "seed" / "drugs.yaml"


def _load_drug_map() -> dict[str, dict]:
    """Load drug metadata from seed YAML."""
    try:
        import yaml
        raw = yaml.safe_load(DRUGS_PATH.read_text(encoding="utf-8"))
        return {d["code"]: d for d in raw}
    except Exception:
        return {}


def _prefill_fhir(raw_input: str) -> list[dict]:
    """Deterministic FHIR extraction."""
    try:
        from app.adapters import FhirAdapter
        adapter = FhirAdapter()
        items = adapter.parse(raw_input)
        return [
            {
                "drug_code": it.get("drug_code"),
                "qty": it.get("qty"),
                "unit": it.get("unit"),
                "batch_no": it.get("batch_no"),
                "expiry": it.get("expiry"),
            }
            for it in items
        ]
    except Exception as e:
        print(f"  FHIR prefill failed: {e}")
        return []


def _prefill_csv(raw_input: str) -> list[dict]:
    """Deterministic CSV extraction."""
    try:
        from app.adapters import CsvAdapter
        adapter = CsvAdapter()
        items = adapter.parse(raw_input)
        return [
            {
                "drug_code": it.get("drug_code"),
                "qty": it.get("qty"),
                "unit": it.get("unit"),
                "batch_no": it.get("batch_no"),
                "expiry": it.get("expiry"),
            }
            for it in items
        ]
    except Exception as e:
        print(f"  CSV prefill failed: {e}")
        return []


def _prefill_text(raw_input: str, facility_code: str) -> list[dict]:
    """Try grounding-based prefill for chat/text."""
    try:
        from app.grounding import ground_drug
        from app.extraction import scan_text_for_mentions

        mentions = scan_text_for_mentions(raw_input)
        return [
            {
                "drug_code": m.get("drug_code"),
                "qty": None,
                "unit": None,
                "batch_no": None,
                "expiry": None,
                "needs_review": True,
            }
            for m in mentions
            if m.get("drug_code")
        ]
    except Exception as e:
        print(f"  Text prefill failed: {e}")
        return []


def prefill_report(report: dict) -> list[dict]:
    """Pre-fill extraction labels from the current extractor."""
    style = report.get("style", "")
    raw = report.get("raw_input", "")
    facility = report.get("facility_code", "")

    if style == "fhir":
        return _prefill_fhir(raw)
    elif style == "csv":
        return _prefill_csv(raw)
    else:
        return _prefill_text(raw, facility)


def label_from_file(input_path: Path, output_path: Path):
    """Read reports, pre-fill labels, write golden set."""
    reports = []

    if input_path.suffix == ".jsonl":
        for line in input_path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                reports.append(json.loads(line))
    else:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            reports = data
        elif "reports" in data:
            reports = data["reports"]

    golden_reports = []
    for i, report in enumerate(reports):
        prefilled = prefill_report(report)
        golden_reports.append({
            "id": report.get("id", f"ext-{i+1:03d}"),
            "facility_code": report.get("facility_code", ""),
            "style": report.get("style", report.get("format", "")),
            "report_date": report.get("report_date", report.get("received_at", "")[:10]),
            "raw_input": report.get("raw_input", report.get("raw_text", "")),
            "expected_items": prefilled,
            "_needs_human_review": any(it.get("needs_review") for it in prefilled),
        })
        print(f"  Report {i+1}: {len(prefilled)} items pre-filled")

    golden = {
        "version": 1,
        "description": "Golden extraction evaluation set (pre-filled, needs human review)",
        "reports": golden_reports,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(golden, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(golden_reports)} reports to {output_path}")

    review_count = sum(1 for r in golden_reports if r.get("_needs_human_review"))
    if review_count:
        print(f"  {review_count} reports need human review (chat/text with qty/expiry)")


def main():
    parser = argparse.ArgumentParser(description="Pre-fill extraction labels for golden set")
    parser.add_argument("--input", type=Path, help="Input reports (JSON or JSONL)")
    parser.add_argument("--output", type=Path, default=GOLDEN_DIR / "extraction.json")
    parser.add_argument("--generate", action="store_true",
                        help="Generate synthetic reports using sim-hospital reporter code")
    args = parser.parse_args()

    if args.generate:
        print("Generating synthetic reports from sim-hospital reporters...")
        print("This requires the sim-hospital code to be importable.")
        print("Use: python -I evals/label_helper.py --input <reports.json> --output evals/golden/extraction.json")
        sys.exit(1)

    if not args.input:
        print("Usage: python -I evals/label_helper.py --input <reports.json>")
        sys.exit(1)

    label_from_file(args.input, args.output)


if __name__ == "__main__":
    main()
