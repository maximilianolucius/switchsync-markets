"""G0B CALIBRATED DEMONSTRATION runner (v2, P1.2-B). sigma_12=1.5, N=40.

Frozen semantics (H): fast = ALL cells with T_swt<=10 synchronize; slow = ALL
cells with T_swt>=160 do NOT. >20% failed/nonfinite seeds in any cell ->
EXECUTION_INVALID. This is a CALIBRATED DEMONSTRATION, never a reproduction, and
makes no N-dependence claim. Import-safe."""
from __future__ import annotations

import sys

from _contract_v2 import provenance, run_cli
from _repro_common_v2 import frac_synced_grid

GATE = "G0B_calibrated_demonstration"
REPORT = "g0b_calibrated_v2.json"
SCOPE = "individual:G0B"


def _cfg(ctx):
    return (ctx.execution["g0b"], ctx.prereg["seed_blocks"]["g0b"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"])


def plan(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    n = len(g["T_swt_grid"]) * len(seeds)
    return {"gate": GATE, "label": "CALIBRATED DEMONSTRATION (NOT reproduction)",
            "params": {k: g[k] for k in ("N", "N_IL", "sigma_inter", "total_time", "T_swt_grid")},
            "seeds": seeds, "simulations": n, "fast_semantics": "ALL", "slow_semantics": "ALL",
            "projected_cost": f"{n} FHN sims of {int(g['total_time']/dt)} steps; minutes total."}


def compute(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    rows = frac_synced_grid(g["N"], g["N_IL"], g["sigma_inter"], g["T_swt_grid"],
                            g["total_time"], dt, g["record_every"], seeds,
                            tol["sync_threshold_E12"], tol["sync_tail_frac"])
    failures = [fr for r in rows for fr in r["failure_records"]]
    if any(r["frac_failed"] > 0.2 for r in rows):
        return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                "provenance": provenance(ctx, seeds, g, ">20% failed/nonfinite seeds in a cell",
                                         reason_code="FAILED_RUNS", failures=failures),
                "result": {"rows": rows}}
    by_T = {r["T_swt"]: r for r in rows}
    fast_all = all(by_T[t]["frac_synced"] is not None and by_T[t]["frac_synced"] >= 0.5
                   for t in g["T_swt_grid"] if t <= 10)
    slow_all = all(by_T[t]["frac_synced"] is not None and by_T[t]["frac_synced"] < 0.5
                   for t in g["T_swt_grid"] if t >= 160)
    verdict = "PASS" if (fast_all and slow_all) else "FAIL"
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "DEMONSTRATED(=PASS) iff ALL fast T_swt<=10 sync AND ALL slow "
                                     "T_swt>=160 do not (ALL semantics); calibrated demo, not reproduction",
                                     failures=failures),
            "result": {"rows": rows, "fast_all_sync": fast_all, "slow_all_not_sync": slow_all,
                       "frac_synced_denominator": ("SUCCESSFUL_SEEDS_ONLY (frozen; failed "
                                                   "seeds are excluded from the denominator "
                                                   "and disclosed per cell)"),
                       "label": "CALIBRATED_QUALITATIVE_DEMONSTRATION (NOT paper reproduction)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
