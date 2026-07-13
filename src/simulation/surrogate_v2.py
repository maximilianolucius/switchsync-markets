"""v2 linear surrogate corrections (audit defects D8, D10).

D8 (signed): `build_basis_operator_v2` introduces genuinely NEGATIVE off-diagonal
couplings with a preserved coupling budget (Frobenius norm of the off-diagonal
block), a documented sign distribution, an explicit diagonal construction, and a
reported spectral radius. It returns (A, meta).

D10 (ground truth): `simulate_observed_v2` records `d_true`, the EXACT noise-free
basis realization that generated p1/p2 in the SAME run, so contraction correlation
uses the same realization instead of an independent one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.networks.ring import ring_laplacian
from src.networks.switching import Schedule
from src.simulation.linear_surrogate import SurrogateParams


def build_basis_operator_v2(p: SurrogateParams, rng: np.random.Generator,
                            neg_fraction: float = 0.4):
    """Basis dynamics operator with correct signed/heterogeneous/directed options.

    Returns (A, meta). For the signed case, a symmetric sign matrix flips a fraction
    of the ring off-diagonal couplings to strictly negative while preserving the
    off-diagonal Frobenius norm (budget), then A is rescaled to rho_target.
    """
    N = p.N
    L = ring_laplacian(N, radius=1)            # zero-row-sum; off-diag +1 on ring
    adj = (L - np.diag(np.diag(L)))            # ring adjacency (0/1), symmetric
    mag = p.intra_coupling * adj               # coupling magnitudes
    off = mag.copy()

    n_negative = 0
    if p.signed:
        # symmetric sign matrix: flip a fraction of existing edges to negative
        iu = np.triu_indices(N, 1)
        edge_mask = adj[iu] > 0
        signs_u = np.ones(len(iu[0]))
        edge_idx = np.where(edge_mask)[0]
        k = int(round(neg_fraction * len(edge_idx)))
        flip = rng.choice(edge_idx, size=k, replace=False) if k > 0 else np.array([], int)
        signs_u[flip] = -1.0
        S = np.zeros((N, N))
        S[iu] = signs_u
        S = S + S.T
        off = mag * S                          # magnitudes preserved, some negative
        n_negative = int(np.sum(off < -1e-12))

    if p.directed:
        asym = 0.5 * p.intra_coupling * rng.standard_normal((N, N))
        np.fill_diagonal(asym, 0.0)
        off = off + asym

    base_persist = np.ones(N)
    if p.heterogeneity > 0:
        base_persist = base_persist + p.heterogeneity * rng.standard_normal(N)

    A = np.diag(base_persist) + off
    r = float(np.max(np.abs(np.linalg.eigvals(A))))
    if r > 0:
        A = A * (p.rho_target / r)

    off_final = A - np.diag(np.diag(A))
    meta = {
        "signed": p.signed,
        "directed": p.directed,
        "heterogeneity": p.heterogeneity,
        "n_negative_offdiag": int(np.sum(off_final < -1e-12)),
        "frac_negative_offdiag": float(np.mean(off_final[np.abs(off_final) > 1e-12] < 0))
                                  if np.any(np.abs(off_final) > 1e-12) else 0.0,
        "offdiag_frobenius_budget": float(np.linalg.norm(off_final)),
        "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(A)))),
        "symmetric": bool(np.allclose(A, A.T)),
        "neg_fraction_requested": neg_fraction if p.signed else 0.0,
    }
    return A, meta


@dataclass
class ObservedDataV2:
    p1: np.ndarray            # (T+1, N) venue-1 levels (with factor + noise)
    p2: np.ndarray            # (T+1, N) venue-2 levels
    active: np.ndarray        # (T, N) ground-truth active pair
    factor: np.ndarray        # (T+1,) common factor
    d_true: np.ndarray        # (T+1, N) EXACT noise-free basis realization (same run)
    params: SurrogateParams = field(repr=False)


def simulate_observed_v2(p: SurrogateParams, sched: Schedule,
                         rng: np.random.Generator,
                         async_stride: tuple[int, int] = (1, 1),
                         signed_operator: bool = False) -> ObservedDataV2:
    """Like linear_surrogate.simulate_observed but records d_true (same realization)
    and can use the corrected signed operator. p1/p2 are built directly from the
    recorded basis, so d_true = the structural part of p1-p2 exactly."""
    N, T = p.N, sched.total_steps
    if signed_operator or p.signed or p.directed:
        A, _ = build_basis_operator_v2(p, np.random.default_rng(p.seed_struct))
    else:
        from src.simulation.linear_surrogate import build_basis_operator
        A = build_basis_operator(p)

    beta = p.factor_scale * (1.0 + 0.3 * rng.standard_normal(N))
    F = np.zeros(T + 1)
    d = np.zeros((T + 1, N))
    mbar = np.zeros((T + 1, N))
    d[0] = rng.standard_normal(N)
    mbar[0] = rng.standard_normal(N)
    active = np.zeros((T, N))
    idx = np.arange(N)
    for t in range(T):
        gamma = sched.gamma_at_step(t)
        active[t] = gamma
        F[t + 1] = p.factor_ar * F[t] + rng.standard_normal()
        M = A.copy(); M[idx, idx] -= 2.0 * p.kappa * gamma
        d[t + 1] = M @ d[t] + 0.1 * rng.standard_normal(N)
        mbar[t + 1] = p.idio_ar * mbar[t] + 0.3 * rng.standard_normal(N)

    m1 = mbar + 0.5 * d
    m2 = mbar - 0.5 * d
    p1 = beta[None, :] * F[:, None] + m1
    p2 = beta[None, :] * F[:, None] + m2
    if p.obs_noise:
        p1 = p1 + p.obs_noise * rng.standard_normal(p1.shape)
        p2 = p2 + p.obs_noise * rng.standard_normal(p2.shape)

    from src.simulation.linear_surrogate import _hold_except_every
    s1, s2 = async_stride
    if s1 > 1:
        p1 = _hold_except_every(p1, s1)
    if s2 > 1:
        p2 = _hold_except_every(p2, s2)

    # d_true is the EXACT noise-free basis realization from this run (m1 - m2 = d).
    return ObservedDataV2(p1=p1, p2=p2, active=active, factor=F, d_true=d, params=p)


def contraction_corr_same_realization(data: ObservedDataV2, W: int) -> float:
    """Correlate TRUE per-window basis contraction (from d_true, the same run)
    against the OBSERVED one (from p1-p2, with noise). Uses the SAME realization,
    unlike the v1 version which drew an independent trajectory."""
    d_true = data.d_true
    d_obs = data.p1 - data.p2
    T = d_true.shape[0] - 1
    tc, oc = [], []
    for t in range(W, T):
        n0t, n1t = np.linalg.norm(d_true[t - W]), np.linalg.norm(d_true[t])
        n0o, n1o = np.linalg.norm(d_obs[t - W]), np.linalg.norm(d_obs[t])
        if n0t > 1e-9 and n0o > 1e-9:
            tc.append(np.log(n1t / n0t)); oc.append(np.log(n1o / n0o))
    if len(tc) < 3:
        return 0.0
    return float(np.corrcoef(tc, oc)[0, 1])
