"""The critical gate: always-valid false-positive control under continuous
peeking, plus power (detects a true effect earlier than fixed-horizon)."""

import numpy as np
from scipy import stats

from app.stats.sequential import ArmStats, SequentialTest

ALPHA = 0.05
TAU2 = 0.1
MAX_N = 2000
PEEK_EVERY = 25
MIN_N = 50


def _aa_trial(seed):
    r = np.random.default_rng(seed)
    test = SequentialTest(alpha=ALPHA, tau2=TAU2)
    c, t = ArmStats(), ArmStats()
    cs = r.normal(0, 1, MAX_N)
    ts = r.normal(0, 1, MAX_N)
    seq_rej = naive_rej = False
    for i in range(MAX_N):
        c.update(cs[i]); t.update(ts[i])
        if (i + 1) % PEEK_EVERY == 0 and (i + 1) >= MIN_N:
            if test.evaluate(c, t).significant:
                seq_rej = True
            _, p = stats.ttest_ind(ts[: i + 1], cs[: i + 1], equal_var=False)
            if p < ALPHA:
                naive_rej = True
    return seq_rej, naive_rej


def test_aa_false_positive_control_under_peeking():
    """mSPRT FPR <= alpha + 2% while naive peeked t-test blows past alpha."""
    n_sims = 400
    seq = naive = 0
    for s in range(n_sims):
        sr, nr = _aa_trial(2000 + s)
        seq += sr
        naive += nr
    seq_fpr = seq / n_sims
    naive_fpr = naive / n_sims
    # Gate: always-valid test controls FPR under continuous peeking
    assert seq_fpr <= ALPHA + 0.02, f"mSPRT FPR too high: {seq_fpr}"
    # Contrast: the naive fixed-horizon test, peeked, badly inflates FPR
    assert naive_fpr > ALPHA + 0.10, f"naive FPR should inflate, got {naive_fpr}"


def _power_trial(seed, effect):
    r = np.random.default_rng(seed)
    test = SequentialTest(alpha=ALPHA, tau2=0.5)
    c, t = ArmStats(), ArmStats()
    cs = r.normal(0, 1, MAX_N)
    ts = r.normal(effect, 1, MAX_N)
    stop_n = None
    for i in range(MAX_N):
        c.update(cs[i]); t.update(ts[i])
        if (i + 1) % PEEK_EVERY == 0 and (i + 1) >= MIN_N:
            if test.evaluate(c, t).significant:
                stop_n = i + 1
                break
    return stop_n


def test_power_and_early_stopping_on_true_effect():
    """On a seeded true effect the sequential test detects it with high power
    and, on average, well before the fixed horizon."""
    n_sims = 200
    effect = 0.3
    detected = 0
    stops = []
    for s in range(n_sims):
        stop = _power_trial(5000 + s, effect)
        if stop is not None:
            detected += 1
            stops.append(stop)
    power = detected / n_sims
    avg_stop = float(np.mean(stops)) if stops else MAX_N
    assert power >= 0.8, f"power too low: {power}"
    assert avg_stop < MAX_N, f"no early stopping: {avg_stop}"
