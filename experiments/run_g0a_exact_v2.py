"""G0A exact-paper reproduction runner (v2, P1.2-A). Paper regime (sigma_12=0.1,
paper-scale N, T=4000). EXPENSIVE. Enforces the frozen G0A cost rule: a wall-time
budget, an append-only checkpoint of completed (N, T_swt, seed) cells, and the
hard rule that a partial/incomplete grid is INCONCLUSIVE with reason_code
INCONCLUSIVE_BY_COST -- never PASS or FAIL. Import-safe."""
from __future__ import annotations

import sys
import time

import numpy as np

from _contract_v2 import provenance, run_cli
from src.dynamics.fhn import FHNParams
from src.metrics.sync import synchronized, time_averaged_error
from src.networks.switching import random_switching
from src.simulation.double_layer import SimConfig, initial_state, simulate

GATE = "G0A_exact_reproduction"
REPORT = "g0a_exact_v2.json"


def _cfg(ctx):
    return (ctx.execution["g0a"], ctx.prereg["seed_blocks"]["g0a"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"],
            ctx.prereg["g0a_cost_rule"])


def plan(ctx):
    g, seeds, dt, tol, cost = _cfg(ctx)
    steps = int(g["total_time"] / dt)
    n = len(g["sizes"]) * len(g["T_swt_grid"]) * len(seeds)
    return {"gate": GATE, "params": g, "seeds": seeds, "simulations": n,
            "cost_rule": cost,
            "projected_cost": (f"EXPENSIVE: {n} FHN sims of {steps} steps; largest 4*N="
                               f"{4*max(g['sizes'])} dims. Likely hours-to-days; the frozen "
                               f"wall-time budget is {cost['max_wall_time_seconds']}s. A partial "
                               f"grid is INCONCLUSIVE(INCONCLUSIVE_BY_COST), never PASS/FAIL.")}


def compute(ctx):
    g, seeds, dt, tol, cost = _cfg(ctx)
    max_wall = cost["max_wall_time_seconds"]
    density = ctx.prereg["fhn"]["density_ratio"]
    t0 = time.time()
    completed = []            # append-only checkpoint of (N, T_swt, seed)
    timed_out = False
    per_size = {}
    total_cells = len(g["sizes"]) * len(g["T_swt_grid"]) * len(seeds)

    for N in g["sizes"]:
        N_IL = int(round(density * N))
        p = FHNParams(N=N, sigma_inter=g["sigma_inter"])
        cfg = SimConfig(dt=dt, total_time=g["total_time"], record_every=g["record_every"])
        rows = []
        for T_swt in g["T_swt_grid"]:
            dwell = int(round(T_swt / dt))
            n_epochs = int(np.ceil(g["total_time"] / T_swt)) + 2
            flags, tails, done_seeds = [], [], []
            for seed in seeds:
                if time.time() - t0 > max_wall:
                    timed_out = True
                    break
                x0 = initial_state(N, np.random.default_rng(1000 + seed))
                sched = random_switching(N, N_IL, dwell, n_epochs,
                                         np.random.default_rng(2000 + seed), f"T{T_swt}")
                res = simulate(p, sched, cfg, x0)
                flags.append(synchronized(res.e12, tol["sync_threshold_E12"], tol["sync_tail_frac"]))
                tails.append(time_averaged_error(res.e12, 1 - tol["sync_tail_frac"]))
                done_seeds.append(seed)
                completed.append([N, T_swt, seed])
            rows.append({"T_swt": float(T_swt), "completed_seeds": done_seeds,
                         "frac_synced": float(np.mean(flags)) if flags else None,
                         "mean_tail_E12": float(np.mean(tails)) if tails else None})
            if timed_out:
                break
        per_size[str(N)] = rows
        if timed_out:
            break

    n_completed = len(completed)
    grid_complete = (n_completed == total_cells)
    if not grid_complete:
        # partial grid: NEVER PASS/FAIL (frozen cost rule)
        return {"gate": GATE, "verdict": "INCONCLUSIVE",
                "provenance": provenance(ctx, seeds, g,
                                         "partial grid under the frozen cost rule cannot be "
                                         "PASS/FAIL; only INCONCLUSIVE(INCONCLUSIVE_BY_COST)",
                                         reason_code="INCONCLUSIVE_BY_COST"),
                "result": {"by_size": per_size, "completed_cells": completed,
                           "total_cells": total_cells, "timed_out": timed_out,
                           "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1) — INCOMPLETE"}}

    fast = any(r["frac_synced"] and r["frac_synced"] >= 0.5
               for N in per_size for r in per_size[N] if r["T_swt"] <= 25)
    slow = all((r["frac_synced"] or 0.0) < 0.5
               for N in per_size for r in per_size[N] if r["T_swt"] >= 120)
    verdict = "PASS" if (fast and slow) else "FAIL"
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "complete grid: PASS iff fast (T_swt<=25) syncs and slow "
                                     "(T_swt>=120) does not"),
            "result": {"by_size": per_size, "completed_cells": completed,
                       "total_cells": total_cells,
                       "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
