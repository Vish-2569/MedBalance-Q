"""PDF generation for DTA vouchers, cold-chain logs, and credit memos.

Uses Jinja2 for HTML templating and WeasyPrint for PDF rendering.
QR codes generated with the qrcode library.
"""
from __future__ import annotations

import base64
import io
from datetime import date
from pathlib import Path
from typing import Any

import jinja2

from medbal_common.logging import get_logger

log = get_logger("genai.pdf")

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html"]),
)


def _generate_qr_data_uri(data: str, box_size: int = 6) -> str:
    """Generate a QR code as a data URI (PNG base64)."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=box_size, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except ImportError:
        log.warning("qrcode_not_installed")
        return ""
    except Exception as exc:
        log.warning("qr_generation_failed", error=str(exc))
        return ""


def _render_html(template_name: str, context: dict[str, Any]) -> str:
    template = _env.get_template(template_name)
    return template.render(**context)


def _html_to_pdf(html: str) -> bytes:
    """Convert HTML to PDF bytes via WeasyPrint."""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        log.warning("weasyprint_not_installed")
        return html.encode("utf-8")
    except Exception as exc:
        log.warning("pdf_render_failed", error=str(exc))
        return html.encode("utf-8")


def generate_dta_pdf(order: dict[str, Any], *, base_url: str = "") -> bytes:
    """Generate a DTA voucher PDF for a transfer order."""
    residual_days = 0
    try:
        exp = date.fromisoformat(str(order.get("expiry", ""))[:10])
        today = date.today()
        residual_days = (exp - today).days
    except (ValueError, TypeError):
        pass

    near_expiry = residual_days < 90

    items = [{
        "drug_code": order.get("drug_code", ""),
        "drug_name": order.get("drug_name", ""),
        "batch_no": order.get("batch_no", ""),
        "expiry": order.get("expiry", ""),
        "qty": order.get("qty", 0),
        "near_expiry": near_expiry,
    }]

    qr_token = order.get("qr_token", "")
    scan_url = f"{base_url}/scan/{qr_token}" if qr_token else ""
    qr_data_uri = _generate_qr_data_uri(scan_url) if scan_url else ""

    eta = ""
    transit_hours = order.get("transit_hours")
    if transit_hours:
        eta = f"{transit_hours:.1f} hours"

    context = {
        "dta_number": order.get("dta_number", ""),
        "date": order.get("created_at", str(date.today()))[:10],
        "plan_id": order.get("plan_id", ""),
        "order_id": order.get("id", ""),
        "status": order.get("status", "proposed"),
        "src_facility_id": order.get("src_facility_id", ""),
        "src_facility_name": order.get("src_facility_name", order.get("src_facility_id", "")),
        "dst_facility_id": order.get("dst_facility_id", ""),
        "dst_facility_name": order.get("dst_facility_name", order.get("dst_facility_id", "")),
        "items": items,
        "temperature_req": order.get("temperature_req", "ambient"),
        "vehicle": order.get("vehicle_id", "Assigned at dispatch"),
        "eta": eta or "Calculated at dispatch",
        "narration": order.get("narration", ""),
        "approved_by": order.get("approved_by", ""),
        "approved_at": order.get("approved_at", ""),
        "audit_hash": order.get("audit_hash", ""),
        "qr_data_uri": qr_data_uri,
        "scan_url": scan_url,
    }

    html = _render_html("dta_voucher.html", context)
    return _html_to_pdf(html)


def generate_coldchain_log_pdf(
    order: dict[str, Any],
    readings: list[dict[str, Any]],
) -> bytes:
    """Generate cold-chain consignment log PDF."""
    temps = [r.get("temp_c", 0) for r in readings if r.get("temp_c") is not None]
    breach_count = sum(
        1 for r in readings
        if r.get("temp_c") is not None and (r["temp_c"] < 2 or r["temp_c"] > 8)
    )

    for r in readings:
        t = r.get("temp_c")
        r["breach"] = t is not None and (t < 2 or t > 8)

    context = {
        "order_id": order.get("id", ""),
        "dta_number": order.get("dta_number", ""),
        "drug_name": order.get("drug_name", ""),
        "drug_code": order.get("drug_code", ""),
        "batch_no": order.get("batch_no", ""),
        "src_facility": order.get("src_facility_name", order.get("src_facility_id", "")),
        "dst_facility": order.get("dst_facility_name", order.get("dst_facility_id", "")),
        "vehicle": order.get("vehicle_id", ""),
        "temp_min": f"{min(temps):.1f}" if temps else "N/A",
        "temp_max": f"{max(temps):.1f}" if temps else "N/A",
        "reading_count": len(readings),
        "breach_count": breach_count,
        "readings": readings,
    }

    html = _render_html("coldchain_log.html", context)
    return _html_to_pdf(html)


def generate_credit_memo_pdf(
    donor_facility: dict[str, Any],
    items: list[dict[str, Any]],
    paragraph: str = "",
    plan_id: str = "",
) -> bytes:
    """Generate donor credit memo PDF."""
    total_units = sum(i.get("qty", 0) for i in items)
    total_value = sum(i.get("value_inr", 0) for i in items)

    context = {
        "date": str(date.today()),
        "plan_id": plan_id,
        "donor_facility_id": donor_facility.get("id", ""),
        "donor_facility_name": donor_facility.get("name", ""),
        "items": items,
        "total_units": total_units,
        "total_value_inr": f"{total_value:.2f}",
        "transfer_count": len(items),
        "paragraph": paragraph,
    }

    html = _render_html("credit_memo.html", context)
    return _html_to_pdf(html)


def get_qr_data_uri(data: str) -> str:
    """Public accessor for QR generation (for tests)."""
    return _generate_qr_data_uri(data)
