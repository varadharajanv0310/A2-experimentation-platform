"""Always-valid sequential testing via the mixture SPRT (mSPRT).

The hard core of this platform. Instead of a fixed-horizon t-test (whose type-I
error inflates badly if you peek), we build an *always-valid confidence
sequence* for the difference in means that permits continuous peeking and
legitimate early stopping while controlling the false-positive rate at alpha
uniformly over time.

Construction (normal mixture / mSPRT, Robbins 1970; Johari, Pekelis, Walsh
2017 "Peeking at A/B Tests").

Let, at any point in the stream:
    d_hat = mean(treatment) - mean(control)      # effect estimate
    V     = s_t^2 / n_t + s_c^2 / n_c            # variance of d_hat

Under H0: true effect Delta = 0, so d_hat ~approx N(0, V). We mix the
alternative over Delta ~ N(0, tau^2). The mixture likelihood ratio of the data
under the mixed alternative vs the null is a non-negative martingale under H0:

    Lambda_n = sqrt(V / (V + tau^2))
               * exp( (d_hat - Delta0)^2 / 2 * tau^2 / (V (V + tau^2)) )

By Ville's inequality, P( sup_n Lambda_n >= 1/alpha ) <= alpha under H0. So the
test "reject H0 when Lambda_n >= 1/alpha" has type-I error <= alpha *uniformly
over all n* — you may peek as often as you like. tau^2 tunes power (best near
the expected effect scale) but never affects validity.

Inverting the test over Delta0 gives the confidence sequence:

    CS_n = d_hat +/- r,
    r = sqrt( (V (V + tau^2) / tau^2) * ( 2 ln(1/alpha) + ln((V + tau^2)/V) ) )

We declare a significant effect the first time 0 is outside CS_n. The
always-valid p-value is the running minimum of 1/Lambda_n(Delta0=0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ArmStats:
    """Sufficient statistics for one arm, updatable online."""

    n: int = 0
    mean: float = 0.0
    m2: float = 0.0  # sum of squared deviations (Welford)

    def update(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def var(self) -> float:
        # sample variance (unbiased); 0 until we have 2 observations
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    def merge_batch(self, values: list[float]) -> None:
        for v in values:
            self.update(v)


@dataclass
class SequentialResult:
    n_control: int
    n_treatment: int
    effect: float
    ci_lower: float
    ci_upper: float
    p_value: float           # always-valid p-value (running min)
    log_lr: float            # log mixture likelihood ratio at Delta0=0
    significant: bool
    decision: str            # "significant" | "inconclusive"


class SequentialTest:
    """Always-valid mSPRT test for the difference in means of two arms.

    tau2 is the mixture variance; pick it near (expected_effect)^2 for good
    power. alpha is the target false-positive rate (uniform over time).
    """

    def __init__(self, alpha: float = 0.05, tau2: float = 1.0) -> None:
        if not (0 < alpha < 1):
            raise ValueError("alpha must be in (0,1)")
        if tau2 <= 0:
            raise ValueError("tau2 must be > 0")
        self.alpha = alpha
        self.tau2 = tau2
        self._min_p = 1.0  # running minimum always-valid p-value

    def _variance(self, control: ArmStats, treatment: ArmStats) -> float:
        vc = control.var / control.n if control.n > 0 else float("inf")
        vt = treatment.var / treatment.n if treatment.n > 0 else float("inf")
        return vc + vt

    def log_lr_at(self, d_hat: float, V: float, delta0: float = 0.0) -> float:
        """log mixture likelihood ratio for H0: Delta = delta0."""
        tau2 = self.tau2
        term_sqrt = 0.5 * math.log(V / (V + tau2))
        term_exp = ((d_hat - delta0) ** 2) / 2.0 * tau2 / (V * (V + tau2))
        return term_sqrt + term_exp

    def radius(self, V: float) -> float:
        tau2 = self.tau2
        inside = (V * (V + tau2) / tau2) * (
            2.0 * math.log(1.0 / self.alpha) + math.log((V + tau2) / V)
        )
        return math.sqrt(max(inside, 0.0))

    def evaluate(self, control: ArmStats, treatment: ArmStats) -> SequentialResult:
        n_c, n_t = control.n, treatment.n
        # Need enough data for a finite variance estimate in each arm.
        if n_c < 2 or n_t < 2:
            return SequentialResult(
                n_control=n_c,
                n_treatment=n_t,
                effect=treatment.mean - control.mean,
                ci_lower=float("-inf"),
                ci_upper=float("inf"),
                p_value=1.0,
                log_lr=0.0,
                significant=False,
                decision="inconclusive",
            )
        d_hat = treatment.mean - control.mean
        V = self._variance(control, treatment)
        if V <= 0 or not math.isfinite(V):
            V = 1e-12
        log_lr = self.log_lr_at(d_hat, V, 0.0)
        # always-valid p-value = 1/Lambda, running-minimized by the caller if
        # they keep the test instance; here we min against our own history.
        p_now = min(1.0, math.exp(-log_lr))
        self._min_p = min(self._min_p, p_now)
        r = self.radius(V)
        lower, upper = d_hat - r, d_hat + r
        significant = not (lower <= 0.0 <= upper)
        return SequentialResult(
            n_control=n_c,
            n_treatment=n_t,
            effect=d_hat,
            ci_lower=lower,
            ci_upper=upper,
            p_value=self._min_p,
            log_lr=log_lr,
            significant=significant,
            decision="significant" if significant else "inconclusive",
        )
