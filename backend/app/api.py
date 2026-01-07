from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, engine, get_session
from .models import Base, Event, Experiment
from .services.metrics_engine import (
    compute_results,
    confidence_sequence,
    ensure_assignment,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="A2 Experimentation Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExperimentIn(BaseModel):
    key: str
    hypothesis: str = ""
    variants: list[str] = ["control", "treatment"]
    weights: list[float] = [1.0, 1.0]
    rollout_pct: float = 100.0
    primary_metric: str = "conversion"
    guardrails: list[dict] = []
    alpha: float = 0.05
    tau2: float = 0.1


class AssignIn(BaseModel):
    experiment_key: str
    unit_id: str
    segment: str = "all"


class EventIn(BaseModel):
    experiment_key: str
    unit_id: str
    metric: str
    value: float
    covariate: float = 0.0
    segment: str = "all"


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/experiments")
def list_experiments(db: Session = Depends(get_session)):
    rows = db.execute(select(Experiment).order_by(Experiment.id)).scalars().all()
    return [
        {
            "id": e.id,
            "key": e.key,
            "hypothesis": e.hypothesis,
            "variants": e.variants,
            "weights": e.weights,
            "rollout_pct": e.rollout_pct,
            "primary_metric": e.primary_metric,
            "guardrails": e.guardrails,
            "alpha": e.alpha,
            "tau2": e.tau2,
            "status": e.status,
        }
        for e in rows
    ]


@app.post("/api/experiments")
def create_experiment(body: ExperimentIn, db: Session = Depends(get_session)):
    if db.execute(
        select(Experiment).where(Experiment.key == body.key)
    ).scalar_one_or_none():
        raise HTTPException(400, "experiment key already exists")
    if len(body.variants) != len(body.weights):
        raise HTTPException(400, "variants/weights length mismatch")
    exp = Experiment(**body.model_dump(), status="draft")
    db.add(exp)
    db.commit()
    return {"id": exp.id, "key": exp.key, "status": exp.status}


def _get_exp(db: Session, key: str) -> Experiment:
    exp = db.execute(
        select(Experiment).where(Experiment.key == key)
    ).scalar_one_or_none()
    if not exp:
        raise HTTPException(404, "experiment not found")
    return exp


@app.post("/api/experiments/{key}/status")
def set_status(key: str, status: str, db: Session = Depends(get_session)):
    exp = _get_exp(db, key)
    if status not in ("draft", "running", "stopped"):
        raise HTTPException(400, "invalid status")
    exp.status = status
    db.commit()
    return {"key": key, "status": status}


@app.post("/api/assign")
def assign_endpoint(body: AssignIn, db: Session = Depends(get_session)):
    exp = _get_exp(db, body.experiment_key)
    variant = ensure_assignment(db, exp, body.unit_id, body.segment)
    return {"unit_id": body.unit_id, "variant": variant, "in_experiment": variant is not None}


@app.post("/api/events")
def ingest_event(body: EventIn, db: Session = Depends(get_session)):
    exp = _get_exp(db, body.experiment_key)
    variant = ensure_assignment(db, exp, body.unit_id, body.segment)
    if variant is None:
        return {"ingested": False, "reason": "unit not in rollout"}
    db.add(
        Event(
            experiment_id=exp.id,
            unit_id=body.unit_id,
            variant=variant,
            segment=body.segment,
            metric=body.metric,
            value=body.value,
            covariate=body.covariate,
        )
    )
    db.commit()
    return {"ingested": True, "variant": variant}


@app.get("/api/experiments/{key}/results")
def results(
    key: str,
    metric: str | None = None,
    cuped: bool = False,
    db: Session = Depends(get_session),
):
    exp = _get_exp(db, key)
    return compute_results(db, exp, metric=metric, use_cuped=cuped)


@app.get("/api/experiments/{key}/sequence")
def sequence(
    key: str,
    metric: str | None = None,
    step: int = 50,
    db: Session = Depends(get_session),
):
    exp = _get_exp(db, key)
    return confidence_sequence(db, exp, metric=metric, step=step)
