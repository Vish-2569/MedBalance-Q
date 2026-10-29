"""H1-style FHIR R5 InventoryReport generator."""
from __future__ import annotations

from ..hospital_config import DRUG_INFO, HOSPITAL_CONFIGS


def generate(facility_id: str, date_str: str, lots: list[dict]) -> dict:
    config = HOSPITAL_CONFIGS.get(facility_id, {})
    display = config.get("name", facility_id)

    items = []
    for lot in lots:
        dc = lot["drug_code"]
        info = DRUG_INFO.get(dc, {})
        if lot.get("qty", 0) <= 0 and lot.get("status") == "expired":
            continue
        items.append({
            "category": {"coding": [{"code": "medication"}]},
            "code": {
                "coding": [{
                    "system": "http://medbal.sim/drugs",
                    "code": dc,
                    "display": info.get("name", dc),
                }]
            },
            "quantity": {
                "value": lot["qty"],
                "unit": info.get("unit", "unit"),
            },
            "lot": lot["batch_no"],
            "expiry": lot["expiry"],
        })

    return {
        "resourceType": "InventoryReport",
        "status": "current",
        "countType": "snapshot",
        "reportedDateTime": date_str,
        "reporter": {
            "reference": f"Location/{facility_id}",
            "display": display,
        },
        "inventoryListing": [{
            "itemStatus": {"coding": [{"code": "active"}]},
            "items": items,
        }],
    }
