"""P1.1 + Gate G0: chaos verification and the fast-vs-slow switching reproduction.

Reproduces (qualitatively) the paper's central result: at fixed density and
coupling, fast switching induces inter-layer synchronization and slow switching
does not. Also confirms the isolated layer is chaotic (lambda_max > 0).
"""
from __future__ import annotations

import numpy as np

from _common import REPORT_DIR, append_registry, atomic_write_json, load_contract
from src.dynamics.fhn import FHNParams
from src.metrics.lyapunov import largest_lyapunov_isolated_layer
from src.metrics.sync import synchronized, time_averaged_error, time_to_sync
from src.networks.switching import random_switching
from src.simulation.double_layer import SimConfig, initial_state, simulate
from src.validation.freeze import config_hash


def run_chaos_check(c: dict) -> dict:
    cc = c["chaos_check"]
    out = {}
    for N in cc["sizes"]:
        p = FHNParams(N=N)
        x0 = np.random.default_rng(7).uniform(-2, 2, size=2 * N)
        lam = largest_lyapunov_isolated_layer(
            p, x0, dt=cc["dt"], n_steps=cc["n_steps"],
            renorm_every=cc["renorm_every"], transient_steps=cc["transient_steps"])
        out[str(N)] = lam
    out["all_positive"] = bool(all(v > 0 for k, v in out.items() if k != "all_positive"))
    return out


def run_reproduction(c: dict) -> dict:
    r = c["reproduction"]
    N, N_IL = r["N"], r["N_IL"]
    dt = c["global"]["dt"]
    p = FHNParams(N=N, sigma_inter=r["sigma_inter"])
    cfg = SimConfig(dt=dt, total_time=r["total_time"], record_every=r["record_every"])
    thr = r["sync_threshold_E12"]

    rows = []
    for Tswt in r["T_swt_grid"]:
        dwell = int(round(Tswt / dt))
        n_epochs = int(np.ceil(r["total_time"] / Tswt)) + 2
        sync_flags, tails, tts = [], [], []
        for seed in r["seeds"]:
            x0 = initial_state(N, np.random.default_rng(1000 + seed))
            sched = random_switching(N, N_IL, dwell, n_epochs,
                                     np.random.default_rng(2000 + seed),
                                     label=f"T{Tswt}")
            res = simulate(p, sched, cfg, x0)
            sync_flags.append(synchronized(res.e12, thr, r["sync_tail_frac"]))
            tails.append(time_averaged_error(res.e12, 1 - r["sync_tail_frac"]))
            t = time_to_sync(res.e12, dt, r["record_every"], thr)
            tts.append(t if t is not None else None)
        rows.append({
            "T_swt": Tswt,
            "frac_synced": float(np.mean(sync_flags)),
            "mean_tail_E12": float(np.mean(tails)),
            "time_to_sync": [None if t is None else round(t, 1) for t in tts],
        })
    return {"rows": rows}


def evaluate_g0(chaos: dict, repro: dict, c: dict) -> tuple[str, str]:
    r = c["reproduction"]
    by_T = {row["T_swt"]: row for row in repro["rows"]}
    fast_synced = any(by_T[T]["frac_synced"] >= 0.5 for T in r["T_swt_grid"] if T <= 10)
    slow_not = all(by_T[T]["frac_synced"] < 0.5 for T in r["T_swt_grid"] if T >= 160)
    chaos_ok = chaos["all_positive"]
    if chaos_ok and fast_synced and slow_not:
        return "PASS", "chaos confirmed; fast switching synchronizes, slow does not"
    return "FAIL", (f"chaos_ok={chaos_ok} fast_synced={fast_synced} slow_not={slow_not}")


def main() -> None:
    c = load_contract()
    h = config_hash(c)
    chaos = run_chaos_check(c)
    repro = run_reproduction(c)
    verdict, summary = evaluate_g0(chaos, repro, c)
    result = {"experiment": "reproduction_g0", "config_hash": h,
              "chaos_check": chaos, "reproduction": repro,
              "gate": "G0", "verdict": verdict, "summary": summary}
    out = REPORT_DIR / "reproduction_g0.json"
    atomic_write_json(out, result)
    append_registry({"experiment": "reproduction_g0", "config_hash": h,
                     "result_file": str(out.relative_to(out.parents[2])),
                     "gate": "G0", "verdict": verdict, "summary": summary})
    print(f"chaos lambda_max: {chaos}")
    for row in repro["rows"]:
        print(f"  T_swt={row['T_swt']:6.1f}  frac_synced={row['frac_synced']:.2f}  "
              f"mean_tail_E12={row['mean_tail_E12']:.4f}")
    print(f"G0 verdict: {verdict} - {summary}")


if __name__ == "__main__":
    main()
