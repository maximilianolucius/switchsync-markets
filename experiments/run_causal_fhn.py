"""Gate G1 in the FHN system (not just the surrogate): compare fast switching
against slow, static-sparse and the average graph at FIXED coupling, density and
occupancy. Confirms the surrogate's causal decomposition holds in the nonlinear
model."""
from __future__ import annotations

import numpy as np

from _common import REPORT_DIR, append_registry, atomic_write_json, load_contract
from src.dynamics.fhn import FHNParams
from src.metrics.sync import time_averaged_error
from src.networks.switching import random_switching, shuffle_order, static_sparse
from src.simulation.double_layer import (
    SimConfig,
    initial_state,
    simulate,
    simulate_fixed_gamma,
)
from src.validation.freeze import config_hash


def run(c: dict) -> dict:
    cf = c["causal_fhn"]
    N, N_IL = cf["N"], cf["N_IL"]
    dt = c["global"]["dt"]
    p = FHNParams(N=N, sigma_inter=cf["sigma_inter"])
    cfg = SimConfig(dt=dt, total_time=cf["total_time"], record_every=cf["record_every"])
    Tf, Ts = cf["T_swt_fast"], cf["T_swt_slow"]

    per_seed = {}
    for seed in cf["seeds"]:
        x0 = initial_state(N, np.random.default_rng(3000 + seed))
        rng = lambda o: np.random.default_rng(seed * 100 + o)
        fast = random_switching(N, N_IL, int(round(Tf / dt)),
                                int(np.ceil(cf["total_time"] / Tf)) + 2, rng(1), "fast")
        slow = random_switching(N, N_IL, int(round(Ts / dt)),
                                int(np.ceil(cf["total_time"] / Ts)) + 2, rng(2), "slow")
        stat = static_sparse(N, N_IL, int(cf["total_time"] / dt), rng(3), "static_sparse")
        sh = shuffle_order(fast, rng(4), "shuffled_order")
        occ = fast.occupancy()

        def tail(sched=None, gamma=None):
            if gamma is not None:
                res = simulate_fixed_gamma(p, gamma, cfg, x0)
            else:
                res = simulate(p, sched, cfg, x0)
            return time_averaged_error(res.e12, 0.75)

        per_seed[str(seed)] = {
            "fast": tail(sched=fast),
            "slow": tail(sched=slow),
            "static_sparse": tail(sched=stat),
            "shuffled_order_fast": tail(sched=sh),
            "average_graph": tail(gamma=occ),
        }
    keys = list(next(iter(per_seed.values())).keys())
    agg = {k: {"mean": float(np.mean([per_seed[s][k] for s in per_seed])),
               "std": float(np.std([per_seed[s][k] for s in per_seed]))} for k in keys}
    return {"per_seed": per_seed, "aggregate": agg}


def evaluate(res: dict) -> dict:
    a = res["aggregate"]
    # lower E12 = better (more synchronized). fast should be << static & slow.
    fast_beats_static = a["fast"]["mean"] < a["static_sparse"]["mean"] - 0.02
    fast_beats_slow = a["fast"]["mean"] < a["slow"]["mean"] - 0.02
    verdict = "PASS" if (fast_beats_static and fast_beats_slow) else "FAIL"
    vs_avg = a["average_graph"]["mean"] - a["fast"]["mean"]
    return {"verdict": verdict,
            "fast_E12": a["fast"]["mean"], "slow_E12": a["slow"]["mean"],
            "static_E12": a["static_sparse"]["mean"],
            "average_graph_E12": a["average_graph"]["mean"],
            "avg_graph_minus_fast": vs_avg,
            "note": "lower E12 = more synchronized; fast should beat static & slow"}


def main() -> None:
    c = load_contract()
    h = config_hash(c)
    res = run(c)
    ev = evaluate(res)
    result = {"experiment": "causal_fhn_g1", "config_hash": h, "results": res,
              "evaluation": ev, "gate": "G1", "verdict": ev["verdict"],
              "summary": str(ev)}
    out = REPORT_DIR / "causal_fhn_g1.json"
    atomic_write_json(out, result)
    append_registry({"experiment": "causal_fhn_g1", "config_hash": h,
                     "result_file": str(out.relative_to(out.parents[2])),
                     "gate": "G1", "verdict": ev["verdict"], "summary": str(ev)})
    for k, v in res["aggregate"].items():
        print(f"  {k:22s} E12={v['mean']:.4f} +/- {v['std']:.4f}")
    print(f"G1(FHN) verdict: {ev}")


if __name__ == "__main__":
    main()
