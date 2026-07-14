"""G0A exact-paper reproduction runner (v2). EXPENSIVE.

Cost/deadline (contract F/G): a SOFT wall-time budget (time.monotonic) bounds the
chaos prerequisite and the switching simulations; it is checked before each size,
before each seed/cell, and DURING both chaos (chunked Benettin) and switching
(chunked RK4). It is SOFT, not hard: a non-interruptible fsync or the final
checkpoint hashing can overshoot it, so elapsed time and any overshoot are recorded
rather than pretended away. Deciding sizes {200,400} run FIRST; N=100 cannot consume
budget before them.

Failure precedence (contract F, frozen, highest first): (1) corrupt/invalid contract
-> EXECUTION_INVALID; (2) >20% technical failures OR zero-success in ANY observable
required cell -> EXECUTION_INVALID (this OUTRANKS cost: a recorded technical failure
is never laundered into INCONCLUSIVE_BY_COST); (3) otherwise, cells missing under a
CLEAN deadline -> INCONCLUSIVE(INCONCLUSIVE_BY_COST); (4) missing WITHOUT a deadline
-> EXECUTION_INVALID; (5) complete grid -> PASS/FAIL. An external signal/crash
(KeyboardInterrupt/SystemExit) propagates and is NEVER converted into a result.

Custody: append-only hash-chained checkpoint ledger OUTSIDE the repo
(duplicate-rejecting, truncation-detecting). The checkpoint is EVIDENCE of what ran,
NOT a resume input: there is no resume and an interrupted attempt is terminal.
Import-safe."""
from __future__ import annotations

import hashlib
import sys
import time

import numpy as np

from _contract_v2 import failure_record, provenance, run_cli
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
                               f"+ chaos cells; SOFT budget {cost['max_wall_time_seconds']}s "
                               f"bounds chaos+switching (checked before/within cells); a "
                               f"non-interruptible fsync/final-hash may overshoot it; "
                               f"deciding sizes run first.")}


def gate_verdict(cells, seeds, T_grid, cost, interrupted_by_cost):
    """Structured verdict (contract F). Distinguishes: failed cell (technical),
    missing cell, incomplete-by-cost, and success. The INTERRUPTED_BY_COST state
    record is NOT a scientific cell. Returns (verdict, reason_code, detail)."""
    deciding = cost["deciding_sizes"]
    # index only genuine science cells (ignore kind=="state")
    switch, chaos = {}, {}
    for c in cells:
        k = c["cell"]["kind"]
        if k == "switch":
            switch[(c["cell"]["N"], c["cell"]["T_swt"], c["cell"]["seed"])] = c["result"]
        elif k == "chaos":
            chaos[(c["cell"]["N"], c["cell"]["seed"])] = c["result"]

    def _failed(res):
        return bool(res.get("failed"))

    # PRECEDENCE 2 (contract F): >20% technical failures OR zero-success in ANY
    # OBSERVABLE (present) required cell -> EXECUTION_INVALID, evaluated over the
    # seeds actually RECORDED for the cell. The cost paths re-raise BEFORE appending
    # a failed record, so a recorded technical failure is never a deadline artifact;
    # this check therefore OUTRANKS both the missing check and the cost path and a
    # technical failure can never be reported as INCONCLUSIVE_BY_COST. This ordering
    # is why {a >20%-failed cell + another missing + interrupted_by_cost} resolves to
    # EXECUTION_INVALID, never INCONCLUSIVE_BY_COST.
    def _invalidating(observed):
        obs = len(observed)
        if obs == 0:
            return False                     # not observable -> handled by the missing check
        nfail = sum(_failed(r) for r in observed)
        return (nfail / obs) > 0.2 or (obs - nfail) == 0

    for N in deciding:
        chaos_obs = [chaos[(N, s)] for s in seeds if (N, s) in chaos]
        if _invalidating(chaos_obs):
            nf = sum(_failed(r) for r in chaos_obs)
            return "EXECUTION_INVALID", "FAILED_RUNS", {
                "chaos_failed": {"N": N, "observed": len(chaos_obs), "failed": nf}}
        for T in T_grid:
            sw_obs = [switch[(N, T, s)] for s in seeds if (N, T, s) in switch]
            if _invalidating(sw_obs):
                nf = sum(_failed(r) for r in sw_obs)
                return "EXECUTION_INVALID", "FAILED_RUNS", {
                    "cell_failed": {"N": N, "T": T, "observed": len(sw_obs), "failed": nf}}

    # PRECEDENCE 3/4: required cells missing. Cost ONLY under a clean deadline;
    # missing WITHOUT a deadline is an unexplained missing result -> EXECUTION_INVALID.
    missing = []
    for N in deciding:
        for s in seeds:
            if (N, s) not in chaos:
                missing.append(("chaos", N, None, s))
            for T in T_grid:
                if (N, T, s) not in switch:
                    missing.append(("switch", N, T, s))
    if missing:
        if interrupted_by_cost:
            return "INCONCLUSIVE", "INCONCLUSIVE_BY_COST", {"missing": len(missing)}
        return "EXECUTION_INVALID", "FAILED_RUNS", {"missing_unexplained": missing[:20]}

    # PRECEDENCE 5: complete grid, no invalidating failure -> decide PASS/FAIL over
    # the SUCCESSFUL seeds only (reduced n disclosed via the checkpoint).
    ok = True
    disclosure = {}
    for N in deciding:
        lam_ok = all(chaos[(N, s)]["lambda_max"] > 0
                     for s in seeds if not _failed(chaos[(N, s)]))
        if not lam_ok:
            ok = False
        for T in T_grid:
            good = [switch[(N, T, s)]["synced"] for s in seeds if not _failed(switch[(N, T, s)])]
            frac = float(np.mean(good))
            disclosure[f"N{N}_T{T}"] = {"frac_synced": frac, "n_successful": len(good)}
            if T <= FAST_MAX and not (frac >= 0.5):
                ok = False
            if T >= SLOW_MIN and not (frac < 0.5):
                ok = False
    return ("PASS" if ok else "FAIL"), None, {"disclosure": disclosure}


def compute(ctx):
    g, seeds, dt, tol, cost, density = _cfg(ctx)
    prov_key = {"freeze": ctx.freeze_content_hash, "prereg": ctx.prereg_canonical_hash,
                "exec": ctx.execution_canonical_hash, "runner": ctx.runner_sha256,
                "scope": ctx.execution_scope, "attempt": ctx.attempt_id}
    ledger = CheckpointLedger(ctx.out_dir / "g0a_checkpoint.jsonl", prov_key,
                              ["kind", "N", "T_swt", "seed"])
    t0 = time.monotonic()                     # monotonic: immune to wall-clock jumps (G)
    soft_deadline = cost["max_wall_time_seconds"]

    def over_budget():
        # SOFT budget: a non-interruptible fsync or the final hashing can overshoot.
        return time.monotonic() - t0 > soft_deadline

    interrupted_by_cost = False
    failures = []
    sizes = _size_order(g["sizes"], cost["deciding_sizes"])
    try:
        for N in sizes:
            if over_budget():                       # before each size
                raise DeadlineExceeded(f"budget exhausted before size N={N}")
            for seed in seeds:
                if over_budget():                   # before each chaos seed
                    raise DeadlineExceeded(f"budget exhausted before chaos N={N} seed={seed}")
                cell = {"kind": "chaos", "N": N, "T_swt": None, "seed": seed}
                if ledger.has(cell):
                    continue
                try:
                    # RNG/initial state + cell-dependent params INSIDE the per-seed
                    # try (contract G): a construction error becomes a failure record,
                    # never an escape.
                    p = FHNParams(N=N, sigma_inter=g["sigma_inter"])
                    x0l = np.random.default_rng(seed).uniform(-2, 2, size=2 * N)
                    lam = largest_lyapunov_isolated_layer(
                        p, x0l, dt=dt, n_steps=g["chaos_n_steps"],
                        renorm_every=g["chaos_renorm"], transient_steps=g["chaos_transient"],
                        chunk_steps=g["chunk_steps"], abort_check=over_budget)
                    if not np.isfinite(lam):
                        raise FloatingPointError("nonfinite lambda_max")
                except (DeadlineExceeded, LyapunovDeadlineExceeded):
                    raise                                    # cost, not a technical failure
                except (KeyboardInterrupt, SystemExit):
                    raise                                    # external interruption -> no result
                except Exception as e:                       # technical chaos failure
                    failures.append(failure_record(e, seed, {"kind": "chaos", "N": N}))
                    ledger.append(cell, {"failed": True, "error": type(e).__name__})
                    continue
                ledger.append(cell, {"lambda_max": float(lam)})
            for seed in seeds:
                for T in g["T_swt_grid"]:
                    if over_budget():               # before each switching cell
                        raise DeadlineExceeded(f"budget exhausted before N={N} T={T} seed={seed}")
                    cell = {"kind": "switch", "N": N, "T_swt": T, "seed": seed}
                    if ledger.has(cell):
                        continue
                    try:
                        # cell-dependent params, RNG/initial state and schedule build
                        # ALL inside the per-seed try (contract G).
                        p = FHNParams(N=N, sigma_inter=g["sigma_inter"])
                        cfg = SimConfig(dt=dt, total_time=g["total_time"],
                                        record_every=g["record_every"])
                        N_IL = int(round(density * N))
                        dwell = int(round(T / dt))
                        n_epochs = int(np.ceil(g["total_time"] / T)) + 2
                        x0 = initial_state(N, np.random.default_rng(1000 + seed))
                        sched = random_switching(N, N_IL, dwell, n_epochs,
                                                 np.random.default_rng(2000 + seed), f"T{T}")
                        res = simulate(p, sched, cfg, x0, chunk_steps=g["chunk_steps"],
                                       abort_check=over_budget)
                        if not np.all(np.isfinite(res.e12)):
                            raise FloatingPointError("nonfinite E12")
                    except (DeadlineExceeded, LyapunovDeadlineExceeded):
                        raise                                    # cost path
                    except (KeyboardInterrupt, SystemExit):
                        raise                                    # external interruption -> no result
                    except Exception as e:                       # technical switch failure
                        failures.append(failure_record(e, seed, {"kind": "switch", "N": N, "T_swt": T}))
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
    # KeyboardInterrupt / SystemExit / any other exception propagates: an external
    # interruption or crash is NOT cost exhaustion and must not become a result.

    over_budget_at_seal = over_budget()          # measured BEFORE serialization (G)
    cp_path = ctx.out_dir / "g0a_checkpoint.jsonl"
    cp_sha = (hashlib.sha256(cp_path.read_bytes()).hexdigest()
              if cp_path.exists() else None)
    elapsed = time.monotonic() - t0              # measured AFTER serialization (G)
    overshoot = max(0.0, elapsed - soft_deadline)

    records = ledger.completed()
    n_ledger_records = len(records)
    n_state_records = sum(1 for c in records if c["cell"]["kind"] == "state")
    n_science_cells = n_ledger_records - n_state_records   # excludes kind=="state"
    verdict, reason, detail = gate_verdict(records, seeds, g["T_swt_grid"],
                                           cost, interrupted_by_cost)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "PASS iff EVERY deciding size has chaos>0 and ALL fast "
                                     "T_swt<=25 frac>=0.5 and ALL slow T_swt>=120 frac<0.5 (over "
                                     "successful seeds); N=100 non-deciding; deciding sizes first. "
                                     "FROZEN precedence (highest first): >20% technical failures or "
                                     "zero-success in any observable required cell -> EXECUTION_INVALID "
                                     "(OUTRANKS cost); else missing under a clean deadline -> "
                                     "INCONCLUSIVE_BY_COST; missing without a deadline -> EXECUTION_INVALID; "
                                     "external interruption -> no result",
                                     reason_code=reason, failures=failures),
            "result": {"interrupted_by_cost": interrupted_by_cost,
                       "n_ledger_records": n_ledger_records,
                       "n_science_cells": n_science_cells,      # excludes kind=="state"
                       "n_state_records": n_state_records,
                       "soft_deadline_seconds": soft_deadline,
                       "elapsed_seconds": elapsed,
                       "overshoot_seconds": overshoot,
                       "over_budget_at_seal": over_budget_at_seal,
                       "checkpoint_name": "g0a_checkpoint.jsonl",   # RELATIVE (C.3)
                       "checkpoint_sha256": cp_sha,
                       "size_order": sizes, "deciding_sizes": cost["deciding_sizes"],
                       "detail": detail,
                       "label": "EXACT_PAPER_REPRODUCTION (sigma_12=0.1)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
