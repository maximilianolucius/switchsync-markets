"""Order-sensitive transverse-contraction metric for LINEAR diffusive systems
(temporal_stability_metrics.md sec.4).

For dx/dt = -kappa L_t x integrated with step dt, the horizon-H state map is the
ordered product Phi = prod_{s=H-1..0} expm(-kappa L_s dt). The transverse
contraction factor is the largest singular value of P_perp Phi P_perp; the rate
is -(1/(H dt)) log(that).

This is the linear analogue of the paper's transverse Lyapunov exponent and,
unlike G_switch, is sensitive to switching rate, order, and reachability.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import expm


def transverse_projector(n: int) -> np.ndarray:
    """P_perp = I - 11^T/n (projects off the consensus/synchronization direction)."""
    return np.eye(n) - np.ones((n, n)) / n


def ordered_propagator(laplacians: list[np.ndarray], kappa: float, dt: float) -> np.ndarray:
    """Phi(t0,H) = expm(-kappa L_{H-1} dt) ... expm(-kappa L_0 dt).

    `laplacians` is the time-ordered list L_0..L_{H-1} (the earliest first). The
    product is built so the earliest generator is applied first (rightmost).
    """
    if not laplacians:
        raise ValueError("need at least one Laplacian")
    n = laplacians[0].shape[0]
    Phi = np.eye(n)
    for L in laplacians:          # earliest -> latest, left-multiply
        Phi = expm(-kappa * L * dt) @ Phi
    return Phi


def ordered_product(step_maps: list[np.ndarray]) -> np.ndarray:
    """Ordered product of explicit per-step linear maps M_0..M_{H-1}:
    Phi = M_{H-1} ... M_1 M_0 (earliest applied first / rightmost).

    Used for discrete-time surrogates whose one-step map is already known (no
    matrix exponential needed)."""
    if not step_maps:
        raise ValueError("need at least one map")
    Phi = np.eye(step_maps[0].shape[0])
    for M in step_maps:
        Phi = M @ Phi
    return Phi


def full_contraction_factor(Phi: np.ndarray) -> float:
    """sigma_max(Phi): worst-case gain of a system whose entire state is already
    transverse (e.g. a basis/difference system with the common mode removed)."""
    s = np.linalg.svd(Phi, compute_uv=False)
    return float(s[0])


def full_contraction_rate(Phi: np.ndarray, horizon_time: float) -> float:
    c = max(full_contraction_factor(Phi), 1e-300)
    return float(-np.log(c) / horizon_time)


def transverse_contraction_factor(Phi: np.ndarray) -> float:
    """sigma_max(P_perp Phi P_perp): worst-case transverse gain over the horizon."""
    n = Phi.shape[0]
    P = transverse_projector(n)
    M = P @ Phi @ P
    s = np.linalg.svd(M, compute_uv=False)
    return float(s[0])


def transverse_contraction_rate(Phi: np.ndarray, horizon_time: float) -> float:
    """gamma = -(1/(H dt)) log sigma_max(P_perp Phi P_perp).  >0 => net contraction."""
    c = transverse_contraction_factor(Phi)
    c = max(c, 1e-300)
    return float(-np.log(c) / horizon_time)


def schedule_contraction_rate(laplacian_sequence: list[np.ndarray], kappa: float,
                              dt: float) -> float:
    """Convenience: build the ordered propagator over the whole sequence and
    return the transverse contraction rate."""
    Phi = ordered_propagator(laplacian_sequence, kappa, dt)
    horizon_time = len(laplacian_sequence) * dt
    return transverse_contraction_rate(Phi, horizon_time)
