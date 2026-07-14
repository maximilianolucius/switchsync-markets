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

from _contract_v2 import failure_record, provenance, run_cli
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
SCOPE = "individual:G1G2"
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


def _candidate_set(sp, sel_seeds):
    """FROZEN static-comparator candidate universe, built ONCE before any gamma is
    evaluated (contract E): the union of the per-selection-seed base snapshots plus
    the deterministic random-search subsets. Index combinatorics only (no gamma),
    so it is well-defined regardless of which seeds later drop from the mask.
    Canonical (sorted) ordering; the lexicographically smallest wins later ties."""
    N, N_IL, K = sp["N"], sp["N_IL"], sp["K"]
    cand = set()
    for s in sel_seeds:
        cand.update(build_base_snapshots(N, N_IL, K, np.random.default_rng(s)))
    srng = np.random.default_rng(sp["candidate_search_seed"])
    for _ in range(sp["best_static_search"]):
        cand.add(tuple(sorted(srng.choice(N, size=N_IL, replace=False).tolist())))
    return sorted(cand)


def _selection_matrix(sp, sel_seeds, candidates):
    """TRULY COMMON selection mask (contract E). For each selection seed, ATOMICALLY
    compute EVERY quantity selection depends on: gamma for all rate arms AND gamma
    for EVERY frozen static candidate, plus their finiteness. If ANY arm or ANY
    candidate raises or is nonfinite, the WHOLE seed leaves the common mask, and the
    failing seed/phase/arm-or-candidate is recorded. Arm and best-static are then
    chosen from this cached matrix with NO recomputation. Returns
    (mask, arm_matrix, static_matrix, failures) where arm_matrix[s][arm] and
    static_matrix[s][candidate_index] hold the cached gammas for masked seeds."""
    mask, arm_matrix, static_matrix, failures = [], {}, {}, []
    for s in sel_seeds:
        failed_on = {"phase": "selection", "stage": "base"}
        arm_vals, static_vals = {}, {}
        try:
            base = _base(sp, s)
            for a in ARM_ORDER:
                failed_on = {"phase": "selection", "arm": a}
                g = _gamma(sp, _arm_schedule(sp, base, a), s)
                if not np.isfinite(g):
                    raise FloatingPointError(f"nonfinite arm gamma ({a})")
                arm_vals[a] = g
            for ci, subset in enumerate(candidates):
                failed_on = {"phase": "selection", "candidate": list(subset)}
                g = _gamma(sp, _static(sp, subset), s)
                if not np.isfinite(g):
                    raise FloatingPointError("nonfinite static candidate gamma")
                static_vals[ci] = g
        except Exception as e:
            failures.append(failure_record(e, s, failed_on))
            continue
        mask.append(s)
        arm_matrix[s], static_matrix[s] = arm_vals, static_vals
    return mask, arm_matrix, static_matrix, failures


def _select_arm_cached(arm_matrix, mask):
    scores = {a: float(np.mean([arm_matrix[s][a] for s in mask])) for a in ARM_ORDER}
    best = max(ARM_ORDER, key=lambda a: (scores[a], -ARM_ORDER.index(a)))  # score, canonical tie-break
    return best, scores


def _select_best_static_cached(static_matrix, mask, candidates):
    best_subset, best_score = None, None
    for ci, subset in enumerate(candidates):     # canonical order; ties -> lexicographically smallest
        score = float(np.mean([static_matrix[s][ci] for s in mask]))
        if best_score is None or score > best_score + 1e-12:
            best_subset, best_score = subset, score
    return best_subset, best_score, len(candidates)


def compute(ctx):
    sp, inf, sel, ev = _cfg(ctx)
    N, N_IL, H = sp["N"], sp["N_IL"], sp["H"]

    # ---- SELECTION phase (selection seeds only; TRULY COMMON cached mask) ----
    # Freeze the static-candidate universe FIRST, then compute one atomic per-seed
    # matrix covering every arm AND every candidate; arm + best-static are picked
    # from that cache with no recomputation (contract E).
    candidates = _candidate_set(sp, sel)
    sel_mask, arm_matrix, static_matrix, sel_failures = _selection_matrix(sp, sel, candidates)
    n_selection_failed = len(sel) - len(sel_mask)
    if not sel_mask or n_selection_failed / len(sel) > 0.2:
        return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                "provenance": provenance(ctx, {"selection": sel, "evaluation": ev}, sp,
                                         "zero successful selection seeds, or >20% failed "
                                         "(frozen policy; common cached-matrix mask)",
                                         reason_code="FAILED_RUNS", failures=sel_failures),
                "result": {"n_selection_failed": n_selection_failed,
                           "n_selection_total": len(sel),
                           "n_static_candidates": len(candidates)}}
    arm, arm_scores = _select_arm_cached(arm_matrix, sel_mask)
    best_static, best_static_score, n_candidates = _select_best_static_cached(
        static_matrix, sel_mask, candidates)

    # ---- EVALUATION phase (disjoint evaluation seeds) ----
    d_weak, d_strict, d_order = [], [], []
    per = {"arm_gamma": [], "static_sparse": [], "average_graph": [], "best_static_frozen": []}
    eval_failures = []
    for seed in ev:
        try:
            base = _base(sp, seed)          # contract E: base construction inside the try
            arm_sched = _arm_schedule(sp, base, arm)
            inter = _arm_schedule(sp, base, "intermediate")
            assert_paired_invariants({"arm": arm_sched, "inter": inter}, N, H, N_IL)
            g_arm = _gamma(sp, arm_sched, seed)
            g_stat = _gamma(sp, _static(sp, base[0]), seed)
            occ = average_operator_gamma(base, N)
            g_avg = full_contraction_rate(ordered_product(
                average_operator_map_v2(_p(sp, seed), occ, np.random.default_rng(seed), H)), H)
            g_best = _gamma(sp, _static(sp, best_static), seed)
            g_ord = _gamma(sp, inter, seed)
            perms = order_permutations(inter, sp["g2_n_perm"],
                                       np.random.default_rng(sp["g2_perm_seed"] + seed))
            g_perm = [_gamma(sp, ps, seed) for ps in perms]
            vals = [g_arm, g_stat, g_avg, g_best, g_ord] + list(g_perm)
            if not all(np.isfinite(v) for v in vals):
                raise FloatingPointError("nonfinite gamma in evaluation seed")
        except Exception as e:
            eval_failures.append(failure_record(e, seed, {"phase": "evaluation"}))
            continue
        per["arm_gamma"].append(g_arm); per["static_sparse"].append(g_stat)
        per["average_graph"].append(g_avg); per["best_static_frozen"].append(g_best)
        d_weak.append(g_arm - g_stat)
        d_strict.append(g_arm - max(g_avg, g_best))
        # G2 permutation-median comparator (Option 1; NOT a permutation test)
        d_order.append(g_ord - float(np.median(g_perm)))

    if len(eval_failures) / len(ev) > 0.2:
        return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                "provenance": provenance(ctx, {"selection": sel, "evaluation": ev}, sp,
                                         ">20% evaluation seeds failed (frozen policy)",
                                         reason_code="FAILED_RUNS", failures=eval_failures),
                "result": {"n_eval_failed": len(eval_failures)}}

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
                                     "best-of-frozen-candidate-set; arm frozen on selection seeds; "
                                     "G2 = permutation-median comparator + cross-seed sign test",
                                     reason_code=reason, failures=sel_failures + eval_failures),
            "result": {
                "selected_arm": arm, "arm_selection_scores": arm_scores,
                "arm_tie_break": "max mean selection gamma; canonical order fast<intermediate<slow",
                "best_static_subset": list(best_static),
                "best_static_selection_score": best_static_score,
                "n_candidates": n_candidates,
                "comparator_name": "best-of-frozen-candidate-set",
                "per_seed_gamma_eval": per,
                "G1_weak": g1w, "G1_strict": g1s, "G2_order": g2,
                "g2_method": ("permutation-median comparator + cross-seed sign test: "
                              "delta_s = gamma_ordered - median(gamma over frozen order "
                              "permutations), aggregated by the shared exact sign test. "
                              "This is NOT a per-seed permutation test; it detects a "
                              "systematic displacement from the permutation median and "
                              "sign-varying order effects can cancel across seeds."),
                "n_eval_failed": len(eval_failures)}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
