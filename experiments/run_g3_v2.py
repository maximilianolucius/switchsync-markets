"""G3 robustness runner (v2), surrogate, implemented stresses only.

Paired fast-vs-static advantage per stage (faithful, heterogeneity, directed,
GENUINE signed). The signed stage asserts >=1 strictly negative coupling with the
off-diagonal Frobenius budget preserved, else the stage is EXECUTION_INVALID.

Import-safe; full run gated by the execution contract."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import provenance, run_cli
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.paired_switching import build_base_snapshots, paired_rate_schedule
from src.networks.switching import Epoch, Schedule
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import build_basis_operator_v2, difference_step_maps_v2

GATE = "G3_robustness"
REPORT = "g3_robustness_v2.json"


def _cfg(ctx):
    return (ctx.execution["surrogate_paired"], ctx.execution["g3_stages"],
            ctx.prereg["seed_blocks"]["stages"])


def plan(ctx):
    sp, stages, seeds = _cfg(ctx)
    return {"gate": GATE, "stages": [s["name"] for s in stages], "seeds": seeds,
            "params": {k: sp[k] for k in ("N", "N_IL", "K", "H", "kappa", "cycles_fast")},
            "projected_cost": f"{len(stages)*len(seeds)*2} ordered products of {sp['H']} maps; fast."}


def _gamma(maps):
    return full_contraction_rate(ordered_product(maps), len(maps))


def compute(ctx):
    sp, stages, seeds = _cfg(ctx)
    N, N_IL, K, H = sp["N"], sp["N_IL"], sp["K"], sp["H"]
    results = {}
    stage_pass = {}
    signed_invalid = False
    for stage in stages:
        advs, gf, gs = [], [], []
        neg_meta = None
        for seed in seeds:
            p = SurrogateParams(N=N, kappa=sp["kappa"], rho_target=sp["rho_target"],
                                intra_coupling=sp["intra_coupling"],
                                heterogeneity=stage["heterogeneity"],
                                directed=stage["directed"], signed=stage["signed"],
                                seed_struct=seed)
            rng = np.random.default_rng(seed)
            base = build_base_snapshots(N, N_IL, K, rng)
            fast = paired_rate_schedule(base, N, N_IL, sp["cycles_fast"], H, "fast")
            static = Schedule(N, N_IL, (Epoch(H, base[0]),), "static")

            def g(sched):
                # build_basis_operator_v2 uses neg_fraction for signed; pass it through
                _, meta = build_basis_operator_v2(p, np.random.default_rng(seed),
                                                  neg_fraction=sp["neg_fraction_signed"])
                return _gamma(difference_step_maps_v2(p, sched, np.random.default_rng(seed))), meta

            gfi, meta = g(fast)
            gsi, _ = g(static)
            gf.append(gfi); gs.append(gsi); advs.append(gfi - gsi)
            neg_meta = meta
        adv_mean = float(np.mean(advs))
        results[stage["name"]] = {
            "gamma_fast_mean": float(np.mean(gf)),
            "gamma_static_mean": float(np.mean(gs)),
            "advantage_mean": adv_mean, "advantage_std": float(np.std(advs)),
            "operator_meta": {k: neg_meta[k] for k in
                              ("n_negative_offdiag", "frac_negative_offdiag",
                               "offdiag_frobenius_budget", "spectral_radius", "symmetric")},
        }
        stage_pass[stage["name"]] = adv_mean > 0
        if stage["signed"] and neg_meta["n_negative_offdiag"] < 1:
            signed_invalid = True

    if signed_invalid:
        verdict = "EXECUTION_INVALID"
        note = "signed stage produced no strictly-negative coupling; stress not implemented"
    else:
        faithful_ok = results.get("faithful", {}).get("advantage_mean", -1) > 0
        mild_ok = results.get("mild_heterogeneity", {}).get("advantage_mean", -1) > 0
        verdict = "PASS" if (faithful_ok and mild_ok) else "INCONCLUSIVE"
        note = "PASS iff faithful & mild-heterogeneity advantage>0; else LIMITED->INCONCLUSIVE"
    first_fail = next((n for n in [s["name"] for s in stages] if not stage_pass[n]), None)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, {"surrogate_paired": sp, "stages": stages},
                                     note),
            "result": {"by_stage": results, "first_stage_without_advantage": first_fail,
                       "advantage": "gamma_fast - gamma_static (>0 => switching helps)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
