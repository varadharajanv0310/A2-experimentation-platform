from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    hypothesis: Mapped[str] = mapped_column(String, default="")
    # variants: ["control","treatment"]; weights parallel list; primary metric name
    variants: Mapped[list] = mapped_column(JSON)
    weights: Mapped[list] = mapped_column(JSON)
    rollout_pct: Mapped[float] = mapped_column(Float, default=100.0)
    primary_metric: Mapped[str] = mapped_column(String, default="conversion")
    # guardrails: [{"metric": "latency", "direction": "increase_bad", "threshold": 0.0}]
    guardrails: Mapped[list] = mapped_column(JSON, default=list)
    alpha: Mapped[float] = mapped_column(Float, default=0.05)
    tau2: Mapped[float] = mapped_column(Float, default=0.1)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|running|stopped
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    events: Mapped[list[Event]] = relationship(back_populates="experiment")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("experiment_key", "unit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_key: Mapped[str] = mapped_column(String, index=True)
    unit_id: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str] = mapped_column(String)
    segment: Mapped[str] = mapped_column(String, default="all")
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    unit_id: Mapped[str] = mapped_column(String, index=True)
    variant: Mapped[str] = mapped_column(String, index=True)
    segment: Mapped[str] = mapped_column(String, default="all")
    metric: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    covariate: Mapped[float] = mapped_column(Float, default=0.0)  # pre-period X for CUPED
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    experiment: Mapped[Experiment] = relationship(back_populates="events")
