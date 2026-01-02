"""Deterministic assignment: same unit always lands in the same variant.

Hash (experiment_key : unit_id : salt) -> uniform [0,1). Two independent draws
are used: one for the rollout gate (% of traffic in the experiment) and one for
the variant bucket, so changing rollout does not reshuffle already-assigned
units into different variants.
"""

from __future__ import annotations

import hashlib


def _uniform(*parts: str) -> float:
    h = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()
    # top 52 bits -> [0,1)
    return int(h[:13], 16) / float(1 << 52)


def in_rollout(experiment_key: str, unit_id: str, rollout_pct: float) -> bool:
    if rollout_pct >= 100:
        return True
    if rollout_pct <= 0:
        return False
    return _uniform(experiment_key, unit_id, "rollout") < rollout_pct / 100.0


def assign_variant(
    experiment_key: str,
    unit_id: str,
    variants: list[str],
    weights: list[float] | None = None,
) -> str:
    """Deterministically assign a unit to one of the variants by weight."""
    if not variants:
        raise ValueError("no variants")
    if weights is None:
        weights = [1.0] * len(variants)
    if len(weights) != len(variants):
        raise ValueError("weights/variants length mismatch")
    total = sum(weights)
    u = _uniform(experiment_key, unit_id, "variant") * total
    cum = 0.0
    for v, w in zip(variants, weights):
        cum += w
        if u < cum:
            return v
    return variants[-1]


def assign(
    experiment_key: str,
    unit_id: str,
    variants: list[str],
    rollout_pct: float = 100.0,
    weights: list[float] | None = None,
) -> str | None:
    """Full assignment: None if not in rollout, else the variant."""
    if not in_rollout(experiment_key, unit_id, rollout_pct):
        return None
    return assign_variant(experiment_key, unit_id, variants, weights)
