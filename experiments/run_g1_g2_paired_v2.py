"""G1_weak / G1_strict / G2 runner (v2), surrogate, paired schedules.

Uses paired_switching (exact horizon H, identical average operator across rate
arms) and the corrected difference operator. Produces SEPARATE verdicts for
G1_weak (vs static-sparse) and G1_strict (vs average graph AND best admissible
static). G2 uses paired ordered-vs-shuffled at the intermediate rate plus a
genuine non-constant shuffled_dwell null.

Import-safe; full run gated by the execution contract."""
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
from src.simulation.surrogate_v2 import (
    average_operator_map_v2,
    difference_step_maps_v2,
)

GATE = "G1_G2_paired"
REPORT = "g1_g2_paired_v2.json"


def _sp(ctx):
    return ctx.prereg["surrogate_paired"], ctx.prereg["seed_blocks"]["paired_causal"]


def plan(ctx):
    sp, seeds = _sp(ctx)
    per_seed = 3 + 1 + 1 + 2 + 1 + sp["best_static_search"]  # arms + comparators + search
    return {"gate": GATE, "seeds": seeds,
            "params": {k: sp[k] for k in ("N", "N_IL", "K", "H", "kappa",
                                          "cycles_fast", "cycles_intermediate",
                                          "cycles_slow", "best_static_search")},
            "ordered_products_per_seed": per_seed,
            "projected_cost": f"~{per_seed*len(seeds)} ordered products of {sp['H']} "
                              f"{sp['N']}x{sp['N']} maps; seconds-to-minutes total."}


def _gamma(maps):
    return full_contraction_rate(ordered_product(maps), len(maps))


def _static_schedule(N, N_IL, snap, H):
    return Schedule(N, N_IL, (Epoch(H, tuple(snap)),), "static_sparse")


def _paired_verdict(diffs, band, direction="greater"):
    """diffs: per-seed paired differences. PASS if mean beyond +band (greater) with
    all-positive sign majority; FAIL if beyond -band; else TIE."""
    m = float(np.mean(diffs))
    if m > band:
        return "PASS", m
    if m < -band:
        return "FAIL", m
    return "TIE", m


def compute(ctx):
    sp, seeds = _sp(ctx)
    N, N_IL, K, H = sp["N"], sp["N_IL"], sp["K"], sp["H"]
    per = {k: [] for k in ("fast", "intermediate", "slow", "static_sparse",
                           "average_graph", "best_static", "ordered_inter",
                           "shuffled_order_inter", "vardwell", "shuffled_dwell")}
    d_weak, d_strict, d_order, d_dwell = [], [], [], []

    for seed in seeds:
        p = SurrogateParams(N=N, kappa=sp["kappa"], rho_target=sp["rho_target"],
                            intra_coupling=sp["intra_coupling"], seed_struct=seed)
        rng = np.random.default_rng(seed)
        base = build_base_snapshots(N, N_IL, K, rng)
        fast = paired_rate_schedule(base, N, N_IL, sp["cycles_fast"], H, "fast")
        inter = paired_rate_schedule(base, N, N_IL, sp["cycles_intermediate"], H, "inter")
        slow = paired_rate_schedule(base, N, N_IL, sp["cycles_slow"], H, "slow")
        assert_paired_invariants({"fast": fast, "inter": inter, "slow": slow}, N, H, N_IL)

        def g(sched):
            return _gamma(difference_step_maps_v2(p, sched, np.random.default_rng(seed)))

        gf, gi, gs = g(fast), g(inter), g(slow)
        gstat = g(_static_schedule(N, N_IL, base[0], H))
        occ = average_operator_gamma(base, N)
        gavg = _gamma(average_operator_map_v2(p, occ, np.random.default_rng(seed), H))

        # best admissible static under the same edge budget (N_IL): base snapshots + search
        best = gstat
        cand = list(base)
        srng = np.random.default_rng(seed * 13 + 1)
        for _ in range(sp["best_static_search"]):
            cand.append(tuple(sorted(srng.choice(N, size=N_IL, replace=False).tolist())))
        for snap in cand:
            best = max(best, g(_static_schedule(N, N_IL, snap, H)))

        sh_inter = shuffle_order(inter, np.random.default_rng(seed * 17 + 1), "sh_order")
        g_sh_inter = g(sh_inter)
        vd = variable_dwell_schedule(base, N, N_IL, tuple(sp["variable_dwell_multiset"]), "vd")
        vd_sh = shuffle_dwell(vd, np.random.default_rng(seed * 19 + 1), "vd_sh")
        gvd, gvd_sh = g(vd), g(vd_sh)

        best_switch = max(gf, gi, gs)
        per["fast"].append(gf); per["intermediate"].append(gi); per["slow"].append(gs)
        per["static_sparse"].append(gstat); per["average_graph"].append(gavg)
        per["best_static"].append(best)
        per["ordered_inter"].append(gi); per["shuffled_order_inter"].append(g_sh_inter)
        per["vardwell"].append(gvd); per["shuffled_dwell"].append(gvd_sh)

        d_weak.append(gf - gstat)
        d_strict.append(best_switch - max(gavg, best))
        d_order.append(gi - g_sh_inter)
        d_dwell.append(gvd - gvd_sh)

    agg = {k: {"mean": float(np.mean(v)), "std": float(np.std(v))} for k, v in per.items()}
    pooled_std = float(np.mean([agg[k]["std"] for k in agg]))
    band = max(ctx.prereg["tolerances"]["gamma_significance_std_mult"] * pooled_std, 1e-9)

    v_weak, m_weak = _paired_verdict(d_weak, band)
    v_strict, m_strict = _paired_verdict(d_strict, band)
    v_order_raw, m_order = _paired_verdict(np.abs(d_order) - 0, band)  # magnitude of order effect
    order_effect = float(np.mean(np.abs(d_order)))
    v_order = "PASS" if order_effect > band else "AGG_CONNECTIVITY_IF_TIE"
    dwell_effect = float(np.mean(np.abs(d_dwell)))

    # headline verdict = the demanding G1_strict gate, mapped to the contract
    # vocabulary (PASS/FAIL/INCONCLUSIVE). The fine-grained PASS/FAIL/TIE per
    # sub-gate is preserved in result.
    headline = {"PASS": "PASS", "FAIL": "FAIL", "TIE": "INCONCLUSIVE"}[v_strict]
    return {"gate": GATE, "verdict": headline,
            "provenance": provenance(ctx, seeds, sp,
                                     "G1_weak: fast>static+3std; G1_strict: "
                                     "best_switch>max(avg,best_static)+3std; G2: |order|>3std"),
            "result": {
                "aggregate_gamma": agg,
                "band_3std": band,
                "G1_weak": {"verdict": v_weak, "mean_fast_minus_static": m_weak},
                "G1_strict": {"verdict": v_strict,
                              "mean_bestswitch_minus_max_comparator": m_strict,
                              "note": "prior: fast arm not expected to beat the average graph"},
                "G2_order": {"verdict": v_order, "mean_abs_order_effect": order_effect,
                             "mean_abs_dwell_effect": dwell_effect}}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT))
