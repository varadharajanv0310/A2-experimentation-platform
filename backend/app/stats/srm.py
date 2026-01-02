"""Sample Ratio Mismatch (SRM) detection via a chi-square goodness-of-fit test.

If the observed variant split diverges from the intended allocation more than
chance allows, the experiment is compromised (e.g. a broken assignment or a
variant that crashes and drops users). Flag when p < threshold (default 0.001).
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy import stats


@dataclass
class SRMResult:
    chi_square: float
    p_value: float
    flagged: bool
    observed: list[int]
    expected: list[float]


def check_srm(
    observed: list[int],
    weights: list[float],
    threshold: float = 0.001,
) -> SRMResult:
    total = sum(observed)
    wsum = sum(weights)
    expected = [total * w / wsum for w in weights]
    if total == 0 or any(e == 0 for e in expected):
        return SRMResult(0.0, 1.0, False, observed, expected)
    chi = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    dof = len(observed) - 1
    p = float(stats.chi2.sf(chi, dof))
    return SRMResult(chi, p, p < threshold, observed, expected)
