import numpy as np

from app.stats.cuped import apply_cuped, cuped_theta, variance_reduction


def test_cuped_reduces_variance_when_correlated():
    rng = np.random.default_rng(1)
    n = 5000
    x = rng.normal(0, 1, n)
    y = 0.8 * x + np.sqrt(1 - 0.64) * rng.normal(0, 1, n)  # rho ~ 0.8
    vr = variance_reduction(y, x)
    # expected reduction ~ rho^2 = 0.64
    assert 0.55 < vr < 0.72


def test_cuped_no_reduction_when_uncorrelated():
    rng = np.random.default_rng(2)
    n = 5000
    x = rng.normal(0, 1, n)
    y = rng.normal(0, 1, n)
    vr = variance_reduction(y, x)
    assert abs(vr) < 0.05


def test_cuped_is_unbiased_for_the_mean():
    rng = np.random.default_rng(3)
    n = 20000
    x = rng.normal(0, 1, n)
    y = 5.0 + 0.7 * x + rng.normal(0, 1, n)
    y_adj, theta = apply_cuped(y, x)
    # adjustment subtracts theta*(x - mean x); mean is preserved in expectation
    assert abs(y_adj.mean() - y.mean()) < 1e-9
    assert abs(theta - cuped_theta(y, x)) < 1e-12
