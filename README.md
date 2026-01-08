# A2 — Experimentation Platform

An A/B testing engine with **always-valid sequential testing** (legitimate early
stopping / continuous peeking), **CUPED** variance reduction, guardrail
regression detection, deterministic assignment with SRM checks, and a React
console to create and monitor experiments.

## The hard core: always-valid inference

A fixed-horizon t-test assumes you look **once**, at a pre-committed sample size.
If you peek repeatedly and stop when you see significance, your false-positive
rate explodes — in our 1000-sim A/A study, a continuously-peeked t-test fires
**32.7%** of the time at a nominal α=0.05.

This platform instead uses the **mixture SPRT (mSPRT)** to build an *always-valid
confidence sequence* for the difference in means. By Ville's inequality the
mixture likelihood ratio is a non-negative martingale under H₀, so
`P(∃n : reject) ≤ α` **uniformly over time** — you may peek as often as you like
and stop the moment 0 leaves the confidence interval. Same study: **2.6%**
false-positive rate (≤ α). Full math in
[`backend/app/stats/sequential.py`](backend/app/stats/sequential.py); the study
artifact is [`docs/aa_study.txt`](docs/aa_study.txt).

```
mSPRT (always-valid) FPR with continuous peeking : 0.0260   (nominal α = 0.05)
naive fixed-horizon t-test, peeked continuously  : 0.3270
```

## Run it

```bash
cp .env.example .env
docker compose up -d db                                  # Postgres on :5434
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m app.seed                 # 3 demo experiments
backend/.venv/Scripts/python -m uvicorn app.api:app --port 8002   # from backend/
cd frontend && npm install && npm run dev                # console on :5175
```

(Or use the `Makefile`: `make setup`, `make seed`, `make dev`, `make dev-web`,
`make test`, `make verify`, `make aa-study`.)

## Architecture

```
Traffic simulator / clients
   │  POST /api/assign     deterministic hash → variant (+ % rollout gate)
   │  POST /api/events     metric values (+ pre-period covariate for CUPED)
   ▼
FastAPI  ── SQLAlchemy ──►  Postgres (experiments, assignments, events)
   │
   └─ metrics engine: mSPRT sequential test · CUPED · guardrails · SRM · segment slices
   ▼
React console: experiment list · live confidence-sequence chart · CUPED toggle ·
               guardrail status · segment table
```

### Statistical components (`backend/app/stats/`)

- **`sequential.py`** — mSPRT confidence sequence for the difference in means.
  Online Welford sufficient stats; radius
  `r = √( V(V+τ²)/τ² · (2 ln(1/α) + ln((V+τ²)/V)) )`; reject when 0 ∉ [d̂−r, d̂+r].
- **`cuped.py`** — `Y_adj = Y − θ(X − E[X])`, `θ = Cov(Y,X)/Var(X)`; reduces
  variance by ≈ρ² without biasing the effect (X is pre-assignment).
- **`assignment.py`** — SHA-256 hash of `(key:unit:salt)`; independent draws for
  the rollout gate and the variant bucket so rollout changes don't reshuffle.
- **`srm.py`** — chi-square goodness-of-fit on observed vs intended split.
- **`guardrails.py`** — the same sequential test on a protected metric, flagged
  when the CI shows significant degradation in the bad direction.

## Verification gate — all items pass

- [x] **A/A false-positive control (critical):** 1000 A/A sims, continuous
      peeking → mSPRT FPR **0.026 ≤ α+0.02**; naive peeked t-test **0.327**
      (documented in `docs/aa_study.txt`, tested in `tests/test_aa_gate.py`).
- [x] **Power + early stopping:** on a seeded effect (0.3), power ≥ 0.8 and it
      stops well before the fixed horizon (`test_power_and_early_stopping`).
- [x] **CUPED:** on data with a ρ≈0.75 pre-covariate, **54.8%** variance
      reduction; console shows the CI tightening when toggled on.
- [x] **Assignment:** same `unit_id` → same variant; 30% rollout hits target
      within 1pt over 100k units; SRM passes balanced, fires on 60/40.
- [x] **Guardrail** flag fires on the seeded latency regression (`promo-banner`).
- [x] `make test` green — 13 tests; ruff clean.

Live end-to-end check: `make verify` (8/8 against a running API + seeded DB).

## Data model

`experiments` (key, hypothesis, variants, weights, rollout_pct, primary_metric,
guardrails, α, τ², status) · `assignments` (experiment_key, unit_id, variant,
segment) · `events` (experiment_id, unit_id, variant, segment, metric, value,
covariate, ts).
