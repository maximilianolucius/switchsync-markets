"""G0A exact-paper reproduction runner (v2). Paper regime (sigma_12=0.1, paper-scale
N, T=4000). EXPENSIVE: declares its projected cost up front. Never a substitute
for G0B. Outcome may be INCONCLUSIVE (recorded here as INCONCLUSIVE) if the run is
not affordable.

Import-safe; full run gated by the execution contract."""
from __future__ import annotations

import sys

from _contract_v2 import provenance, run_cli
from _repro_common_v2 import frac_synced_grid

GATE = "G0A_exact_reproduction"
REPORT = "g0a_exact_v2.json"


def _cfg(ctx):
    return (ctx.prereg["gates"][GATE], ctx.prereg["seed_blocks"]["g0a"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"])


def plan(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    steps = int(g["total_time"] / dt)
    n = len(g["sizes"]) * len(g["T_swt_grid"]) * len(seeds)
    biggest = max(g["sizes"])
    return {"gate": GATE,
            "params": {k: g[k] for k in ("sizes", "sigma_inter", "density_ratio",
                                         "T_swt_grid", "total_time")},
            "seeds": seeds, "simulations": n,
            "projected_cost": (f"EXPENSIVE: {n} FHN simulations of {steps} steps; "
                               f"largest state 4*N={4*biggest} dims at N={biggest}. "
                               f"Order 1e5 steps x 1e3 dims x {n} runs -> likely hours-to-days. "
                               f"If unaffordable, the authorized verdict is INCONCLUSIVE.")}


def compute(ctx):
    g, seeds, dt, tol = _cfg(ctx)
    per_size = {}
    for N in g["sizes"]:
        N_IL = int(round(g["density_ratio"] * N))
        rows = frac_synced_grid(N, N_IL, g["sigma_inter"], g["T_swt_grid"],
                                g["total_time"], dt, g["record_every"], seeds,
                                tol["sync_threshold_E12"], tol["sync_tail_frac"])
        per_size[str(N)] = rows
    fast_sync = any(r["frac_synced"] >= 0.5 for N in per_size
                    for r in per_size[N] if r["T_swt"] <= 25)
    slow_no = all(r["frac_synced"] < 0.5 for N in per_size
                  for r in per_size[N] if r["T_swt"] >= 120)
    verdict = "PASS" if (fast_sync and slow_no) else "FAIL"
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "exact-paper regime sigma_12=0.1; PASS iff fast (T_swt<=25) "
                                     "syncs and slow (T_swt>=120) does not; INCONCLUSIVE if unaffordable"),
            "result": {"by_size": per_size,
                       "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
