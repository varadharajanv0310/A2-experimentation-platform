"""Traffic simulator: streams units through an experiment, generating a metric
with an optional true treatment effect and a correlated pre-period covariate
(so CUPED has something to exploit)."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from .models import Event, Experiment
from .services.metrics_engine import ensure_assignment


def simulate_traffic(
    db: Session,
    exp: Experiment,
    n_units: int,
    true_effect: float = 0.0,
    covariate_corr: float = 0.7,
    guardrail_effect: dict[str, float] | None = None,
    seed: int = 42,
    start_unit: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)
    treatment_name = exp.variants[1]
    ingested = 0
    guardrail_effect = guardrail_effect or {}

    for i in range(start_unit, start_unit + n_units):
        unit_id = f"user-{i}"
        segment = "new" if rng.random() < 0.4 else "returning"
        variant = ensure_assignment(db, exp, unit_id, segment)
        if variant is None:
            continue

        # pre-period covariate X ~ N(0,1); metric Y correlated with X
        x = rng.normal(0, 1)
        base = covariate_corr * x + np.sqrt(1 - covariate_corr**2) * rng.normal(0, 1)
        y = base
        if variant == treatment_name:
            # heterogeneous: bigger lift for "new" segment
            seg_mult = 1.5 if segment == "new" else 0.6
            y += true_effect * seg_mult

        db.add(
            Event(
                experiment_id=exp.id,
                unit_id=unit_id,
                variant=variant,
                segment=segment,
                metric=exp.primary_metric,
                value=float(y),
                covariate=float(x),
            )
        )
        # guardrail metrics
        for gm, geff in guardrail_effect.items():
            gv = rng.normal(0, 1) + (geff if variant == treatment_name else 0.0)
            db.add(
                Event(
                    experiment_id=exp.id,
                    unit_id=unit_id,
                    variant=variant,
                    segment=segment,
                    metric=gm,
                    value=float(gv),
                    covariate=0.0,
                )
            )
        ingested += 1
        if ingested % 500 == 0:
            db.commit()
    db.commit()
    return {"ingested": ingested}
