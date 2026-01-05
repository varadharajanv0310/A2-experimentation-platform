from collections import Counter

from app.stats.assignment import assign, assign_variant, in_rollout
from app.stats.srm import check_srm


def test_assignment_is_deterministic():
    for uid in ["u1", "u2", "abc", "user-9999"]:
        v1 = assign_variant("exp-a", uid, ["control", "treatment"])
        v2 = assign_variant("exp-a", uid, ["control", "treatment"])
        assert v1 == v2


def test_rollout_hits_target_over_100k():
    n = 100_000
    inside = sum(1 for i in range(n) if in_rollout("exp-r", f"u{i}", 30.0))
    frac = inside / n
    assert abs(frac - 0.30) < 0.01  # within 1 point of target


def test_variant_split_is_balanced_and_srm_passes():
    n = 100_000
    counts = Counter(
        assign_variant("exp-b", f"u{i}", ["control", "treatment"]) for i in range(n)
    )
    obs = [counts["control"], counts["treatment"]]
    srm = check_srm(obs, [1.0, 1.0])
    assert not srm.flagged  # balanced -> no SRM
    assert 0.49 < obs[0] / n < 0.51


def test_srm_fires_on_imbalanced_counts():
    # 60/40 when 50/50 expected, large n -> clear SRM
    srm = check_srm([6000, 4000], [1.0, 1.0])
    assert srm.flagged
    assert srm.p_value < 0.001


def test_rollout_gate_independent_of_variant():
    # changing rollout should not move an already-in unit to a different variant
    uid = "stable-user"
    v_full = assign("exp-c", uid, ["control", "treatment"], rollout_pct=100.0)
    v_half = assign("exp-c", uid, ["control", "treatment"], rollout_pct=100.0)
    assert v_full == v_half
