"""G0B CALIBRATED DEMONSTRATION runner (v2). sigma_12=1.5, N=40 -- a calibrated
demonstration of the fast-vs-slow mechanism, NEVER a reproduction of the paper's
regime. It must not claim an N-dependence of the switching threshold (no multi-N
switching grid is run here).

Import-safe; full run gated by the execution contract."""
from __future__ import annotations

import sys

from _contract_v2 import provenance, run_cli
from _repro_common_v2 import frac_synced_grid

GATE = "G0B_calibrated_demonstration"
REPORT = "g0b_calibrated_v2.json"


def _cfg(ctx):
    return (ctx.execution["g0b"], ctx.prereg["seed_blocks"]["g0b"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"])


def plan(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    steps = int(g["total_time"] / dt)
    n = len(g["T_swt_grid"]) * len(seeds)
    return {"gate": GATE, "label": "CALIBRATED DEMONSTRATION (NOT reproduction)",
            "params": {k: g[k] for k in ("N", "N_IL", "sigma_inter", "total_time",
                                         "T_swt_grid")},
            "seeds": seeds, "simulations": n,
            "projected_cost": f"{n} FHN sims of {steps} steps on 4*N={4*g['N']} dims; minutes total."}


def compute(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    rows = frac_synced_grid(g["N"], g["N_IL"], g["sigma_inter"], g["T_swt_grid"],
                            g["total_time"], dt, g["record_every"], seeds,
                            tol["sync_threshold_E12"], tol["sync_tail_frac"])
    by_T = {r["T_swt"]: r for r in rows}
    fast = any(by_T[t]["frac_synced"] >= 0.5 for t in g["T_swt_grid"] if t <= 10)
    slow = all(by_T[t]["frac_synced"] < 0.5 for t in g["T_swt_grid"] if t >= 160)
    # DEMONSTRATED -> PASS, NOT_DEMONSTRATED -> FAIL (contract verdict vocabulary)
    verdict = "PASS" if (fast and slow) else "FAIL"
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "calibrated demonstration (sigma_12=1.5, N=40); "
                                     "DEMONSTRATED(=PASS) iff fast T_swt<=10 syncs AND slow "
                                     "T_swt>=160 does not; no N-dependence claim permitted"),
            "result": {"rows": rows,
                       "label": "CALIBRATED_QUALITATIVE_DEMONSTRATION (NOT paper reproduction)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
