import numpy as np

from app.stats.sequential import ArmStats, SequentialTest


def test_armstats_matches_numpy():
    xs = [1.0, 2.5, 3.0, -1.0, 4.2, 0.5]
    a = ArmStats()
    for x in xs:
        a.update(x)
    assert a.n == len(xs)
    assert abs(a.mean - np.mean(xs)) < 1e-12
    assert abs(a.var - np.var(xs, ddof=1)) < 1e-10


def test_radius_positive_and_shrinks_with_data():
    t = SequentialTest(alpha=0.05, tau2=0.1)
    r_small = t.radius(V=0.1)
    r_large = t.radius(V=0.001)  # more data -> smaller V -> tighter interval
    assert r_small > 0 and r_large > 0
    assert r_large < r_small


def test_detects_large_true_effect():
    rng = np.random.default_rng(0)
    t = SequentialTest(alpha=0.05, tau2=0.5)
    c, tr = ArmStats(), ArmStats()
    for _ in range(2000):
        c.update(rng.normal(0, 1))
        tr.update(rng.normal(0.5, 1))
    res = t.evaluate(c, tr)
    assert res.significant
    assert res.ci_lower > 0  # correctly identifies positive effect
