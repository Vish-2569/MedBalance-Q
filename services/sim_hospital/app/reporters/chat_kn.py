"""H3-style Kannada+English chat message report generator."""
from __future__ import annotations

import hashlib

from ..hospital_config import DRUG_INFO

GREETINGS = [
    "ನಮಸ್ಕಾರ ಸರ್, ಇವತ್ತಿನ stock update:",
    "ಸರ್ ನಮಸ್ಕಾರ, ಈ ದಿನದ ಸ್ಟಾಕ್ ವಿವರ:",
    "Good morning sir, ಇವತ್ತಿನ stock report ಕಳಿಸ್ತೀನಿ:",
    "ಹಲೋ ಸರ್, ಇಂದಿನ ಔಷಧಿ stock update:",
    "ನಮಸ್ಕಾರ, today stock position ಕಳಿಸ್ತಿದೀನಿ:",
    "ಸರ್ ಇವತ್ತಿನ medicine stock:",
    "Hi sir, ಇಂದಿನ stock ವಿವರ ಇಲ್ಲಿದೆ:",
    "ನಮಸ್ಕಾರ ಸರ್, stock position for today:",
    "ಸರ್, ಇವತ್ತಿನ ಔಷಧಿ ಲೆಕ್ಕ:",
    "Good evening sir, ಈ ದಿನದ stock:",
    "ನಮಸ್ಕಾರ, ಇವತ್ತು stock check ಮಾಡಿದ್ದೇನೆ:",
    "ಸರ್ ದಯವಿಟ್ಟು ನೋಡಿ, today's stock:",
    "ಹಲೋ, ಇವತ್ತಿನ ಔಷಧಿ stock list:",
    "ನಮಸ್ಕಾರ ಸರ್, stock count ಮಾಡಿದ್ದು:",
    "Sir ನಮಸ್ಕಾರ, ಇಂದಿನ stock ಕಳಿಸ್ತೀನಿ:",
    "ಸರ್, ಇವತ್ತಿನ ಔಷಧಿ ಸ್ಟಾಕ್ ಇಲ್ಲಿದೆ:",
]

CLOSINGS = [
    "ಧನ್ಯವಾದಗಳು 🙏",
    "pls check ಮಾಡಿ 🙏",
    "ಯಾವುದಾದ್ರೂ ಬೇಕಿದ್ರೆ ಹೇಳಿ",
    "urgent ಇದ್ರೆ call ಮಾಡಿ",
    "thanks sir 🙏🙏",
    "ಪ್ಲೀಸ್ confirm ಮಾಡಿ",
    "ಇಷ್ಟೇ ಸರ್, balance stock",
    "stock ಕಡಿಮೆ ಇದೆ 😟 pls send",
]

UNIT_CASUAL = {
    "vial": "vial",
    "ampoule": "amp",
    "dose": "dose",
    "tablet": "strip",
    "capsule": "cap",
    "sachet": "packet",
    "bottle": "bottle",
}


def _drug_hash(drug_code: str, seed: int, day_index: int) -> int:
    key = f"{drug_code}:{seed}:{day_index}"
    return int.from_bytes(hashlib.md5(key.encode()).digest()[:4], "little")


def _format_expiry_short(expiry: str) -> str:
    try:
        parts = expiry.split("-")
        return f"{parts[2]}/{parts[1]}"
    except (IndexError, ValueError):
        return expiry


def generate(
    facility_id: str,
    date_str: str,
    lots: list[dict],
    seed: int,
    day_index: int,
) -> str:
    rng_base = seed + day_index * 7

    greeting = GREETINGS[rng_base % len(GREETINGS)]
    closing = CLOSINGS[(rng_base + 3) % len(CLOSINGS)]

    # Group lots by drug, shuffle order deterministically
    drug_lots: dict[str, list[dict]] = {}
    for lot in lots:
        if lot.get("qty", 0) <= 0 and lot.get("status") == "expired":
            continue
        dc = lot["drug_code"]
        drug_lots.setdefault(dc, []).append(lot)

    drug_codes = sorted(drug_lots.keys())
    # Deterministic shuffle
    drug_codes.sort(key=lambda dc: _drug_hash(dc, seed, day_index))

    lines = [greeting, ""]

    for dc in drug_codes:
        info = DRUG_INFO.get(dc, {})
        chat_name = info.get("chat_name", dc)
        unit = UNIT_CASUAL.get(info.get("unit", "unit"), info.get("unit", "unit"))
        dh = _drug_hash(dc, seed, day_index)

        for lot in drug_lots[dc]:
            qty = lot["qty"]
            batch = lot["batch_no"]
            expiry = _format_expiry_short(lot["expiry"])

            # For tablets/capsules, sometimes report in strips
            if info.get("unit") in ("tablet", "capsule") and dh % 3 == 0:
                qty = max(1, qty // info.get("pack_size", 10))
                unit = "strip"

            # ~30% of entries omit batch
            if dh % 3 == 1:
                lines.append(f"- {chat_name} {qty} {unit} exp {expiry}")
            else:
                lines.append(f"- {chat_name} {qty} {unit} (batch {batch} exp {expiry})")

            # Occasional urgency markers
            if qty <= 5 and dh % 2 == 0:
                lines[-1] += " ⚠️ ಕಡಿಮೆ!!"
            elif qty <= 10:
                lines[-1] += " ಕಡಿಮೆ ಇದೆ"

    lines.append("")
    lines.append(closing)
    return "\n".join(lines)
