"""G1_weak / G1_strict / G2 runner (v2, P1.2-B), surrogate, paired schedules.

Fixes:
  B: the switching RATE ARM is selected on the SELECTION seeds only and FROZEN
     before any evaluation seed is opened (no per-evaluation-seed max()). The
     static comparator is the "best-of-frozen-candidate-set" (NOT "best admissible
     static"; the C(24,6)=134596 universe is not searched), with canonical ordering
     and a lexicographic tie-break. G1_strict and G2 are NOT_INTERPRETABLE unless
     G1_weak PASSes.
  C: all verdicts use the single shared inference (exact sign test + effect band).
  D: G2 uses a permutation null (median of n_perm frozen order-permutations per
     seed) and a signed paired test on delta = gamma_ordered - median_perm.
Import-safe."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import provenance, run_cli
from src.metrics.inference import paired_decision
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.paired_switching import (
    assert_paired_invariants,
    average_operator_gamma,
    build_base_snapshots,
    order_permutations,
    paired_rate_schedule,
)
from src.networks.switching import Epoch, Schedule
from src.simulation.linear_surrogate import SurrogateParams
from src.simulation.surrogate_v2 import average_operator_map_v2, difference_step_maps_v2

GATE = "G1_G2_paired"
REPORT = "g1_g2_paired_v2.json"
ARM_ORDER = ["fast", "intermediate", "slow"]


def _cfg(ctx):
    sp = ctx.execution["surrogate_paired"]
    inf = ctx.execution["inference"]
    sel = ctx.prereg["seed_blocks"]["paired_selection"]
    ev = ctx.prereg["seed_blocks"]["paired_evaluation"]
    return sp, inf, sel, ev


def _decision(diffs, inf):
    return paired_decision(diffs, floor=inf["floor_surrogate_gamma"],
                           std_mult=inf["std_mult"], alpha=inf["alpha"],
                           n_boot=inf["n_boot"], boot_seed=inf["boot_seed"])


def plan(ctx):
    sp, inf, sel, ev = _cfg(ctx)
    return {"gate": GATE, "selection_seeds": sel, "evaluation_seeds": ev,
            "params": {k: sp[k] for k in ("N", "N_IL", "K", "H", "cycles_fast",
                                          "cycles_intermediate", "cycles_slow",
                                          "best_static_search", "g2_n_perm")},
            "protocol": "arm + best-static SELECTED on selection seeds, FROZEN, then "
                        "EVALUATED on disjoint evaluation seeds; shared sign-test rule; "
                        "G2 permutation null.",
            "comparator_name": "best-of-frozen-candidate-set (NOT best admissible static)"}


def _p(sp, seed):
    return SurrogateParams(N=sp["N"], kappa=sp["kappa"], rho_target=sp["rho_target"],
                           intra_coupling=sp["intra_coupling"], seed_struct=seed)


def _gamma(sp, sched, seed):
    p = _p(sp, seed)
    return full_contraction_rate(ordered_product(
        difference_step_maps_v2(p, sched, np.random.default_rng(seed))), sched.total_steps)


def _static(sp, snap):
    return Schedule(sp["N"], sp["N_IL"], (Epoch(sp["H"], tuple(snap)),), "static")


def _arm_schedule(sp, base, arm):
    cyc = {"fast": sp["cycles_fast"], "intermediate": sp["cycles_intermediate"],
           "slow": sp["cycles_slow"]}[arm]
    return paired_rate_schedule(base, sp["N"], sp["N_IL"], cyc, sp["H"], arm)


def _base(sp, seed):
    return build_base_snapshots(sp["N"], sp["N_IL"], sp["K"], np.random.default_rng(seed))


def _apply_hierarchy(weak_verdict, g1s_raw, g2_raw):
    """G1_strict and G2 are NOT_INTERPRETABLE unless G1_weak PASSes (diagnostic
    values are retained but not interpreted as gate verdicts). G2 (when
    interpretable) PASSes iff a significant order effect in EITHER direction."""
    g1s, g2 = dict(g1s_raw), dict(g2_raw)
    if weak_verdict != "PASS":
        g1s["interpretable"] = False; g1s["gate_verdict"] = "NOT_INTERPRETABLE"
        g2["interpretable"] = False; g2["gate_verdict"] = "NOT_INTERPRETABLE"
    else:
        g1s["interpretable"] = True; g1s["gate_verdict"] = g1s_raw["verdict"]
        g2["interpretable"] = True
        g2["gate_verdict"] = "PASS" if g2_raw["verdict"] in ("PASS", "FAIL") else "INCONCLUSIVE"
    return g1s, g2


def _select_arm(sp, sel_seeds):
    scores = {}
    for arm in ARM_ORDER:
        vals = [_gamma(sp, _arm_schedule(sp, _base(sp, s), arm), s) for s in sel_seeds]
        scores[arm] = float(np.mean(vals))
    best = max(ARM_ORDER, key=lambda a: (scores[a], -ARM_ORDER.index(a)))  # score, canonical tie-break
    return best, scores


def _select_best_static(sp, sel_seeds):
    N, N_IL, K, H = sp["N"], sp["N_IL"], sp["K"], sp["H"]
    cand = set()
    for s in sel_seeds:
        cand.update(build_base_snapshots(N, N_IL, K, np.random.default_rng(s)))
    srng = np.random.default_rng(sp["candidate_search_seed"])
    for _ in range(sp["best_static_search"]):
        cand.add(tuple(sorted(srng.choice(N, size=N_IL, replace=False).tolist())))
    ordered = sorted(cand)                                   # canonical ordering
    best_subset, best_score = None, None
    for subset in ordered:                                   # ties -> first = lexicographically smallest
        score = float(np.mean([_gamma(sp, _static(sp, subset), s) for s in sel_seeds]))
        if best_score is None or score > best_score + 1e-12:
            best_subset, best_score = subset, score
    return best_subset, best_score, len(ordered)


def compute(ctx):
    sp, inf, sel, ev = _cfg(ctx)
    N, N_IL, H = sp["N"], sp["N_IL"], sp["H"]

    # ---- SELECTION phase (selection seeds only) ----
    arm, arm_scores = _select_arm(sp, sel)
    best_static, best_static_score, n_candidates = _select_best_static(sp, sel)

    # ---- EVALUATION phase (disjoint evaluation seeds) ----
    d_weak, d_strict, d_order = [], [], []
    per = {"arm_gamma": [], "static_sparse": [], "average_graph": [], "best_static_frozen": []}
    for seed in ev:
        base = _base(sp, seed)
        arm_sched = _arm_schedule(sp, base, arm)
        inter = _arm_schedule(sp, base, "intermediate")
        assert_paired_invariants({"arm": arm_sched, "inter": inter}, N, H, N_IL)
        g_arm = _gamma(sp, arm_sched, seed)
        g_stat = _gamma(sp, _static(sp, base[0]), seed)
        occ = average_operator_gamma(base, N)
        g_avg = full_contraction_rate(ordered_product(
            average_operator_map_v2(_p(sp, seed), occ, np.random.default_rng(seed), H)), H)
        g_best = _gamma(sp, _static(sp, best_static), seed)
        per["arm_gamma"].append(g_arm); per["static_sparse"].append(g_stat)
        per["average_graph"].append(g_avg); per["best_static_frozen"].append(g_best)
        d_weak.append(g_arm - g_stat)
        d_strict.append(g_arm - max(g_avg, g_best))
        # G2 permutation null on the intermediate arm
        g_ord = _gamma(sp, inter, seed)
        perms = order_permutations(inter, sp["g2_n_perm"], np.random.default_rng(sp["g2_perm_seed"] + seed))
        g_perm = [_gamma(sp, ps, seed) for ps in perms]
        d_order.append(g_ord - float(np.median(g_perm)))

    g1w = _decision(d_weak, inf)
    g1s_raw = _decision(d_strict, inf)
    g2_raw = _decision(d_order, inf)

    g1s, g2 = _apply_hierarchy(g1w["verdict"], g1s_raw, g2_raw)
    headline = g1w["verdict"]
    reason = g1w["reason"] if g1w["reason"] in ("TIE", "NOT_SIGNIFICANT") else None
    return {"gate": GATE, "verdict": headline,
            "provenance": provenance(ctx, {"selection": sel, "evaluation": ev}, sp,
                                     "G1_weak by shared sign-test rule; G1_strict/G2 "
                                     "NOT_INTERPRETABLE unless G1_weak PASS; comparator = "
                                     "best-of-frozen-candidate-set; arm frozen on selection seeds",
                                     reason_code=reason),
            "result": {
                "selected_arm": arm, "arm_selection_scores": arm_scores,
                "arm_tie_break": "max mean selection gamma; canonical order fast<intermediate<slow",
                "best_static_subset": list(best_static),
                "best_static_selection_score": best_static_score,
                "n_candidates": n_candidates,
                "comparator_name": "best-of-frozen-candidate-set",
                "per_seed_gamma_eval": per,
                "G1_weak": g1w, "G1_strict": g1s, "G2_order": g2}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
