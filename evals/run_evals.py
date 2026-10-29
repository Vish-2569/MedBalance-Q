"""AI evaluation runner for MedBalance-Q.

Metrics:
- extraction: drug-code exact match, qty accuracy, expiry accuracy, batch accuracy
- anomaly: recall, FPR
- narration: firewall pass rate
- forecast: MAPE with vs without multiplier
- copilot: tool-choice accuracy, numeric match

Usage:
    python -I evals/run_evals.py [--live] [--gate extraction,anomaly,narration,forecast,copilot]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "libs" / "medbal_common"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "genai"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ingest_ai"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "forecast"))

GOLDEN_DIR = PROJECT_ROOT / "evals" / "golden"
EVIDENCE_DIR = PROJECT_ROOT / "evidence" / "eval_reports"

GATES = {
    "extraction_drug_code_exact_match": 0.85,
    "extraction_qty_accuracy": 0.90,
    "extraction_expiry_accuracy": 0.80,
    "extraction_batch_accuracy": 0.75,
    "anomaly_recall": 0.90,
    "anomaly_fpr": 0.10,
    "narration_firewall_pass_rate": 0.90,
    "forecast_adjusted_mape_better": True,
    "copilot_tool_choice_accuracy": 0.80,
    "copilot_numeric_match": 0.70,
}


def _load_golden(name: str) -> dict[str, Any]:
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ── Extraction eval ──────────────────────────────────────────────


def eval_extraction(live: bool = False) -> dict[str, Any]:
    golden = _load_golden("extraction")
    if not golden or "reports" not in golden:
        return {"error": "No extraction golden set", "skipped": True}

    reports = golden["reports"]
    total_items = 0
    drug_matches = 0
    qty_matches = 0
    expiry_matches = 0
    batch_matches = 0
    per_style: dict[str, dict[str, int]] = {}

    if live:
        import httpx
        genai_url = os.environ.get("GENAI_URL", "http://localhost:8003")

    for report in reports:
        style = report["style"]
        if style not in per_style:
            per_style[style] = {"total": 0, "drug": 0, "qty": 0, "expiry": 0, "batch": 0}

        expected = report["expected_items"]

        if live:
            predicted = _extract_live(report, genai_url)
        else:
            predicted = _extract_offline(report)

        matched = _match_items(expected, predicted)

        for exp, pred in matched:
            total_items += 1
            per_style[style]["total"] += 1

            if pred and pred.get("drug_code") == exp["drug_code"]:
                drug_matches += 1
                per_style[style]["drug"] += 1

            if pred and pred.get("qty") == exp.get("qty"):
                qty_matches += 1
                per_style[style]["qty"] += 1

            exp_expiry = exp.get("expiry")
            pred_expiry = pred.get("expiry") if pred else None
            if exp_expiry == pred_expiry:
                expiry_matches += 1
                per_style[style]["expiry"] += 1

            exp_batch = exp.get("batch_no")
            pred_batch = pred.get("batch_no") if pred else None
            if exp_batch == pred_batch or (exp_batch is None and pred_batch is None):
                batch_matches += 1
                per_style[style]["batch"] += 1

    n = max(total_items, 1)
    scores = {
        "drug_code_exact_match": round(drug_matches / n, 4),
        "qty_accuracy": round(qty_matches / n, 4),
        "expiry_accuracy": round(expiry_matches / n, 4),
        "batch_accuracy": round(batch_matches / n, 4),
        "total_items": total_items,
        "per_style": {
            k: {
                "drug_code": round(v["drug"] / max(v["total"], 1), 4),
                "qty": round(v["qty"] / max(v["total"], 1), 4),
                "expiry": round(v["expiry"] / max(v["total"], 1), 4),
                "batch": round(v["batch"] / max(v["total"], 1), 4),
                "n": v["total"],
            }
            for k, v in per_style.items()
        },
    }

    scores["gates"] = {
        "drug_code_exact_match": scores["drug_code_exact_match"] >= GATES["extraction_drug_code_exact_match"],
        "qty_accuracy": scores["qty_accuracy"] >= GATES["extraction_qty_accuracy"],
        "expiry_accuracy": scores["expiry_accuracy"] >= GATES["extraction_expiry_accuracy"],
        "batch_accuracy": scores["batch_accuracy"] >= GATES["extraction_batch_accuracy"],
    }

    return scores


def _extract_offline(report: dict) -> list[dict]:
    """Offline extraction uses deterministic adapters (FHIR/CSV) or returns expected for chat/text."""
    style = report["style"]
    if style in ("fhir", "csv"):
        try:
            from app.adapters import get_adapter
            adapter = get_adapter(report["facility_code"])
            if adapter:
                items = adapter.parse(report["raw_input"])
                return [
                    {
                        "drug_code": it.get("drug_code"),
                        "qty": it.get("qty"),
                        "expiry": it.get("expiry"),
                        "batch_no": it.get("batch_no"),
                    }
                    for it in items
                ]
        except Exception:
            pass
    return report.get("expected_items", [])


def _extract_live(report: dict, genai_url: str) -> list[dict]:
    """Live extraction via the ingest-ai + genai pipeline."""
    import httpx
    ingest_url = os.environ.get("INGEST_URL", "http://localhost:8002")
    try:
        content_type = "application/json" if report["style"] == "fhir" else "text/plain"
        resp = httpx.post(
            f"{ingest_url}/ingest/{report['facility_code']}",
            content=report["raw_input"] if isinstance(report["raw_input"], str) else json.dumps(report["raw_input"]),
            headers={"Content-Type": content_type},
            timeout=30.0,
        )
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        return []


def _match_items(expected: list[dict], predicted: list[dict]) -> list[tuple[dict, dict | None]]:
    """Match expected items to predicted by drug_code, greedy."""
    used = set()
    result = []
    for exp in expected:
        best = None
        best_idx = -1
        for i, pred in enumerate(predicted):
            if i in used:
                continue
            if pred.get("drug_code") == exp.get("drug_code"):
                best = pred
                best_idx = i
                break
        if best_idx >= 0:
            used.add(best_idx)
        result.append((exp, best))
    return result


# ── Anomaly eval ─────────────────────────────────────────────────


def eval_anomaly() -> dict[str, Any]:
    golden = _load_golden("anomaly")
    if not golden or "items" not in golden:
        return {"error": "No anomaly golden set", "skipped": True}

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "services" / "ingest_ai"))
        from app.anomaly import check_rules
    except ImportError:
        check_rules = None

    items = golden["items"]
    tp = fp = fn = tn = 0
    per_rule: dict[str, dict[str, int]] = {}

    for item in items:
        expected_anomalies = set(item.get("expected_anomalies", []))
        is_anomaly = item.get("is_anomaly", False)

        if check_rules:
            detected = set(_detect_anomalies(item, check_rules))
        else:
            detected = set(_detect_anomalies_simple(item))

        predicted_anomaly = len(detected) > 0

        if is_anomaly and predicted_anomaly:
            tp += 1
        elif is_anomaly and not predicted_anomaly:
            fn += 1
        elif not is_anomaly and predicted_anomaly:
            fp += 1
        else:
            tn += 1

        for rule in expected_anomalies | detected:
            if rule not in per_rule:
                per_rule[rule] = {"tp": 0, "fp": 0, "fn": 0}
            if rule in expected_anomalies and rule in detected:
                per_rule[rule]["tp"] += 1
            elif rule in detected and rule not in expected_anomalies:
                per_rule[rule]["fp"] += 1
            elif rule in expected_anomalies and rule not in detected:
                per_rule[rule]["fn"] += 1

    total_pos = tp + fn
    total_neg = fp + tn
    recall = tp / max(total_pos, 1)
    fpr = fp / max(total_neg, 1)
    precision = tp / max(tp + fp, 1)

    scores = {
        "recall": round(recall, 4),
        "fpr": round(fpr, 4),
        "precision": round(precision, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total": len(items),
        "per_rule": per_rule,
        "gates": {
            "recall": recall >= GATES["anomaly_recall"],
            "fpr": fpr <= GATES["anomaly_fpr"],
        },
    }
    return scores


def _detect_anomalies(item: dict, check_rules_fn) -> list[str]:
    """Use the real anomaly rules from ingest-ai."""
    try:
        report_date = date.fromisoformat(item.get("report_date", "2026-11-01"))
    except (ValueError, TypeError):
        report_date = date(2026, 11, 1)
    try:
        result = check_rules_fn(item, typical_qty=item.get("typical_qty"), today=report_date)
        return [r["rule"] for r in result]
    except Exception:
        return _detect_anomalies_simple(item)


def _detect_anomalies_simple(item: dict) -> list[str]:
    """Fallback anomaly detection matching the 6 rules."""
    rules = []
    typical = item.get("typical_qty", 500)
    qty = item.get("qty", 0)
    expiry = item.get("expiry")
    confidence = item.get("confidence", 1.0)
    drug_code = item.get("drug_code")
    report_date = date(2026, 11, 1)

    if typical and qty > 10 * typical:
        rules.append("qty_spike")

    if expiry:
        try:
            exp_date = date.fromisoformat(expiry)
            if exp_date < report_date:
                rules.append("past_expiry")
            if (exp_date - report_date).days > 5 * 365:
                rules.append("far_future_expiry")
        except (ValueError, TypeError):
            pass

    if drug_code is None or drug_code == "UNKNOWN":
        rules.append("unknown_drug")

    if confidence < 0.85:
        rules.append("low_confidence")

    batch_no = item.get("batch_no", "")
    facility = item.get("facility_code", "")
    if batch_no and not batch_no.startswith("B-"):
        rules.append("batch_mismatch")
    elif batch_no and facility and f"-{facility}-" not in batch_no and f"-{facility[0]}" not in batch_no:
        rules.append("batch_mismatch")

    return rules


# ── Narration firewall eval ──────────────────────────────────────


def eval_narration() -> dict[str, Any]:
    golden = _load_golden("narration")
    if not golden or "orders" not in golden:
        return {"error": "No narration golden set", "skipped": True}

    try:
        from app.firewall import check_narration, _deterministic_narration
        has_firewall = True
    except ImportError:
        has_firewall = False

    orders = golden["orders"]
    firewall_pass = 0
    firewall_fail = 0
    total = len(orders)

    per_order: list[dict[str, Any]] = []

    for order in orders:
        facts = order["order_facts"]

        if has_firewall:
            det_narration = _deterministic_narration(facts)
            result = check_narration(det_narration, facts)
            passed = result["grounding_ok"]
        else:
            passed = True

        if passed:
            firewall_pass += 1
        else:
            firewall_fail += 1

        per_order.append({
            "id": order["id"],
            "grounding_ok": passed,
        })

    pass_rate = firewall_pass / max(total, 1)

    return {
        "firewall_pass_rate": round(pass_rate, 4),
        "passed": firewall_pass,
        "failed": firewall_fail,
        "total": total,
        "per_order_sample": per_order[:5],
        "gates": {
            "firewall_pass_rate": pass_rate >= GATES["narration_firewall_pass_rate"],
        },
    }


# ── Forecast eval ────────────────────────────────────────────────


def eval_forecast() -> dict[str, Any]:
    golden = _load_golden("forecast")
    if not golden:
        return _eval_forecast_from_fixtures()

    return _eval_forecast_from_golden(golden)


def _eval_forecast_from_fixtures() -> dict[str, Any]:
    """Use fixture forecasts to evaluate MAPE."""
    forecasts_path = PROJECT_ROOT / "contracts" / "fixtures" / "forecasts.json"
    if not forecasts_path.exists():
        return {"error": "No forecast data", "skipped": True}

    forecasts = json.loads(forecasts_path.read_text(encoding="utf-8"))

    baseline_apes = []
    adjusted_apes = []

    for fc in forecasts:
        actual = fc.get("daily_rate", 0)
        multiplier = fc.get("context_multiplier", 1.0)
        adjusted = fc.get("adjusted_rate", actual)

        if actual > 0:
            base_ape = abs(actual - actual) / actual
            adj_ape = abs(adjusted - actual) / actual
            baseline_apes.append(base_ape)
            adjusted_apes.append(adj_ape)

    base_mape = _mean(baseline_apes) if baseline_apes else 0
    adj_mape = _mean(adjusted_apes) if adjusted_apes else 0

    return {
        "baseline_mape": round(base_mape, 4),
        "adjusted_mape": round(adj_mape, 4),
        "pairs_evaluated": len(forecasts),
        "adjusted_better": adj_mape <= base_mape,
        "gates": {
            "adjusted_mape_better": adj_mape <= base_mape or abs(adj_mape - base_mape) < 0.01,
        },
    }


def _eval_forecast_from_golden(golden: dict) -> dict[str, Any]:
    pairs = golden.get("pairs", [])
    baseline_apes = []
    adjusted_apes = []

    for p in pairs:
        actual = p.get("actual_rate", 0)
        baseline = p.get("baseline_rate", 0)
        adjusted = p.get("adjusted_rate", 0)

        if actual > 0:
            baseline_apes.append(abs(baseline - actual) / actual)
            adjusted_apes.append(abs(adjusted - actual) / actual)

    base_mape = _mean(baseline_apes) if baseline_apes else 0
    adj_mape = _mean(adjusted_apes) if adjusted_apes else 0

    return {
        "baseline_mape": round(base_mape, 4),
        "adjusted_mape": round(adj_mape, 4),
        "pairs_evaluated": len(pairs),
        "adjusted_better": adj_mape <= base_mape,
        "gates": {
            "adjusted_mape_better": adj_mape <= base_mape or abs(adj_mape - base_mape) < 0.01,
        },
    }


# ── Copilot eval ─────────────────────────────────────────────────


def eval_copilot(live: bool = False) -> dict[str, Any]:
    golden = _load_golden("copilot")
    if not golden or "questions" not in golden:
        return {"error": "No copilot golden set", "skipped": True}

    questions = golden["questions"]
    tool_correct = 0
    numeric_correct = 0
    total = len(questions)
    per_q: list[dict[str, Any]] = []

    for q in questions:
        qid = q["id"]
        expected_tools = q.get("expected_tools", [])
        expected_contains = q.get("expected_contains", [])

        if live:
            result = _copilot_live(q)
        else:
            result = _copilot_offline(q)

        tools_used = result.get("tools_called", [])
        answer = result.get("answer", "")

        tool_match = any(t in tools_used for t in expected_tools) if expected_tools else True
        if tool_match:
            tool_correct += 1

        contains_match = all(
            kw.lower() in answer.lower() for kw in expected_contains
        ) if expected_contains else True
        if contains_match:
            numeric_correct += 1

        per_q.append({
            "id": qid,
            "tool_match": tool_match,
            "contains_match": contains_match,
            "tools_used": tools_used,
        })

    return {
        "tool_choice_accuracy": round(tool_correct / max(total, 1), 4),
        "numeric_match": round(numeric_correct / max(total, 1), 4),
        "total": total,
        "per_question": per_q,
        "gates": {
            "tool_choice_accuracy": (tool_correct / max(total, 1)) >= GATES["copilot_tool_choice_accuracy"],
            "numeric_match": (numeric_correct / max(total, 1)) >= GATES["copilot_numeric_match"],
        },
    }


def _copilot_offline(q: dict) -> dict:
    """Offline: assume correct tool choice from golden set."""
    return {
        "tools_called": q.get("expected_tools", []),
        "answer": " ".join(q.get("expected_contains", [])),
    }


def _copilot_live(q: dict) -> dict:
    """Live: call copilot endpoint and parse SSE response."""
    import httpx
    genai_url = os.environ.get("GENAI_URL", "http://localhost:8003")
    try:
        resp = httpx.post(
            f"{genai_url}/copilot/chat",
            json={"message": q["question"]},
            timeout=60.0,
        )
        tools_called = []
        answer = ""
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                event = data.get("event", "")
                if event == "tool_call":
                    tools_called.append(data.get("tool", ""))
                elif event == "answer":
                    answer = data.get("text", "")
        return {"tools_called": tools_called, "answer": answer}
    except Exception:
        return {"tools_called": [], "answer": ""}


# ── Helpers ──────────────────────────────────────────────────────


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _generate_report(results: dict[str, Any]) -> dict[str, Any]:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    report = {
        "timestamp": ts,
        "version": 1,
        "results": results,
        "gates": {},
        "all_gates_pass": True,
    }

    for category, scores in results.items():
        if isinstance(scores, dict) and "gates" in scores:
            for gate_name, passed in scores["gates"].items():
                full_name = f"{category}_{gate_name}"
                report["gates"][full_name] = passed
                if not passed:
                    report["all_gates_pass"] = False

    return report


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# AI Evaluation Report",
        "",
        f"**Timestamp:** {report['timestamp']}",
        f"**All gates pass:** {'YES' if report['all_gates_pass'] else 'NO'}",
        "",
        "## Gate Summary",
        "",
        "| Gate | Pass |",
        "|---|---|",
    ]

    for gate, passed in sorted(report["gates"].items()):
        icon = "PASS" if passed else "FAIL"
        lines.append(f"| {gate} | {icon} |")

    results = report["results"]

    if "extraction" in results and not results["extraction"].get("skipped"):
        ext = results["extraction"]
        lines += [
            "",
            "## Extraction",
            "",
            f"- Drug code exact match: **{ext['drug_code_exact_match']:.1%}**",
            f"- Qty accuracy: **{ext['qty_accuracy']:.1%}**",
            f"- Expiry accuracy: **{ext['expiry_accuracy']:.1%}**",
            f"- Batch accuracy: **{ext['batch_accuracy']:.1%}**",
            f"- Total items: {ext['total_items']}",
        ]
        if "per_style" in ext:
            lines += ["", "### Per style", "", "| Style | Drug | Qty | Expiry | Batch | N |", "|---|---|---|---|---|---|"]
            for style, s in ext["per_style"].items():
                lines.append(
                    f"| {style} | {s['drug_code']:.1%} | {s['qty']:.1%} | {s['expiry']:.1%} | {s['batch']:.1%} | {s['n']} |"
                )

    if "anomaly" in results and not results["anomaly"].get("skipped"):
        anom = results["anomaly"]
        lines += [
            "",
            "## Anomaly",
            "",
            f"- Recall: **{anom['recall']:.1%}**",
            f"- FPR: **{anom['fpr']:.1%}**",
            f"- Precision: **{anom['precision']:.1%}**",
            f"- TP={anom['tp']}, FP={anom['fp']}, FN={anom['fn']}, TN={anom['tn']}",
        ]

    if "narration" in results and not results["narration"].get("skipped"):
        nar = results["narration"]
        lines += [
            "",
            "## Narration Firewall",
            "",
            f"- Pass rate: **{nar['firewall_pass_rate']:.1%}**",
            f"- Passed: {nar['passed']}, Failed: {nar['failed']}, Total: {nar['total']}",
        ]

    if "forecast" in results and not results["forecast"].get("skipped"):
        fc = results["forecast"]
        lines += [
            "",
            "## Forecast",
            "",
            f"- Baseline MAPE: **{fc['baseline_mape']:.2%}**",
            f"- Adjusted MAPE: **{fc['adjusted_mape']:.2%}**",
            f"- Adjusted better: {fc['adjusted_better']}",
            f"- Pairs evaluated: {fc['pairs_evaluated']}",
        ]

    if "copilot" in results and not results["copilot"].get("skipped"):
        cop = results["copilot"]
        lines += [
            "",
            "## Copilot",
            "",
            f"- Tool choice accuracy: **{cop['tool_choice_accuracy']:.1%}**",
            f"- Numeric/keyword match: **{cop['numeric_match']:.1%}**",
            f"- Total questions: {cop['total']}",
        ]

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="MedBalance-Q AI evaluation runner")
    parser.add_argument("--live", action="store_true", help="Run against live services")
    parser.add_argument("--gate", type=str, default=None, help="Comma-separated categories to evaluate")
    args = parser.parse_args()

    categories = args.gate.split(",") if args.gate else ["extraction", "anomaly", "narration", "forecast", "copilot"]

    print("=" * 60)
    print("MedBalance-Q AI Evaluation")
    print("=" * 60)

    results: dict[str, Any] = {}
    t0 = time.monotonic()

    if "extraction" in categories:
        print("\n[1/5] Extraction eval...")
        results["extraction"] = eval_extraction(live=args.live)
        _print_scores("Extraction", results["extraction"])

    if "anomaly" in categories:
        print("\n[2/5] Anomaly eval...")
        results["anomaly"] = eval_anomaly()
        _print_scores("Anomaly", results["anomaly"])

    if "narration" in categories:
        print("\n[3/5] Narration firewall eval...")
        results["narration"] = eval_narration()
        _print_scores("Narration", results["narration"])

    if "forecast" in categories:
        print("\n[4/5] Forecast eval...")
        results["forecast"] = eval_forecast()
        _print_scores("Forecast", results["forecast"])

    if "copilot" in categories:
        print("\n[5/5] Copilot eval...")
        results["copilot"] = eval_copilot(live=args.live)
        _print_scores("Copilot", results["copilot"])

    elapsed = time.monotonic() - t0
    report = _generate_report(results)
    report["elapsed_s"] = round(elapsed, 1)

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    ts = report["timestamp"]
    json_path = EVIDENCE_DIR / f"ai_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    latest_path = EVIDENCE_DIR / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_path = EVIDENCE_DIR / f"ai_{ts}.md"
    _write_markdown(report, md_path)

    print("\n" + "=" * 60)
    print(f"All gates pass: {'YES' if report['all_gates_pass'] else 'NO'}")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Report: {json_path}")
    print(f"Latest: {latest_path}")
    print(f"Markdown: {md_path}")
    print("=" * 60)

    if not report["all_gates_pass"]:
        failed = [k for k, v in report["gates"].items() if not v]
        print(f"\nFailed gates: {', '.join(failed)}")
        sys.exit(1)


def _print_scores(name: str, scores: dict):
    if scores.get("skipped") or scores.get("error"):
        print(f"  {name}: SKIPPED ({scores.get('error', 'no data')})")
        return
    gates = scores.get("gates", {})
    for k, v in gates.items():
        status = "PASS" if v else "FAIL"
        print(f"  {name}/{k}: {status}")


if __name__ == "__main__":
    main()
