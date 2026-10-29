"""Poisson demand determinism tests."""
from __future__ import annotations

from app.consumption import compute_demand, stable_drug_hash


def test_deterministic():
    """Same inputs always produce the same demand."""
    d1 = compute_demand("PCM", 10.0, 1.0, day_index=5, seed=42)
    d2 = compute_demand("PCM", 10.0, 1.0, day_index=5, seed=42)
    assert d1 == d2
    assert d1 > 0


def test_different_days():
    """Different day_index produces different demand (with high probability)."""
    results = set()
    for day in range(20):
        results.add(compute_demand("PCM", 10.0, 1.0, day_index=day, seed=42))
    assert len(results) > 1


def test_zero_rate():
    """Zero base rate always produces zero demand."""
    d = compute_demand("PCM", 0.0, 1.0, day_index=5, seed=42)
    assert d == 0


def test_stable_hash_deterministic():
    """Hash is the same across calls."""
    h1 = stable_drug_hash("INSULIN")
    h2 = stable_drug_hash("INSULIN")
    assert h1 == h2

    h3 = stable_drug_hash("PCM")
    assert h3 != h1
