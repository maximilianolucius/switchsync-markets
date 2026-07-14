"""G4 identifiability runner (v2, P1.2-B). Same-realization ground truth; past-only
estimators. Fixes: exact horizon (schedule.total_steps == H, asserted at runtime);
PASS requires ALL FOUR frozen conditions including a DEFINED "beats the baseline"
(per-seed paired precision margin via the shared inference); failed/nonfinite
seeds handled (>20% -> EXECUTION_INVALID). Import-safe."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import ContractError, failure_record, provenance, run_cli
from src.metrics.identifiability import (
    precision_recall,
    rolling_basis_ar1_estimator,
    rolling_levelcorr_estimator,
)
from src.metrics.inference import paired_decision
from src.networks.switching import random_switching
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import (
    contraction_corr_same_realization,
    simulate_observed_v2,
)

GATE = "G4_identifiability"
REPORT = "g4_identifiability_v2.json"
SCOPE = "individual:G4"


def _cfg(ctx):
    return (ctx.execution["g4"], ctx.execution["inference"],
            ctx.prereg["seed_blocks"]["identifiability"])


def plan(ctx):
    g, inf, seeds = _cfg(ctx)
    return {"gate": GATE, "seeds": seeds,
            "params": {k: g[k] for k in ("N", "N_IL", "horizon_steps", "dwell_fast",
                                         "estimator_window", "obs_noise", "async_variants")},
            "conditions": ["precision>0.6", "recall>0.6", "contraction_corr>0.5",
                           "basis beats factor-confounded baseline (paired margin)"]}


def _verdict_from_conditions(conds: dict) -> str:
    """PASS iff ALL FOUR frozen conditions hold (incl. beats_baseline)."""
    return "PASS" if all(conds.values()) else "FAIL"


def _make_schedule(N, N_IL, H, dwell, seed):
    if H % dwell != 0:
        raise ContractError(f"G4 horizon {H} not divisible by dwell {dwell}")
    n_epochs = H // dwell                      # EXACT horizon (fixes v3 606-for-600 bug)
    sched = random_switching(N, N_IL, dwell, n_epochs, np.random.default_rng(seed * 7 + 1), "fast")
    if sched.total_steps != H:
        raise ContractError(f"G4 schedule total_steps {sched.total_steps} != horizon {H}")
    return sched


def compute(ctx):
    g, inf, seeds = _cfg(ctx)
    N, N_IL = g["N"], g["N_IL"]
    H, dwell, W = g["horizon_steps"], g["dwell_fast"], g["estimator_window"]
    out, failed_by_variant = {}, {}
    per_seed_basis_prec = {}   # for the synchronous baseline paired test

    for stride in g["async_variants"]:
        key = f"async_{stride[0]}_{stride[1]}"
        rows, failed, fail_records = [], [], []
        for seed in seeds:
            try:
                p = SurrogateParams(N=N, kappa=g["kappa"], rho_target=g["rho_target"],
                                    intra_coupling=g["intra_coupling"], obs_noise=g["obs_noise"],
                                    factor_scale=g["factor_scale"], seed_struct=seed)
                sched = _make_schedule(N, N_IL, H, dwell, seed)   # asserts total_steps == H
                data = simulate_observed_v2(p, sched, np.random.default_rng(seed * 7 + 2),
                                            async_stride=tuple(stride))
                if not (np.all(np.isfinite(data.p1)) and np.all(np.isfinite(data.p2))):
                    raise FloatingPointError("nonfinite observation")
                eb = rolling_basis_ar1_estimator(data.p1, data.p2, N_IL, W)
                el = rolling_levelcorr_estimator(data.p1, data.p2, N_IL, W)
                pb, rb = precision_recall(eb, data.active, W)
                pl, rl = precision_recall(el, data.active, W)
                cc = contraction_corr_same_realization(data, W)
                if not all(np.isfinite(x) for x in (pb, rb, pl, rl, cc)):
                    raise FloatingPointError("nonfinite metric")
            except ContractError:
                raise
            except Exception as e:
                failed.append(seed)
                fail_records.append(failure_record(e, seed, {"variant": key}))
                continue
            rows.append({"seed": seed, "basis_precision": pb, "basis_recall": rb,
                         "levelcorr_precision": pl, "levelcorr_recall": rl, "contraction_corr": cc})
        failed_by_variant[key] = {"seeds": failed, "records": fail_records}
        if rows:
            out[key] = {"basis_precision": float(np.mean([r["basis_precision"] for r in rows])),
                        "basis_recall": float(np.mean([r["basis_recall"] for r in rows])),
                        "levelcorr_precision": float(np.mean([r["levelcorr_precision"] for r in rows])),
                        "contraction_corr_same_realization": float(np.mean([r["contraction_corr"] for r in rows]))}
            if key == "async_1_1":
                per_seed_basis_prec = {"basis": [r["basis_precision"] for r in rows],
                                       "levelcorr": [r["levelcorr_precision"] for r in rows]}
        else:
            out[key] = None

    # failed-run handling: apply >20% to EVERY configured variant (all variants are
    # gate-relevant here; none is declared diagnostic-only in the contract).
    all_fail_records = [r for v in failed_by_variant.values() for r in v["records"]]
    for key, fv in failed_by_variant.items():
        if len(fv["seeds"]) / len(seeds) > 0.2:
            return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                    "provenance": provenance(ctx, seeds, g,
                                             f">20% failed/nonfinite seeds in variant {key}",
                                             reason_code="FAILED_RUNS", failures=all_fail_records),
                    "result": {"by_async_variant": out, "failed_by_variant": failed_by_variant}}

    sync = out["async_1_1"]
    # "beats the baseline": per-seed paired precision margin, shared inference, floor=margin
    margin = [b - l for b, l in zip(per_seed_basis_prec["basis"], per_seed_basis_prec["levelcorr"])]
    beats = paired_decision(margin, floor=inf["floor_identifiability_margin"],
                            std_mult=inf["std_mult"], alpha=inf["alpha"],
                            n_boot=inf["n_boot"], boot_seed=inf["boot_seed"])
    conds = {"precision_gt_0.6": sync["basis_precision"] > 0.6,
             "recall_gt_0.6": sync["basis_recall"] > 0.6,
             "contraction_corr_gt_0.5": sync["contraction_corr_same_realization"] > 0.5,
             "beats_baseline": beats["verdict"] == "PASS"}
    verdict = _verdict_from_conditions(conds)
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "PASS iff precision>0.6 AND recall>0.6 AND contraction_corr>0.5 "
                                     "AND basis beats baseline (paired precision margin, shared rule)",
                                     failures=all_fail_records),
            "result": {"by_async_variant": out, "conditions": conds,
                       "beats_baseline_decision": beats,
                       "failed_by_variant": failed_by_variant}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
