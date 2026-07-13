"""G0A exact-paper reproduction runner (v2, P1.2-B). EXPENSIVE.

Enforces the frozen cost rule (G): a durable append-only checkpoint OUTSIDE the
repo (crash-recoverable, duplicate-rejecting), a chunked wall-clock deadline that
can stop a long simulation mid-cell, an isolated-layer chaos prerequisite, and the
quantifier that PASS requires EVERY deciding size (200, 400) to satisfy the fast/
slow criterion for ALL its cells. N=100 is non-deciding: a single favorable N=100
cell can never decide the gate. Any incomplete deciding cell -> INCONCLUSIVE with
reason_code INCONCLUSIVE_BY_COST (a partial grid is never PASS/FAIL). Import-safe."""
from __future__ import annotations

import sys
import time

import numpy as np

from _contract_v2 import provenance, run_cli
from _custody import CheckpointLedger
from src.dynamics.fhn import FHNParams
from src.metrics.lyapunov import largest_lyapunov_isolated_layer
from src.metrics.sync import synchronized, time_averaged_error
from src.networks.switching import random_switching
from src.simulation.double_layer import DeadlineExceeded, SimConfig, initial_state, simulate

GATE = "G0A_exact_reproduction"
REPORT = "g0a_exact_v2.json"
FAST_MAX, SLOW_MIN = 25.0, 120.0


def _cfg(ctx):
    return (ctx.execution["g0a"], ctx.prereg["seed_blocks"]["g0a"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"],
            ctx.prereg["gates"][GATE]["cost_rule"], ctx.prereg["fhn"]["density_ratio"])


def plan(ctx):
    g, seeds, dt, tol, cost, density = _cfg(ctx)
    n = len(g["sizes"]) * len(g["T_swt_grid"]) * len(seeds)
    return {"gate": GATE, "params": g, "seeds": seeds, "switch_cells": n,
            "cost_rule": cost,
            "projected_cost": (f"EXPENSIVE: {n} FHN sims of {int(g['total_time']/dt)} steps "
                               f"(largest 4N={4*max(g['sizes'])}) + chaos cells; likely "
                               f"hours-to-days; deadline {cost['max_wall_time_seconds']}s. "
                               f"Deciding sizes {cost['deciding_sizes']}; N=100 non-deciding.")}


def gate_verdict(cells, seeds, T_grid, cost, timed_out):
    """Pure verdict from completed cell records (testable independently)."""
    deciding = cost["deciding_sizes"]
    switch = {(c["cell"]["N"], c["cell"]["T_swt"], c["cell"]["seed"]): c["result"]
              for c in cells if c["cell"]["kind"] == "switch"}
    chaos = {(c["cell"]["N"], c["cell"]["seed"]): c["result"]
             for c in cells if c["cell"]["kind"] == "chaos"}
    complete = not timed_out
    for N in deciding:
        for s in seeds:
            if (N, s) not in chaos:
                complete = False
            for T in T_grid:
                if (N, T, s) not in switch:
                    complete = False
    if not complete:
        return "INCONCLUSIVE", "INCONCLUSIVE_BY_COST", complete
    ok = True
    for N in deciding:
        if not all(chaos[(N, s)]["lambda_max"] > 0 for s in seeds):
            ok = False
        for T in T_grid:
            frac = float(np.mean([switch[(N, T, s)]["synced"] for s in seeds]))
            if T <= FAST_MAX and not (frac >= 0.5):
                ok = False
            if T >= SLOW_MIN and not (frac < 0.5):
                ok = False
    return ("PASS" if ok else "FAIL"), None, complete


def compute(ctx):
    g, seeds, dt, tol, cost, density = _cfg(ctx)
    prov_key = {"freeze": ctx.freeze_content_hash, "prereg": ctx.prereg_canonical_hash,
                "exec": ctx.execution_canonical_hash, "runner": ctx.runner_sha256}
    ledger = CheckpointLedger(ctx.out_dir / "g0a_checkpoint.jsonl", prov_key,
                              ["kind", "N", "T_swt", "seed"])
    t0 = time.time()
    deadline = cost["max_wall_time_seconds"]

    def abort():
        return time.time() - t0 > deadline

    timed_out = False
    try:
        for N in g["sizes"]:
            N_IL = int(round(density * N))
            p = FHNParams(N=N, sigma_inter=g["sigma_inter"])
            cfg = SimConfig(dt=dt, total_time=g["total_time"], record_every=g["record_every"])
            for seed in seeds:
                cell = {"kind": "chaos", "N": N, "T_swt": None, "seed": seed}
                if not ledger.has(cell):
                    x0l = np.random.default_rng(seed).uniform(-2, 2, size=2 * N)
                    lam = largest_lyapunov_isolated_layer(
                        p, x0l, dt=dt, n_steps=g["chaos_n_steps"],
                        renorm_every=g["chaos_renorm"], transient_steps=g["chaos_transient"])
                    ledger.append(cell, {"lambda_max": float(lam)})
            for seed in seeds:
                for T in g["T_swt_grid"]:
                    cell = {"kind": "switch", "N": N, "T_swt": T, "seed": seed}
                    if ledger.has(cell):
                        continue
                    dwell = int(round(T / dt))
                    n_epochs = int(np.ceil(g["total_time"] / T)) + 2
                    x0 = initial_state(N, np.random.default_rng(1000 + seed))
                    sched = random_switching(N, N_IL, dwell, n_epochs,
                                             np.random.default_rng(2000 + seed), f"T{T}")
                    res = simulate(p, sched, cfg, x0, chunk_steps=g["chunk_steps"],
                                   abort_check=abort)
                    ledger.append(cell, {
                        "synced": bool(synchronized(res.e12, tol["sync_threshold_E12"], tol["sync_tail_frac"])),
                        "tail_E12": float(time_averaged_error(res.e12, 1 - tol["sync_tail_frac"]))})
    except DeadlineExceeded:
        timed_out = True

    verdict, reason, complete = gate_verdict(ledger.completed(), seeds, g["T_swt_grid"],
                                             cost, timed_out)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "PASS iff EVERY deciding size (200,400) has chaos>0 and ALL "
                                     "fast T_swt<=25 frac>=0.5 and ALL slow T_swt>=120 frac<0.5; "
                                     "N=100 non-deciding; partial grid -> INCONCLUSIVE_BY_COST",
                                     reason_code=reason),
            "result": {"complete": complete, "timed_out": timed_out,
                       "n_completed_cells": ledger.n_completed(),
                       "checkpoint": str(ctx.out_dir / "g0a_checkpoint.jsonl"),
                       "deciding_sizes": cost["deciding_sizes"],
                       "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
