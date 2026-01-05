"""Seed realistic demo experiments so the console is non-empty on first open."""

from __future__ import annotations

from sqlalchemy import select

from .db import SessionLocal, engine
from .models import Base, Experiment
from .simulator import simulate_traffic


def run_seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.execute(select(Experiment)).first():
            print("[seed] experiments already present — skipping")
            return

        # 1) A real winner with a correlated covariate (CUPED demo) + guardrail
        checkout = Experiment(
            key="checkout-redesign",
            hypothesis="New checkout increases revenue per session",
            variants=["control", "treatment"],
            weights=[1.0, 1.0],
            rollout_pct=100.0,
            primary_metric="revenue",
            guardrails=[{"metric": "latency", "direction": "increase_bad", "threshold": 0.0}],
            alpha=0.05,
            tau2=0.1,
            status="running",
        )
        db.add(checkout)
        db.commit()
        simulate_traffic(
            db, checkout, n_units=6000, true_effect=0.12,
            covariate_corr=0.75, guardrail_effect={"latency": 0.0}, seed=7,
        )

        # 2) A guardrail regression: tiny primary lift but latency clearly worse
        banner = Experiment(
            key="promo-banner",
            hypothesis="Promo banner lifts clicks",
            variants=["control", "treatment"],
            weights=[1.0, 1.0],
            rollout_pct=100.0,
            primary_metric="clicks",
            guardrails=[{"metric": "latency", "direction": "increase_bad", "threshold": 0.0}],
            alpha=0.05,
            tau2=0.1,
            status="running",
        )
        db.add(banner)
        db.commit()
        simulate_traffic(
            db, banner, n_units=6000, true_effect=0.03,
            covariate_corr=0.5, guardrail_effect={"latency": 0.25}, seed=11,
        )

        # 3) A true A/A (no effect) at 50% rollout
        aa = Experiment(
            key="null-test",
            hypothesis="Sanity A/A",
            variants=["control", "treatment"],
            weights=[1.0, 1.0],
            rollout_pct=50.0,
            primary_metric="conversion",
            guardrails=[],
            alpha=0.05,
            tau2=0.1,
            status="running",
        )
        db.add(aa)
        db.commit()
        simulate_traffic(db, aa, n_units=6000, true_effect=0.0, seed=3)

        print("[seed] created 3 experiments with simulated traffic")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
