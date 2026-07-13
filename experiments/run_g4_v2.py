"""G4 identifiability runner (v2). Same-realization ground truth via
simulate_observed_v2; past-only AR(1) basis estimator vs factor-confounded
baseline; contraction correlation against d_true (same realization).

Import-safe. Full run gated by the execution contract. DO NOT run full grids
without authorization."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import ContractError, provenance, run_cli
from src.metrics.identifiability import (
    precision_recall,
    rolling_basis_ar1_estimator,
    rolling_levelcorr_estimator,
)
from src.networks.switching import random_switching
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import (
    contraction_corr_same_realization,
    simulate_observed_v2,
)

GATE = "G4_identifiability"
REPORT = "g4_identifiability_v2.json"


def _params(ctx):
    g = ctx.execution["g4"]                                   # operational grid
    seeds = ctx.prereg["seed_blocks"]["identifiability"]      # frozen seeds (prereg)
    return g, seeds


def plan(ctx):
    g, seeds = _params(ctx)
    n = len(seeds) * len(g["async_variants"])
    return {"gate": GATE, "simulations": n,
            "params": {k: g[k] for k in ("N", "N_IL", "horizon_steps", "dwell_fast",
                                         "estimator_window", "obs_noise")},
            "seeds": seeds,
            "projected_cost": f"{n} surrogate observation runs of H={g['horizon_steps']} "
                              f"on N={g['N']} (seconds each); cheap."}


def compute(ctx):
    g, seeds = _params(ctx)
    N, N_IL = g["N"], g["N_IL"]
    H, dwell, W = g["horizon_steps"], g["dwell_fast"], g["estimator_window"]
    out = {}
    for stride in g["async_variants"]:
        key = f"async_{stride[0]}_{stride[1]}"
        bp, br, lp, lr, cc = [], [], [], [], []
        for seed in seeds:
            p = SurrogateParams(N=N, kappa=g["kappa"], rho_target=g["rho_target"],
                                intra_coupling=g["intra_coupling"],
                                obs_noise=g["obs_noise"], factor_scale=g["factor_scale"],
                                seed_struct=seed)
            sched = random_switching(N, N_IL, dwell, H // dwell + 1,
                                     np.random.default_rng(seed * 7 + 1), "fast")
            data = simulate_observed_v2(p, sched, np.random.default_rng(seed * 7 + 2),
                                        async_stride=tuple(stride))
            eb = rolling_basis_ar1_estimator(data.p1, data.p2, N_IL, W)
            el = rolling_levelcorr_estimator(data.p1, data.p2, N_IL, W)
            pbi, rbi = precision_recall(eb, data.active, W)
            pli, rli = precision_recall(el, data.active, W)
            bp.append(pbi); br.append(rbi); lp.append(pli); lr.append(rli)
            cc.append(contraction_corr_same_realization(data, W))
        out[key] = {"basis_precision": float(np.mean(bp)),
                    "basis_recall": float(np.mean(br)),
                    "levelcorr_precision": float(np.mean(lp)),
                    "levelcorr_recall": float(np.mean(lr)),
                    "contraction_corr_same_realization": float(np.mean(cc))}

    sync = out.get("async_1_1")
    if sync is None:
        raise ContractError("G4 requires a synchronous async_1_1 variant in the prereg")
    passed = (sync["basis_precision"] > 0.6 and sync["basis_recall"] > 0.6
              and sync["contraction_corr_same_realization"] > 0.5)
    verdict = "PASS" if passed else "FAIL"
    criterion = ("PASS iff synchronous precision>0.6 AND recall>0.6 AND "
                 "contraction_corr_same_realization>0.5; async is Epps-like degradation.")
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds,
                                     {k: g[k] for k in g if k != "async_variants"},
                                     criterion),
            "result": {"by_async_variant": out,
                       "false_link_gap": sync["basis_precision"] - sync["levelcorr_precision"]}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
