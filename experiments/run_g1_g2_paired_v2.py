"""G1_weak / G1_strict / G2 runner (v2, P1.2-A), surrogate, paired schedules.

Fixes the F statistical defect: the best admissible static subset is SELECTED on
the selection seed block and then EVALUATED (frozen) on the DISJOINT evaluation
seed block, so it is never optimized and judged on the same realization. The
decision rule is the frozen bootstrap-CI rule from the prereg statistical
contract. Separate G1_weak / G1_strict / G2 verdicts. Import-safe."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import provenance, run_cli
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.paired_switching import (
    assert_paired_invariants,
    average_operator_gamma,
    build_base_snapshots,
    paired_rate_schedule,
    variable_dwell_schedule,
)
from src.networks.switching import Epoch, Schedule, shuffle_dwell, shuffle_order
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import average_operator_map_v2, difference_step_maps_v2

GATE = "G1_G2_paired"
REPORT = "g1_g2_paired_v2.json"
SELECTION_RNG_SEED = 900001  # frozen: candidate pool for the best-static search


def _cfg(ctx):
    sp = ctx.execution["surrogate_paired"]
    sel = ctx.prereg["seed_blocks"]["paired_selection"]
    ev = ctx.prereg["seed_blocks"]["paired_evaluation"]
    stat = ctx.prereg["statistical_contract"]
    return sp, sel, ev, stat


def plan(ctx):
    sp, sel, ev, stat = _cfg(ctx)
    return {"gate": GATE, "selection_seeds": sel, "evaluation_seeds": ev,
            "params": {k: sp[k] for k in ("N", "N_IL", "K", "H", "cycles_fast",
                                          "cycles_intermediate", "cycles_slow",
                                          "best_static_search")},
            "protocol": "best-static selected on selection seeds, evaluated on disjoint "
                        "evaluation seeds; bootstrap-CI decision rule",
            "projected_cost": f"selection ~{sp['best_static_search']}x{len(sel)} gammas + "
                              f"evaluation ~8x{len(ev)} gammas of H={sp['H']}; seconds."}


def _gamma_maps(p, sched, seed):
    return full_contraction_rate(ordered_product(
        difference_step_maps_v2(p, sched, np.random.default_rng(seed))), sched.total_steps)


def _static(N, N_IL, snap, H):
    return Schedule(N, N_IL, (Epoch(H, tuple(snap)),), "static")


def _bootstrap_ci(diffs, n_boot, boot_seed, alpha=0.05):
    rng = np.random.default_rng(boot_seed)
    d = np.asarray(diffs, float); n = len(d)
    means = np.array([rng.choice(d, size=n, replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def _decide(diffs, floor, n_boot, boot_seed):
    m = float(np.mean(diffs)); s = float(np.std(diffs))
    band = max(3 * s, floor)
    lo, hi = _bootstrap_ci(diffs, n_boot, boot_seed)
    if m > band and lo > 0:
        return {"verdict": "PASS", "mean": m, "band": band, "ci95": [lo, hi], "reason_code": None}
    if m < -band and hi < 0:
        return {"verdict": "FAIL", "mean": m, "band": band, "ci95": [lo, hi], "reason_code": None}
    reason = "TIE" if abs(m) <= band else None
    return {"verdict": "INCONCLUSIVE", "mean": m, "band": band, "ci95": [lo, hi], "reason_code": reason}


def _select_best_static(sp, sel_seeds):
    """Select the best static N_IL-subset by max mean gamma across SELECTION seeds.
    Candidate pool = base snapshots from each selection seed UNION a frozen random
    search. Returns the frozen winning subset (tuple of node indices)."""
    N, N_IL, K, H = sp["N"], sp["N_IL"], sp["K"], sp["H"]
    cand = set()
    for s in sel_seeds:
        for snap in build_base_snapshots(N, N_IL, K, np.random.default_rng(s)):
            cand.add(snap)
    srng = np.random.default_rng(SELECTION_RNG_SEED)
    for _ in range(sp["best_static_search"]):
        cand.add(tuple(sorted(srng.choice(N, size=N_IL, replace=False).tolist())))
    best_subset, best_score = None, -np.inf
    for subset in cand:
        scores = []
        for s in sel_seeds:
            p = SurrogateParams(N=N, kappa=sp["kappa"], rho_target=sp["rho_target"],
                                intra_coupling=sp["intra_coupling"], seed_struct=s)
            scores.append(_gamma_maps(p, _static(N, N_IL, subset, H), s))
        m = float(np.mean(scores))
        if m > best_score:
            best_score, best_subset = m, subset
    return best_subset, best_score


def compute(ctx):
    sp, sel, ev, stat = _cfg(ctx)
    N, N_IL, K, H = sp["N"], sp["N_IL"], sp["K"], sp["H"]
    floor = stat["min_effect_size"]["surrogate_gamma_floor"]
    n_boot = stat["min_effect_size"]["n_boot"]
    boot_seed = stat["min_effect_size"]["boot_seed"]

    # ---- SELECTION phase (selection seeds only) ----
    best_static_subset, best_static_sel_score = _select_best_static(sp, sel)

    # ---- EVALUATION phase (disjoint evaluation seeds only) ----
    per = {k: [] for k in ("fast", "intermediate", "slow", "static_sparse",
                           "average_graph", "best_static_frozen",
                           "ordered_inter", "shuffled_order_inter", "vardwell", "shuffled_dwell")}
    d_weak, d_strict, d_order, d_dwell = [], [], [], []
    for seed in ev:
        p = SurrogateParams(N=N, kappa=sp["kappa"], rho_target=sp["rho_target"],
                            intra_coupling=sp["intra_coupling"], seed_struct=seed)
        base = build_base_snapshots(N, N_IL, K, np.random.default_rng(seed))
        fast = paired_rate_schedule(base, N, N_IL, sp["cycles_fast"], H, "fast")
        inter = paired_rate_schedule(base, N, N_IL, sp["cycles_intermediate"], H, "inter")
        slow = paired_rate_schedule(base, N, N_IL, sp["cycles_slow"], H, "slow")
        assert_paired_invariants({"fast": fast, "inter": inter, "slow": slow}, N, H, N_IL)

        gf = _gamma_maps(p, fast, seed); gi = _gamma_maps(p, inter, seed); gs = _gamma_maps(p, slow, seed)
        gstat = _gamma_maps(p, _static(N, N_IL, base[0], H), seed)
        occ = average_operator_gamma(base, N)
        gavg = full_contraction_rate(ordered_product(
            average_operator_map_v2(p, occ, np.random.default_rng(seed), H)), H)
        gbest = _gamma_maps(p, _static(N, N_IL, best_static_subset, H), seed)  # FROZEN subset
        gsh = _gamma_maps(p, shuffle_order(inter, np.random.default_rng(seed * 17 + 1)), seed)
        vd = variable_dwell_schedule(base, N, N_IL, tuple(sp["variable_dwell_multiset"]), "vd")
        gvd = _gamma_maps(p, vd, seed)
        gvd_sh = _gamma_maps(p, shuffle_dwell(vd, np.random.default_rng(seed * 19 + 1)), seed)

        best_switch = max(gf, gi, gs)
        per["fast"].append(gf); per["intermediate"].append(gi); per["slow"].append(gs)
        per["static_sparse"].append(gstat); per["average_graph"].append(gavg)
        per["best_static_frozen"].append(gbest)
        per["ordered_inter"].append(gi); per["shuffled_order_inter"].append(gsh)
        per["vardwell"].append(gvd); per["shuffled_dwell"].append(gvd_sh)
        d_weak.append(gf - gstat)
        d_strict.append(best_switch - max(gavg, gbest))
        d_order.append(gi - gsh)
        d_dwell.append(gvd - gvd_sh)

    agg = {k: {"mean": float(np.mean(v)), "std": float(np.std(v))} for k, v in per.items()}
    g1w = _decide(d_weak, floor, n_boot, boot_seed)
    g1s = _decide(d_strict, floor, n_boot, boot_seed)
    # G2: order magnitude vs band (two-sided effect); PASS if beyond band else INCONCLUSIVE(TIE)
    g2 = _decide(np.abs(d_order), floor, n_boot, boot_seed)
    g2_verdict = "PASS" if g2["verdict"] == "PASS" else "INCONCLUSIVE"
    g2_reason = None if g2_verdict == "PASS" else "TIE"

    headline = g1s["verdict"]  # already in {PASS,FAIL,INCONCLUSIVE}
    reason_code = g1s["reason_code"]
    return {"gate": GATE, "verdict": headline,
            "provenance": provenance(ctx, {"selection": sel, "evaluation": ev}, sp,
                                     "G1_weak/G1_strict/G2 via bootstrap-CI rule on evaluation "
                                     "seeds; best-static selected on disjoint selection seeds",
                                     reason_code=reason_code),
            "result": {"aggregate_gamma_eval": agg,
                       "best_static_subset": list(best_static_subset),
                       "best_static_selection_score": best_static_sel_score,
                       "G1_weak": g1w, "G1_strict": g1s,
                       "G2_order": {"verdict": g2_verdict, "reason_code": g2_reason,
                                    "mean_abs_order_effect": g2["mean"], "band": g2["band"],
                                    "ci95": g2["ci95"],
                                    "mean_abs_dwell_effect": float(np.mean(np.abs(d_dwell)))}}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
