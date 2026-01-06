"""Run the full 1000-sim A/A false-positive study and write the documented
result (numbers + an ASCII confidence-sequence plot) to runs/. This is the
gate artifact required by the DoD."""

from __future__ import annotations

import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.stats.sequential import ArmStats, SequentialTest  # noqa: E402

ALPHA = 0.05
TAU2 = 0.1
MAX_N = 2000
PEEK_EVERY = 25
MIN_N = 50
N_SIMS = 1000


def aa_trial(seed):
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


def one_cs_path(seed, effect):
    """Return (ns, effects, lowers, uppers) for a single confidence-sequence path."""
    r = np.random.default_rng(seed)
    test = SequentialTest(alpha=ALPHA, tau2=0.5)
    c, t = ArmStats(), ArmStats()
    ns, eff, lo, hi = [], [], [], []
    for i in range(MAX_N):
        c.update(r.normal(0, 1)); t.update(r.normal(effect, 1))
        if (i + 1) % PEEK_EVERY == 0 and (i + 1) >= MIN_N:
            res = test.evaluate(c, t)
            ns.append(i + 1); eff.append(res.effect)
            lo.append(res.ci_lower); hi.append(res.ci_upper)
    return ns, eff, lo, hi


def main():
    os.makedirs("runs", exist_ok=True)
    seq = naive = 0
    for s in range(N_SIMS):
        sr, nr = aa_trial(10_000 + s)
        seq += sr; naive += nr
    seq_fpr = seq / N_SIMS
    naive_fpr = naive / N_SIMS

    # sample confidence-sequence paths (A/A converges around 0; A/B excludes 0)
    ns0, e0, l0, h0 = one_cs_path(1, 0.0)
    ns1, e1, l1, h1 = one_cs_path(2, 0.3)

    lines = []
    lines.append("A/A FALSE-POSITIVE STUDY (1000 sims, continuous peeking)")
    lines.append("=" * 60)
    lines.append(f"nominal alpha                         : {ALPHA}")
    lines.append(f"mSPRT (always-valid) FPR              : {seq_fpr:.4f}")
    lines.append(f"  -> gate requires <= alpha + 0.02 = {ALPHA + 0.02:.2f}: "
                 f"{'PASS' if seq_fpr <= ALPHA + 0.02 else 'FAIL'}")
    lines.append(f"naive fixed-horizon t-test, peeked    : {naive_fpr:.4f}")
    lines.append(f"  -> demonstrates peeking inflates FPR far above alpha")
    lines.append("")
    lines.append("SAMPLE CONFIDENCE SEQUENCE — A/A (true effect 0), should keep 0 inside:")
    for i in range(0, len(ns0), max(1, len(ns0) // 12)):
        bar = "0 in CI" if l0[i] <= 0 <= h0[i] else "0 EXCLUDED"
        lines.append(f"  n={ns0[i]:5d}  effect={e0[i]:+.3f}  CI=[{l0[i]:+.3f},{h0[i]:+.3f}]  {bar}")
    lines.append("")
    lines.append("SAMPLE CONFIDENCE SEQUENCE — A/B (true effect 0.30), should exclude 0:")
    excluded_at = None
    for i in range(0, len(ns1), max(1, len(ns1) // 12)):
        inside = l1[i] <= 0 <= h1[i]
        if not inside and excluded_at is None:
            excluded_at = ns1[i]
        bar = "0 in CI" if inside else "0 EXCLUDED <-- stop"
        lines.append(f"  n={ns1[i]:5d}  effect={e1[i]:+.3f}  CI=[{l1[i]:+.3f},{h1[i]:+.3f}]  {bar}")
    lines.append(f"\nA/B first excluded 0 near n={excluded_at}")

    report = "\n".join(lines)
    with open("runs/aa_study.txt", "w") as f:
        f.write(report + "\n")
    print(report)
    print("\n[written] runs/aa_study.txt")


if __name__ == "__main__":
    main()
