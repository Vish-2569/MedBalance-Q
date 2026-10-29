"""Shared fixtures for ingest-ai tests."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("USE_FIXTURES", "1")


SAMPLE_FHIR = {
    "resourceType": "InventoryReport",
    "status": "current",
    "countType": "snapshot",
    "reportedDateTime": "2026-11-01T10:00:00",
    "reporter": {
        "reference": "Location/H1",
        "display": "SIM-DH Jayanagar",
    },
    "inventoryListing": [{
        "itemStatus": {"coding": [{"code": "active"}]},
        "items": [
            {
                "code": {"coding": [{"system": "http://medbal.sim/drugs", "code": "INSULIN", "display": "Insulin Human 40 IU/ml"}]},
                "quantity": {"value": 50, "unit": "vial"},
                "lot": "INS-2026-001",
                "expiry": "2027-03-15",
            },
            {
                "code": {"coding": [{"system": "http://medbal.sim/drugs", "code": "PCM", "display": "Paracetamol 500mg"}]},
                "quantity": {"value": 1000, "unit": "tablet"},
                "lot": "PCM-2026-010",
                "expiry": "2027-06-30",
            },
        ],
    }],
}


SAMPLE_CSV = (
    "Facility Code,Drug Name,Batch No,Exp Date,Qty,Unit\n"
    "H2,Paracetamol 500mg Tab,PCM-2026-010,06/2027,1000,tablet\n"
    "H2,Amoxycillin 500mg Cap,,03/2027,50,capsule\n"
    "H2,Insulin Human 40IU/ml Inj,INS-2026-005,12/2026,10,strip\n"
)
