"""G3 robustness runner (v2, P1.2-B). Uses the shared inference per stage, records
per-seed paired differences and per-seed operator metadata for ALL seeds, applies
failed-run handling, and for the signed stage verifies (per seed) a strictly
negative coupling AND numeric off-diagonal budget equality vs the unsigned
comparator. Gate PASS requires BOTH faithful and mild_heterogeneity to PASS.
Import-safe."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import failure_record, provenance, run_cli
from src.metrics.inference import paired_decision
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.paired_switching import build_base_snapshots, paired_rate_schedule
from src.networks.switching import Epoch, Schedule
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import build_basis_operator_v2

GATE = "G3_robustness"
REPORT = "g3_robustness_v2.json"
SCOPE = "individual:G3"


def _cfg(ctx):
    return (ctx.execution["surrogate_paired"], ctx.execution["inference"],
            ctx.execution["g3_stages"], ctx.prereg["seed_blocks"]["stages"],
            ctx.prereg["gates"][GATE]["signed_budget_tolerance"])


def plan(ctx):
    sp, inf, stages, seeds, tol = _cfg(ctx)
    return {"gate": GATE, "stages": [s["name"] for s in stages], "seeds": seeds,
            "params": {k: sp[k] for k in ("N", "N_IL", "K", "H", "cycles_fast")},
            "signed_budget_tolerance": tol}


def _gamma_from_A(A, sp, sched):
    idx = np.arange(sp["N"])
    maps = []
    for step in range(sched.total_steps):
        gv = sched.gamma_at_step(step)
        M = A.copy(); M[idx, idx] -= 2.0 * sp["kappa"] * gv
        maps.append(M)
    return full_contraction_rate(ordered_product(maps), sched.total_steps)


def _sp_params(sp, stage, seed):
    return SurrogateParams(N=sp["N"], kappa=sp["kappa"], rho_target=sp["rho_target"],
                           intra_coupling=sp["intra_coupling"],
                           heterogeneity=stage["heterogeneity"], directed=stage["directed"],
                           signed=stage["signed"], seed_struct=seed)


def compute(ctx):
    sp, inf, stages, seeds, tol = _cfg(ctx)
    N, N_IL, H = sp["N"], sp["N_IL"], sp["H"]
    negf = sp["neg_fraction_signed"]
    results = {}
    stage_pass = {}
    signed_invalid = False
    any_failed_gate = False

    for stage in stages:
        advs, per_seed, failed, fail_records = [], [], [], []
        for seed in seeds:
            try:
                p = _sp_params(sp, stage, seed)
                A, meta = build_basis_operator_v2(p, np.random.default_rng(seed), neg_fraction=negf)
                base = build_base_snapshots(N, N_IL, sp["K"], np.random.default_rng(seed))
                fast = paired_rate_schedule(base, N, N_IL, sp["cycles_fast"], H, "fast")
                static = Schedule(N, N_IL, (Epoch(H, base[0]),), "static")
                gf, gs = _gamma_from_A(A, sp, fast), _gamma_from_A(A, sp, static)
                if not (np.isfinite(gf) and np.isfinite(gs)):
                    raise FloatingPointError("nonfinite gamma")
                rec = {"seed": seed, "advantage": gf - gs,
                       "n_negative_offdiag": meta["n_negative_offdiag"],
                       "offdiag_frobenius_prescale": meta["offdiag_frobenius_prescale"]}
                if stage["signed"]:
                    # the unsigned comparator is part of the per-seed computation:
                    # a failure here is a seed failure too (captured below)
                    p_uns = SurrogateParams(N=N, kappa=sp["kappa"], rho_target=sp["rho_target"],
                                            intra_coupling=sp["intra_coupling"],
                                            heterogeneity=stage["heterogeneity"], directed=False,
                                            signed=False, seed_struct=seed)
                    _, meta_uns = build_basis_operator_v2(p_uns, np.random.default_rng(seed))
                    budget_diff = abs(meta["offdiag_frobenius_prescale"]
                                      - meta_uns["offdiag_frobenius_prescale"])
                    rec["unsigned_budget_prescale"] = meta_uns["offdiag_frobenius_prescale"]
                    rec["budget_diff"] = budget_diff
                    if meta["n_negative_offdiag"] < 1 or budget_diff > tol:
                        signed_invalid = True
            except Exception as e:
                failed.append(seed)
                fail_records.append(failure_record(e, seed, {"stage": stage["name"]}))
                continue
            advs.append(gf - gs)
            per_seed.append(rec)

        frac_failed = len(failed) / len(seeds)
        if frac_failed > 0.2:
            any_failed_gate = True
        dec = paired_decision(advs, floor=inf["floor_surrogate_gamma"], std_mult=inf["std_mult"],
                              alpha=inf["alpha"], n_boot=inf["n_boot"], boot_seed=inf["boot_seed"]) \
            if advs else {"verdict": "INCONCLUSIVE", "reason": "NO_DATA"}
        stage_pass[stage["name"]] = (dec["verdict"] == "PASS")
        results[stage["name"]] = {"decision": dec, "per_seed": per_seed,
                                  "failed_seeds": failed, "frac_failed": frac_failed,
                                  "failure_records": fail_records}

    if any_failed_gate:
        verdict, reason = "EXECUTION_INVALID", "FAILED_RUNS"
    elif signed_invalid:
        verdict, reason = "EXECUTION_INVALID", "STRESS_NOT_IMPLEMENTED"
    else:
        both = stage_pass.get("faithful") and stage_pass.get("mild_heterogeneity")
        verdict, reason = ("PASS", None) if both else ("INCONCLUSIVE", "TIE")
    first_no_adv = next((s["name"] for s in stages if not stage_pass.get(s["name"])), None)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, {"surrogate_paired": sp, "stages": stages},
                                     "per-stage shared sign-test on (gamma_fast - gamma_static); "
                                     "PASS iff faithful AND mild_heterogeneity PASS; signed stage "
                                     "requires per-seed negative weight and budget equality",
                                     reason_code=reason,
                                     failures=[fr for r in results.values() for fr in r["failure_records"]]),
            "result": {"by_stage": results, "first_stage_without_pass": first_no_adv,
                       "advantage": "gamma_fast - gamma_static per seed (paired)"}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
