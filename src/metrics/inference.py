"""Single shared inferential function for the paired gates (P1.2-B, contract C).

One rule, used identically by G1_weak, G1_strict and G3:

    * statistic: per-seed paired differences d_i (treatment - comparator);
    * test: EXACT two-sided sign test on the non-zero differences (n=8 seeds are
      too few for an asymptotic test; the exact sign test on 8/8 equal signs gives
      p = 2 * C(8,0) / 2^8 = 0.0078125, which the v3 doc wrongly denied);
    * effect band: band = max(std_mult * std, floor), where `std` is the SAMPLE
      standard deviation of the paired differences with ddof=1;
    * zero handling: differences with |d| <= zero_tol are dropped from the sign
      test (classic tie handling) and reported;
    * decision:
        - if the sign-test p >= alpha            -> INCONCLUSIVE (not significant)
        - elif mean(d) >  band                   -> PASS
        - elif mean(d) < -band                   -> FAIL
        - else (significant but |mean| <= band)  -> INCONCLUSIVE (reason TIE)

A bootstrap CI is reported only as a SECONDARY descriptor with an explicit
small-n caveat; it is NOT part of the decision rule (the v3 error of mixing a
p<0.05 rule with a bootstrap-only rule is removed).
"""
from __future__ import annotations

from math import comb

import numpy as np


def exact_two_sided_sign_test(diffs, zero_tol: float = 1e-12) -> dict:
    d = np.asarray(diffs, dtype=float)
    nonzero = d[np.abs(d) > zero_tol]
    n = int(nonzero.size)
    n_zero = int(d.size - n)
    if n == 0:
        return {"p_value": 1.0, "n_nonzero": 0, "n_zero": n_zero, "n_pos": 0, "n_neg": 0}
    n_pos = int(np.sum(nonzero > 0))
    n_neg = n - n_pos
    k = min(n_pos, n_neg)
    tail = sum(comb(n, i) for i in range(k + 1))
    p = min(1.0, 2.0 * tail / (2 ** n))
    return {"p_value": float(p), "n_nonzero": n, "n_zero": n_zero,
            "n_pos": n_pos, "n_neg": n_neg}


def _bootstrap_ci(diffs, n_boot: int, boot_seed: int, alpha: float = 0.05):
    rng = np.random.default_rng(boot_seed)
    d = np.asarray(diffs, float)
    n = d.size
    if n == 0:
        return [float("nan"), float("nan")]
    means = np.array([rng.choice(d, size=n, replace=True).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return [float(lo), float(hi)]


def paired_decision(diffs, floor: float, std_mult: float, alpha: float,
                    n_boot: int, boot_seed: int) -> dict:
    """The frozen paired decision. Returns a full record (verdict, stats, reason)."""
    d = np.asarray(diffs, dtype=float)
    n = int(d.size)
    mean = float(np.mean(d)) if n else 0.0
    std = float(np.std(d, ddof=1)) if n > 1 else 0.0     # SAMPLE std, ddof=1
    band = max(std_mult * std, floor)
    st = exact_two_sided_sign_test(d)
    p = st["p_value"]
    if p >= alpha:
        verdict, reason = "INCONCLUSIVE", "NOT_SIGNIFICANT"
    elif mean > band:
        verdict, reason = "PASS", None
    elif mean < -band:
        verdict, reason = "FAIL", None
    else:
        verdict, reason = "INCONCLUSIVE", "TIE"
    return {
        "verdict": verdict, "reason": reason,
        "paired_differences": d.tolist(),
        "mean": mean, "sample_std_ddof1": std, "n": n,
        "effect_band": band, "floor": floor, "std_mult": std_mult,
        "sign_test": st, "alpha": alpha,
        "bootstrap_ci95_descriptor": _bootstrap_ci(d, n_boot, boot_seed),
        "bootstrap_small_n_caveat": ("bootstrap CI is a descriptor only, NOT the "
                                     "decision rule; with n<=8 it is unreliable"),
        "std_definition": "sample standard deviation of paired differences, ddof=1",
        "zero_handling": "differences with |d|<=1e-12 dropped from the sign test",
    }
