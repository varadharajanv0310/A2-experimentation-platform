"""Live end-to-end gate driver against a running API + seeded DB.
Prints PASS/FAIL per gate item; exit 0 only if all pass."""

from __future__ import annotations

import sys

import httpx

BASE = "http://localhost:8002"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{' — ' + detail if detail else ''}")


def main() -> int:
    c = httpx.Client(timeout=30)

    health = c.get(f"{BASE}/api/health").json()
    check("api reachable", health.get("ok") is True)

    exps = c.get(f"{BASE}/api/experiments").json()
    keys = {e["key"] for e in exps}
    check("seeded experiments present", len(exps) >= 3, f"{len(exps)} experiments")

    # deterministic assignment
    a1 = c.post(f"{BASE}/api/assign", json={"experiment_key": "checkout-redesign", "unit_id": "verify-u1"}).json()
    a2 = c.post(f"{BASE}/api/assign", json={"experiment_key": "checkout-redesign", "unit_id": "verify-u1"}).json()
    check("assignment deterministic (same unit -> same variant)", a1["variant"] == a2["variant"], a1["variant"])

    # primary metric significant with recovered effect near seeded 0.12
    r = c.get(f"{BASE}/api/experiments/checkout-redesign/results", params={"metric": "revenue"}).json()
    p = r["pooled"]
    check("real effect detected (checkout revenue)", p["significant"] and p["ci_lower"] > 0,
          f"effect={p['effect']:.3f} CI=[{p['ci_lower']:.3f},{p['ci_upper']:.3f}]")
    check("SRM passes on balanced traffic", not r["srm"]["flagged"], f"p={r['srm']['p_value']:.3f}")

    # CUPED reduces variance
    rc = c.get(f"{BASE}/api/experiments/checkout-redesign/results", params={"metric": "revenue", "cuped": "true"}).json()
    vr = rc["pooled"].get("cuped_variance_reduction", 0.0)
    check("CUPED reduces variance materially", vr > 0.2, f"{vr*100:.1f}% reduction")

    # guardrail fires on the promo-banner latency regression
    rg = c.get(f"{BASE}/api/experiments/promo-banner/results", params={"metric": "clicks"}).json()
    fired = any(g["flagged"] for g in rg["guardrails"])
    check("guardrail flag fires on seeded degradation", fired,
          str([(g["metric"], g["flagged"]) for g in rg["guardrails"]]))

    # segment slicing present (heterogeneous effects)
    check("segment slices computed", len(r["segments"]) >= 1, f"segments={list(r['segments'].keys())}")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} live gate checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
