"""Guardrail evaluation: flag when a protected metric significantly degrades.

A guardrail is a metric we don't want to harm (e.g. latency, error rate). We
run the same always-valid sequential test on the guardrail metric and flag if
the effect is significantly in the *bad* direction beyond a tolerated threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from .sequential import ArmStats, SequentialTest


@dataclass
class GuardrailResult:
    metric: str
    effect: float
    ci_lower: float
    ci_upper: float
    direction: str      # "increase_bad" | "decrease_bad"
    threshold: float
    flagged: bool


def evaluate_guardrail(
    metric: str,
    control: ArmStats,
    treatment: ArmStats,
    direction: str,
    threshold: float,
    alpha: float = 0.05,
    tau2: float = 0.1,
) -> GuardrailResult:
    test = SequentialTest(alpha=alpha, tau2=tau2)
    res = test.evaluate(control, treatment)
    flagged = False
    if direction == "increase_bad":
        # bad if treatment increases the metric: CI lower bound above threshold
        flagged = res.ci_lower > threshold
    else:  # decrease_bad
        flagged = res.ci_upper < -threshold
    return GuardrailResult(
        metric=metric,
        effect=res.effect,
        ci_lower=res.ci_lower,
        ci_upper=res.ci_upper,
        direction=direction,
        threshold=threshold,
        flagged=flagged,
    )
