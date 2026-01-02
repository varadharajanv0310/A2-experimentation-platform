"""CUPED variance reduction (Deng, Xu, Kohavi, Walker 2013).

Y_adj = Y - theta * (X - E[X]),  theta = Cov(Y, X) / Var(X)

Using a pre-experiment covariate X correlated with the metric Y removes the
part of Y's variance explained by X, without biasing the treatment effect
(X is measured pre-assignment, so it is independent of the treatment).
Variance is reduced by a factor (1 - rho^2), rho = corr(X, Y).
"""

from __future__ import annotations

import numpy as np


def cuped_theta(y: np.ndarray, x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    vx = np.var(x, ddof=1)
    if vx <= 0:
        return 0.0
    cov = np.cov(y, x, ddof=1)[0, 1]
    return float(cov / vx)


def apply_cuped(
    y: np.ndarray, x: np.ndarray, theta: float | None = None
) -> tuple[np.ndarray, float]:
    """Return (adjusted Y, theta). theta fit on the pooled data if not given."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if theta is None:
        theta = cuped_theta(y, x)
    y_adj = y - theta * (x - x.mean())
    return y_adj, theta


def variance_reduction(y: np.ndarray, x: np.ndarray) -> float:
    """Fractional variance reduction from CUPED, i.e. 1 - Var(Y_adj)/Var(Y)."""
    y = np.asarray(y, dtype=float)
    y_adj, _ = apply_cuped(y, x)
    v0 = np.var(y, ddof=1)
    if v0 <= 0:
        return 0.0
    return float(1.0 - np.var(y_adj, ddof=1) / v0)
