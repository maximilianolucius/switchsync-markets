"""Past-only link-recovery estimators for the identifiability gate (G4).

Library home for the estimators (v1 kept private copies inside its runner; v2
imports these instead, so v2 never depends on the superseded v1 runner).
"""
from __future__ import annotations

import numpy as np


def ar1_coef(win: np.ndarray) -> np.ndarray:
    """Per-column AR(1) self-coefficient over a window (LS of x[t] on x[t-1])."""
    x0, x1 = win[:-1], win[1:]
    num = (x0 * x1).sum(axis=0)
    den = (x0 * x0).sum(axis=0) + 1e-12
    return num / den


def rolling_basis_ar1_estimator(p1: np.ndarray, p2: np.ndarray, N_IL: int,
                                W: int) -> np.ndarray:
    """Flag, at each t>=W, the N_IL pairs with the LOWEST basis AR(1) coefficient
    (strongest mean reversion) over the trailing window [t-W, t) (PAST ONLY). The
    common factor cancels in the venue-difference basis p1-p2."""
    basis = p1 - p2
    T, N = basis.shape[0] - 1, basis.shape[1]
    est = np.zeros((T, N))
    for t in range(W, T):
        coef = ar1_coef(basis[t - W:t])
        est[t, np.argsort(coef)[:N_IL]] = 1.0
    return est


def rolling_levelcorr_estimator(p1: np.ndarray, p2: np.ndarray, N_IL: int,
                                W: int) -> np.ndarray:
    """Naive factor-confounded baseline: flag the N_IL pairs whose venue LEVELS are
    most correlated over the trailing window (a common factor inflates all)."""
    T, N = p1.shape[0] - 1, p1.shape[1]
    est = np.zeros((T, N))
    for t in range(W, T):
        a = p1[t - W:t] - p1[t - W:t].mean(0)
        b = p2[t - W:t] - p2[t - W:t].mean(0)
        corr = (a * b).sum(0) / (np.sqrt((a * a).sum(0) * (b * b).sum(0)) + 1e-12)
        est[t, np.argsort(-corr)[:N_IL]] = 1.0
    return est


def precision_recall(est: np.ndarray, true: np.ndarray, W: int) -> tuple[float, float]:
    T = est.shape[0]
    e = est[W:T].ravel().astype(bool)
    g = true[W:T].ravel().astype(bool)
    tp = int(np.sum(e & g)); fp = int(np.sum(e & ~g)); fn = int(np.sum(~e & g))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall
