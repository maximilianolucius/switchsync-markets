"""Gate G4: identifiability. Generate observations from a TRUE switching network,
then try to recover the active inter-layer links using ONLY past observations.

Two estimators, to expose the common-factor confound:
  * basis estimator: uses the venue difference d_j = p1_j - p2_j (the common
    factor cancels). Active links contract the basis -> low recent basis variance.
  * level-correlation estimator (naive): flags a link where the two venues' LEVELS
    are highly correlated in the window. Because a common factor drives both
    levels, this manufactures links everywhere -> the common-factor false-link
    failure the brief asks us to demonstrate.

No estimator ever sees `active` (ground truth) or any data after time t.
"""
from __future__ import annotations

import numpy as np

from _common import REPORT_DIR, append_registry, atomic_write_json, load_contract
from src.networks.switching import random_switching
from src.simulation.linear_surrogate import SurrogateParams, simulate_observed
from src.validation.freeze import config_hash


def _ar1_coef(win):
    """Per-column AR(1) self-coefficient over a window (least squares of x[t] on
    x[t-1]). Returns array of length N. Active inter-layer coupling drives the
    basis self-coefficient negative (mean reversion); inactive pairs stay >~1."""
    x0 = win[:-1]
    x1 = win[1:]
    num = (x0 * x1).sum(axis=0)
    den = (x0 * x0).sum(axis=0) + 1e-12
    return num / den


def _rolling_basis_estimator(p1, p2, N_IL, W):
    """For each t>=W, estimate per-pair AR(1) coefficient of the basis over the
    trailing window [t-W, t) (PAST ONLY) and flag the N_IL pairs with the LOWEST
    coefficient (strongest mean reversion) as active. The common factor cancels in
    the basis by construction, so no explicit factor removal is needed here."""
    T = p1.shape[0] - 1
    basis = p1 - p2                       # (T+1, N); common factor already cancels
    N = p1.shape[1]
    est = np.zeros((T, N))
    for t in range(W, T):
        win = basis[t - W:t]              # PAST ONLY
        coef = _ar1_coef(win)
        active_idx = np.argsort(coef)[:N_IL]
        est[t, active_idx] = 1.0
    return est


def _rolling_levelcorr_estimator(p1, p2, N_IL, W):
    """Naive: flag the N_IL assets whose venue LEVELS are most correlated over the
    trailing window. Common factor inflates all correlations -> false links."""
    T = p1.shape[0] - 1
    N = p1.shape[1]
    est = np.zeros((T, N))
    for t in range(W, T):
        a = p1[t - W:t]; b = p2[t - W:t]
        a = a - a.mean(0); b = b - b.mean(0)
        num = (a * b).sum(0)
        den = np.sqrt((a * a).sum(0) * (b * b).sum(0)) + 1e-12
        corr = num / den
        active_idx = np.argsort(-corr)[:N_IL]
        est[t, active_idx] = 1.0
    return est


def _precision_recall(est, true, W):
    T = est.shape[0]
    e = est[W:T].ravel().astype(bool)
    g = true[W:T].ravel().astype(bool)
    tp = int(np.sum(e & g)); fp = int(np.sum(e & ~g)); fn = int(np.sum(~e & g))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def _contraction_corr(p1, p2, params, sched, W):
    """Correlate TRUE per-window basis contraction with the OBSERVED one.
    True basis is recomputed noise-free; observed is from p1-p2 (with obs noise)."""
    from src.simulation.linear_surrogate import simulate_basis
    rng = np.random.default_rng(999)
    d_true = simulate_basis(params, sched, rng, noise=0.0)
    d_obs = p1 - p2
    T = d_true.shape[0] - 1
    true_c, obs_c = [], []
    for t in range(W, T):
        n0t = np.linalg.norm(d_true[t - W]); n1t = np.linalg.norm(d_true[t])
        n0o = np.linalg.norm(d_obs[t - W]); n1o = np.linalg.norm(d_obs[t])
        if n0t > 1e-9 and n0o > 1e-9:
            true_c.append(np.log(n1t / n0t))
            obs_c.append(np.log(n1o / n0o))
    if len(true_c) < 3:
        return 0.0
    return float(np.corrcoef(true_c, obs_c)[0, 1])


def run(c: dict) -> dict:
    idc = c["identifiability"]
    N, N_IL, H, W = idc["N"], idc["N_IL"], idc["horizon_steps"], idc["estimator_window"]
    df = idc["dwell_fast"]
    out = {}
    for async_stride in idc["async_variants"]:
        key = f"async_{async_stride[0]}_{async_stride[1]}"
        basis_pr, basis_re, corr, lvl_pr, lvl_re = [], [], [], [], []
        for seed in idc["seeds"]:
            p = SurrogateParams(N=N, kappa=idc["kappa"], rho_target=idc["rho_target"],
                                intra_coupling=idc["intra_coupling"],
                                obs_noise=idc["obs_noise"],
                                factor_scale=idc["factor_scale"], seed_struct=seed)
            sched = random_switching(N, N_IL, df, H // df + 1,
                                     np.random.default_rng(seed * 7 + 1), "fast")
            data = simulate_observed(p, sched, np.random.default_rng(seed * 7 + 2),
                                     async_stride=tuple(async_stride))
            est_b = _rolling_basis_estimator(data.p1, data.p2, N_IL, W)
            est_l = _rolling_levelcorr_estimator(data.p1, data.p2, N_IL, W)
            pb, rb = _precision_recall(est_b, data.active, W)
            pl, rl = _precision_recall(est_l, data.active, W)
            basis_pr.append(pb); basis_re.append(rb)
            lvl_pr.append(pl); lvl_re.append(rl)
            corr.append(_contraction_corr(data.p1, data.p2, p, sched, W))
        out[key] = {
            "basis_precision": float(np.mean(basis_pr)),
            "basis_recall": float(np.mean(basis_re)),
            "levelcorr_precision": float(np.mean(lvl_pr)),
            "levelcorr_recall": float(np.mean(lvl_re)),
            "contraction_corr": float(np.mean(corr)),
        }
    return out


def evaluate(res: dict) -> dict:
    sync = res["async_1_1"]
    passed = (sync["basis_precision"] > 0.6 and sync["basis_recall"] > 0.6
              and sync["contraction_corr"] > 0.5)
    verdict = "PASS" if passed else "FAIL"
    return {
        "verdict": verdict,
        "synchronous": sync,
        "false_link_gap": sync["basis_precision"] - sync["levelcorr_precision"],
        "note": ("basis (venue-difference) estimator removes the common factor by "
                 "construction; the level-correlation estimator inflates precision-"
                 "loss via factor-induced false links, demonstrated by the gap"),
    }


def main() -> None:
    c = load_contract()
    h = config_hash(c)
    res = run(c)
    ev = evaluate(res)
    result = {"experiment": "identifiability_g4", "config_hash": h,
              "results": res, "evaluation": ev, "gate": "G4",
              "verdict": ev["verdict"], "summary": str(ev["synchronous"])}
    out = REPORT_DIR / "identifiability_g4.json"
    atomic_write_json(out, result)
    append_registry({"experiment": "identifiability_g4", "config_hash": h,
                     "result_file": str(out.relative_to(out.parents[2])),
                     "gate": "G4", "verdict": ev["verdict"],
                     "summary": str(ev["synchronous"])})
    for k, v in res.items():
        print(f"  {k}: basis P/R={v['basis_precision']:.2f}/{v['basis_recall']:.2f} "
              f"levelcorr P/R={v['levelcorr_precision']:.2f}/{v['levelcorr_recall']:.2f} "
              f"contraction_corr={v['contraction_corr']:.2f}")
    print(f"G4 verdict: {ev}")


if __name__ == "__main__":
    main()
