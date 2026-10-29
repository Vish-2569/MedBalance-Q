"""Per-hospital report style config and drug metadata."""
from __future__ import annotations

HOSPITAL_CONFIGS: dict[str, dict] = {
    "H1": {"style": "fhir", "channel": "pull", "language": "en",
            "name": "SIM-DH Jayanagar"},
    "H2": {"style": "csv", "channel": "pull", "language": "en",
            "name": "SIM-TGH Anekal"},
    "H3": {"style": "chat", "channel": "push", "language": "kn+en",
            "name": "SIM-CHC Yelahanka",
            "push_url": "http://ingest-ai:8002/ingest/H3"},
    "H4": {"style": "text", "channel": "push", "language": "en",
            "name": "SIM-PHC Hesaraghatta",
            "push_url": "http://ingest-ai:8002/ingest/H4"},
}

DRUG_INFO: dict[str, dict] = {
    "INSULIN": {
        "name": "Insulin Human 40 IU/ml", "unit": "vial", "pack_size": 1,
        "kn": "ಇನ್ಸುಲಿನ್", "csv_name": "Insulin Human 40IU/ml Inj",
        "typo": "inzulin", "chat_name": "ಇನ್ಸುಲಿನ್ 40IU",
    },
    "OXYTOCIN": {
        "name": "Oxytocin Injection 5 IU/ml", "unit": "ampoule", "pack_size": 5,
        "kn": "ಆಕ್ಸಿಟೋಸಿನ್", "csv_name": "Oxytocin Inj 5IU/ml",
        "typo": "oxytosin", "chat_name": "ಆಕ್ಸಿಟೋಸಿನ್",
    },
    "ASV": {
        "name": "Anti-Snake Venom Polyvalent", "unit": "vial", "pack_size": 1,
        "kn": "ಹಾವಿನ ವಿಷ ನಿರೋಧಕ", "csv_name": "Anti Snake Venom Polyvalent Inj",
        "typo": "anti snake venm", "chat_name": "ASV",
    },
    "TD": {
        "name": "Td Vaccine (Tetanus-Diphtheria)", "unit": "dose", "pack_size": 10,
        "kn": "ಟಿಡಿ ಲಸಿಕೆ", "csv_name": "Td Vaccine",
        "typo": "td vaccne", "chat_name": "ಟಿಡಿ ಲಸಿಕೆ",
    },
    "CEFTRIAXONE": {
        "name": "Ceftriaxone Injection 1g", "unit": "vial", "pack_size": 1,
        "kn": "ಸೆಫ್ಟ್ರಿಯಾಕ್ಸೋನ್", "csv_name": "Ceftriaxone Inj 1gm",
        "typo": "ceftriaxon", "chat_name": "ceftriaxone inj",
    },
    "RL": {
        "name": "Ringer's Lactate 500ml", "unit": "bottle", "pack_size": 1,
        "kn": "ರಿಂಗರ್ಸ್ ಲ್ಯಾಕ್ಟೇಟ್", "csv_name": "Ringer Lactate 500ml",
        "typo": "ringers lactte", "chat_name": "RL 500ml",
    },
    "ORS": {
        "name": "ORS Sachet (WHO formula)", "unit": "sachet", "pack_size": 25,
        "kn": "ಒಆರ್‌ಎಸ್", "csv_name": "ORS Packet WHO",
        "typo": "ors pkt", "chat_name": "ಒಆರ್‌ಎಸ್",
    },
    "PCM": {
        "name": "Paracetamol 500mg", "unit": "tablet", "pack_size": 10,
        "kn": "ಪ್ಯಾರಸಿಟಮಾಲ್", "csv_name": "Paracetamol 500mg Tab",
        "typo": "paracetmol", "chat_name": "ಪ್ಯಾರಸಿಟಮಾಲ್ 500",
    },
    "AMOX": {
        "name": "Amoxicillin 500mg", "unit": "capsule", "pack_size": 10,
        "kn": "ಅಮಾಕ್ಸಿಸಿಲಿನ್", "csv_name": "Amoxycillin 500mg Cap",
        "typo": "amoxy", "chat_name": "amoxy 500 cap",
    },
    "METFORMIN": {
        "name": "Metformin 500mg", "unit": "tablet", "pack_size": 10,
        "kn": "ಮೆಟ್ಫಾರ್ಮಿನ್", "csv_name": "Metformin 500mg Tab",
        "typo": "metformn", "chat_name": "ಮೆಟ್ಫಾರ್ಮಿನ್ 500",
    },
    "AMLODIPINE": {
        "name": "Amlodipine 5mg", "unit": "tablet", "pack_size": 10,
        "kn": "ಅಮ್ಲೋಡಿಪೈನ್", "csv_name": "Amlodipine 5mg Tab",
        "typo": "amlodipin", "chat_name": "ಅಮ್ಲೋಡಿಪೈನ್ 5mg",
    },
    "IFA": {
        "name": "Iron Folic Acid Tablet", "unit": "tablet", "pack_size": 100,
        "kn": "ಐಎಫ್‌ಎ", "csv_name": "Iron Folic Acid Tab",
        "typo": "iron folic acd", "chat_name": "IFA",
    },
    "MORPHINE": {
        "name": "Morphine Sulphate Injection 15mg/ml", "unit": "ampoule", "pack_size": 5,
        "kn": "ಮಾರ್ಫಿನ್", "csv_name": "Morphine Sulph Inj 15mg/ml",
        "typo": "morfine", "chat_name": "morphine inj",
    },
}
