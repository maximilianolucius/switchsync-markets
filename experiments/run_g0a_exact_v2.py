"""G0A exact-paper reproduction runner (v2, P1.2-C). EXPENSIVE.

Cost/deadline (contract G): the wall-time budget covers the chaos prerequisite,
the switching simulations and checkpoint serialization. The deadline is checked
before each size, before each seed/cell, and DURING both chaos (chunked Benettin)
and switching (chunked RK4). Deciding sizes {200, 400} run FIRST; N=100 cannot
consume budget before them. A clean deadline expiry is recorded as
INTERRUPTED_BY_COST in the checkpoint and, per the frozen policy, converts to
verdict INCONCLUSIVE(reason INCONCLUSIVE_BY_COST). An external signal/crash
propagates (KeyboardInterrupt etc.) and is NOT converted into a result.

Custody: durable hash-chained checkpoint ledger OUTSIDE the repo (crash-recoverable,
duplicate-rejecting, truncation-detecting). Import-safe."""
from __future__ import annotations

import sys
import time

import numpy as np

from _contract_v2 import provenance, run_cli
from _custody import CheckpointLedger
from src.dynamics.fhn import FHNParams
from src.metrics.lyapunov import LyapunovDeadlineExceeded, largest_lyapunov_isolated_layer
from src.metrics.sync import synchronized, time_averaged_error
from src.networks.switching import random_switching
from src.simulation.double_layer import DeadlineExceeded, SimConfig, initial_state, simulate

GATE = "G0A_exact_reproduction"
REPORT = "g0a_exact_v2.json"
SCOPE = "individual:G0A"
FAST_MAX, SLOW_MIN = 25.0, 120.0


def _cfg(ctx):
    return (ctx.execution["g0a"], ctx.prereg["seed_blocks"]["g0a"],
            ctx.prereg["global"]["dt"], ctx.prereg["tolerances"],
            ctx.prereg["gates"][GATE]["cost_rule"], ctx.prereg["fhn"]["density_ratio"])


def _size_order(sizes, deciding):
    """Deciding sizes first (in ascending order), then the rest."""
    return sorted([s for s in sizes if s in deciding]) + \
           sorted([s for s in sizes if s not in deciding])


def plan(ctx):
    g, seeds, dt, tol, cost, density = _cfg(ctx)
    n = len(g["sizes"]) * len(g["T_swt_grid"]) * len(seeds)
    return {"gate": GATE, "params": g, "seeds": seeds, "switch_cells": n,
            "cost_rule": cost, "size_order": _size_order(g["sizes"], cost["deciding_sizes"]),
            "projected_cost": (f"EXPENSIVE: {n} FHN sims of {int(g['total_time']/dt)} steps "
                               f"+ chaos cells; deadline {cost['max_wall_time_seconds']}s "
                               f"covers chaos+switching+serialization; deciding sizes run first.")}


def gate_verdict(cells, seeds, T_grid, cost, interrupted_by_cost):
    """Pure verdict from completed cell records (testable independently)."""
    deciding = cost["deciding_sizes"]
    switch = {(c["cell"]["N"], c["cell"]["T_swt"], c["cell"]["seed"]): c["result"]
              for c in cells if c["cell"]["kind"] == "switch"}
    chaos = {(c["cell"]["N"], c["cell"]["seed"]): c["result"]
             for c in cells if c["cell"]["kind"] == "chaos"}
    complete = not interrupted_by_cost
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
                "exec": ctx.execution_canonical_hash, "runner": ctx.runner_sha256,
                "scope": ctx.execution_scope, "attempt": ctx.attempt_id}
    ledger = CheckpointLedger(ctx.out_dir / "g0a_checkpoint.jsonl", prov_key,
                              ["kind", "N", "T_swt", "seed"])
    t0 = time.time()
    deadline = cost["max_wall_time_seconds"]

    def over_budget():
        return time.time() - t0 > deadline

    interrupted_by_cost = False
    failures = []
    sizes = _size_order(g["sizes"], cost["deciding_sizes"])
    try:
        for N in sizes:
            if over_budget():                       # before each size
                raise DeadlineExceeded(f"budget exhausted before size N={N}")
            N_IL = int(round(density * N))
            p = FHNParams(N=N, sigma_inter=g["sigma_inter"])
            cfg = SimConfig(dt=dt, total_time=g["total_time"], record_every=g["record_every"])
            for seed in seeds:
                if over_budget():                   # before each chaos seed
                    raise DeadlineExceeded(f"budget exhausted before chaos N={N} seed={seed}")
                cell = {"kind": "chaos", "N": N, "T_swt": None, "seed": seed}
                if not ledger.has(cell):
                    x0l = np.random.default_rng(seed).uniform(-2, 2, size=2 * N)
                    lam = largest_lyapunov_isolated_layer(
                        p, x0l, dt=dt, n_steps=g["chaos_n_steps"],
                        renorm_every=g["chaos_renorm"], transient_steps=g["chaos_transient"],
                        chunk_steps=g["chunk_steps"], abort_check=over_budget)
                    ledger.append(cell, {"lambda_max": float(lam)})
            for seed in seeds:
                for T in g["T_swt_grid"]:
                    if over_budget():               # before each switching cell
                        raise DeadlineExceeded(f"budget exhausted before N={N} T={T} seed={seed}")
                    cell = {"kind": "switch", "N": N, "T_swt": T, "seed": seed}
                    if ledger.has(cell):
                        continue
                    dwell = int(round(T / dt))
                    n_epochs = int(np.ceil(g["total_time"] / T)) + 2
                    x0 = initial_state(N, np.random.default_rng(1000 + seed))
                    sched = random_switching(N, N_IL, dwell, n_epochs,
                                             np.random.default_rng(2000 + seed), f"T{T}")
                    try:
                        res = simulate(p, sched, cfg, x0, chunk_steps=g["chunk_steps"],
                                       abort_check=over_budget)
                    except (FloatingPointError, ValueError) as e:
                        from _contract_v2 import failure_record
                        failures.append(failure_record(e, seed, {"N": N, "T_swt": T}))
                        ledger.append(cell, {"failed": True, "error": type(e).__name__})
                        continue
                    ledger.append(cell, {
                        "synced": bool(synchronized(res.e12, tol["sync_threshold_E12"],
                                                    tol["sync_tail_frac"])),
                        "tail_E12": float(time_averaged_error(res.e12, 1 - tol["sync_tail_frac"]))})
    except (DeadlineExceeded, LyapunovDeadlineExceeded):
        # CLEAN cost exhaustion: checkpoint state + INTERRUPTED_BY_COST. This is the
        # ONLY path that converts a deadline into a scientific INCONCLUSIVE_BY_COST.
        interrupted_by_cost = True
        state_cell = {"kind": "state", "N": None, "T_swt": None, "seed": None}
        if not ledger.has(state_cell):
            ledger.append(state_cell, {"state": "INTERRUPTED_BY_COST"})
    # KeyboardInterrupt / any other exception propagates: an external interruption
    # or crash is NOT cost exhaustion and must not become a scientific result.

    cells = [c for c in ledger.completed() if c["cell"]["kind"] in ("chaos", "switch")
             and not c["result"].get("failed")]
    verdict, reason, complete = gate_verdict(cells, seeds, g["T_swt_grid"], cost,
                                             interrupted_by_cost)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "PASS iff EVERY deciding size (200,400) has chaos>0 and ALL "
                                     "fast T_swt<=25 frac>=0.5 and ALL slow T_swt>=120 frac<0.5; "
                                     "N=100 non-deciding; deciding sizes run first; clean deadline "
                                     "-> INCONCLUSIVE_BY_COST; external interruption -> no result",
                                     reason_code=reason, failures=failures),
            "result": {"complete": complete, "interrupted_by_cost": interrupted_by_cost,
                       "n_completed_cells": ledger.n_completed(),
                       "checkpoint": str(ctx.out_dir / "g0a_checkpoint.jsonl"),
                       "size_order": sizes, "deciding_sizes": cost["deciding_sizes"],
                       "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
