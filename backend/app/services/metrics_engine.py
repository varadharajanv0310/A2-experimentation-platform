"""Metrics engine: pull events, run the sequential test (optionally with CUPED),
compute guardrails, SRM, and per-segment slices."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Assignment, Event, Experiment
from ..stats.assignment import assign
from ..stats.cuped import apply_cuped, variance_reduction
from ..stats.guardrails import evaluate_guardrail
from ..stats.sequential import ArmStats, SequentialTest
from ..stats.srm import check_srm


def _arm_from_values(values: list[float]) -> ArmStats:
    a = ArmStats()
    for v in values:
        a.update(v)
    return a


def compute_results(
    db: Session, exp: Experiment, metric: str | None = None, use_cuped: bool = False
) -> dict:
    metric = metric or exp.primary_metric
    control_name, treatment_name = exp.variants[0], exp.variants[1]

    rows = db.execute(
        select(Event.variant, Event.value, Event.covariate, Event.segment).where(
            Event.experiment_id == exp.id, Event.metric == metric
        )
    ).all()

    by_variant: dict[str, list[tuple[float, float]]] = defaultdict(list)
    by_segment: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for variant, value, cov, segment in rows:
        by_variant[variant].append((value, cov))
        by_segment[segment][variant].append((value, cov))

    def run_test(pairs_c, pairs_t):
        yc = np.array([p[0] for p in pairs_c], dtype=float)
        yt = np.array([p[0] for p in pairs_t], dtype=float)
        vr = None
        if use_cuped and len(yc) > 2 and len(yt) > 2:
            xc = np.array([p[1] for p in pairs_c], dtype=float)
            xt = np.array([p[1] for p in pairs_t], dtype=float)
            # fit theta on pooled data, apply per arm (X is pre-treatment)
            y_all = np.concatenate([yc, yt])
            x_all = np.concatenate([xc, xt])
            _, theta = apply_cuped(y_all, x_all)
            yc = yc - theta * (xc - x_all.mean())
            yt = yt - theta * (xt - x_all.mean())
            vr = variance_reduction(y_all, x_all)
        test = SequentialTest(alpha=exp.alpha, tau2=exp.tau2)
        res = test.evaluate(_arm_from_values(list(yc)), _arm_from_values(list(yt)))
        d = asdict(res)
        if vr is not None:
            d["cuped_variance_reduction"] = vr
        return d

    pooled = run_test(by_variant.get(control_name, []), by_variant.get(treatment_name, []))

    # segment slices (heterogeneous effects)
    segments = {}
    for seg, vmap in by_segment.items():
        if seg == "all":
            continue
        if len(vmap.get(control_name, [])) > 2 and len(vmap.get(treatment_name, [])) > 2:
            segments[seg] = run_test(
                vmap.get(control_name, []), vmap.get(treatment_name, [])
            )

    # SRM on assignment counts
    assign_rows = db.execute(
        select(Assignment.variant).where(Assignment.experiment_key == exp.key)
    ).all()
    counts = defaultdict(int)
    for (v,) in assign_rows:
        counts[v] += 1
    observed = [counts.get(v, 0) for v in exp.variants]
    srm = check_srm(observed, exp.weights)

    # guardrails
    guardrails = []
    for g in exp.guardrails or []:
        grows = db.execute(
            select(Event.variant, Event.value).where(
                Event.experiment_id == exp.id, Event.metric == g["metric"]
            )
        ).all()
        gc = [val for var, val in grows if var == control_name]
        gt = [val for var, val in grows if var == treatment_name]
        if len(gc) > 2 and len(gt) > 2:
            gr = evaluate_guardrail(
                g["metric"],
                _arm_from_values(gc),
                _arm_from_values(gt),
                g.get("direction", "increase_bad"),
                float(g.get("threshold", 0.0)),
                alpha=exp.alpha,
                tau2=exp.tau2,
            )
            guardrails.append(asdict(gr))

    return {
        "experiment": exp.key,
        "metric": metric,
        "use_cuped": use_cuped,
        "pooled": pooled,
        "segments": segments,
        "srm": asdict(srm),
        "guardrails": guardrails,
    }


def confidence_sequence(
    db: Session, exp: Experiment, metric: str | None = None, step: int = 50
) -> list[dict]:
    """Walk events in arrival order and emit the confidence sequence over time,
    so the console can chart legitimate peeking (the CI tightens; a real effect
    excludes 0 and stays excluded)."""
    metric = metric or exp.primary_metric
    control_name, treatment_name = exp.variants[0], exp.variants[1]
    rows = db.execute(
        select(Event.variant, Event.value)
        .where(Event.experiment_id == exp.id, Event.metric == metric)
        .order_by(Event.id)
    ).all()

    test = SequentialTest(alpha=exp.alpha, tau2=exp.tau2)
    c, t = ArmStats(), ArmStats()
    points: list[dict] = []
    for i, (variant, value) in enumerate(rows):
        if variant == control_name:
            c.update(value)
        elif variant == treatment_name:
            t.update(value)
        if (i + 1) % step == 0 and c.n > 2 and t.n > 2:
            res = test.evaluate(c, t)
            points.append(
                {
                    "n": i + 1,
                    "effect": res.effect,
                    "ci_lower": res.ci_lower,
                    "ci_upper": res.ci_upper,
                    "significant": res.significant,
                    "p_value": res.p_value,
                }
            )
    return points


def ensure_assignment(db: Session, exp: Experiment, unit_id: str, segment: str = "all") -> str | None:
    existing = db.execute(
        select(Assignment).where(
            Assignment.experiment_key == exp.key, Assignment.unit_id == unit_id
        )
    ).scalar_one_or_none()
    if existing:
        return existing.variant
    variant = assign(exp.key, unit_id, exp.variants, exp.rollout_pct, exp.weights)
    if variant is None:
        return None
    db.add(
        Assignment(
            experiment_key=exp.key, unit_id=unit_id, variant=variant, segment=segment
        )
    )
    db.commit()
    return variant
