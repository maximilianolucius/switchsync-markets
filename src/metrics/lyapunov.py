"""Lyapunov exponents.

`largest_lyapunov_isolated_layer`: Benettin method for a single isolated FHN ring
layer (sigma_12 = 0), to confirm chaos (paper Fig. 2, lambda_max ~ 0.04 > 0).

`transverse_lyapunov`: finite-time transverse Lyapunov exponent of the double-
layer synchronized state via the FULL variational equation
    d(dTheta)/dt = [DG(S(t)) - sigma_12 * lam_perp * Gamma(t)] dTheta
integrated along the synchronized trajectory S(t) (paper Eqs. 6-8; our
temporal_stability_metrics.md sec.6). This is the paper's MSF Psi for the minimal
system. DISCIPLINE: this is only a Lyapunov exponent because both a dynamical
system and its variational equation are explicitly defined here.
"""
from __future__ import annotations

import numpy as np

from src.dynamics.fhn import (
    FHNParams,
    single_layer_jacobian,
    single_layer_operator,
    single_layer_rhs,
)


def _rk4_layer(x, p, M, b_layer, dt):
    k1 = single_layer_rhs(x, p, M, b_layer)
    k2 = single_layer_rhs(x + 0.5 * dt * k1, p, M, b_layer)
    k3 = single_layer_rhs(x + 0.5 * dt * k2, p, M, b_layer)
    k4 = single_layer_rhs(x + dt * k3, p, M, b_layer)
    return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def _rk4_state_tangent(x, v, p, M, b_layer, dt, coupling_diag=None):
    """Co-integrate state x and tangent v with one RK4 step, evaluating the
    Jacobian at each substage state (not frozen). If coupling_diag is given it is
    subtracted from the Jacobian diagonal (transverse inter-layer coupling)."""

    def fx(s):
        return single_layer_rhs(s, p, M, b_layer)

    def Jv(s, w):
        J = single_layer_jacobian(s, p, M)
        if coupling_diag is not None:
            J = J.copy()
            idx = np.arange(J.shape[0])
            J[idx, idx] -= coupling_diag
        return J @ w

    k1 = fx(x); j1 = Jv(x, v)
    x2 = x + 0.5 * dt * k1; k2 = fx(x2); j2 = Jv(x2, v + 0.5 * dt * j1)
    x3 = x + 0.5 * dt * k2; k3 = fx(x3); j3 = Jv(x3, v + 0.5 * dt * j2)
    x4 = x + dt * k3;       k4 = fx(x4); j4 = Jv(x4, v + dt * j3)
    x_new = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    v_new = v + (dt / 6.0) * (j1 + 2 * j2 + 2 * j3 + j4)
    return x_new, v_new


def largest_lyapunov_isolated_layer(p: FHNParams, x0: np.ndarray, dt: float,
                                    n_steps: int, renorm_every: int = 10,
                                    transient_steps: int = 2000) -> float:
    """Benettin largest Lyapunov exponent of one isolated FHN ring layer.

    Integrates the trajectory and a tangent vector, renormalizing periodically and
    accumulating log growth. Returns lambda_max (per unit time).
    """
    M = single_layer_operator(p)
    a = p.a_vector()
    b_layer = np.zeros(2 * p.N)
    b_layer[1::2] = a

    x = x0.astype(float).copy()
    # burn-in transient onto the attractor
    for _ in range(transient_steps):
        x = _rk4_layer(x, p, M, b_layer, dt)

    rng = np.random.default_rng(0)
    v = rng.standard_normal(2 * p.N)
    v /= np.linalg.norm(v)

    log_sum = 0.0
    n_renorm = 0
    for step in range(n_steps):
        x, v = _rk4_state_tangent(x, v, p, M, b_layer, dt)
        if (step + 1) % renorm_every == 0:
            nrm = np.linalg.norm(v)
            if nrm <= 0 or not np.isfinite(nrm):
                raise FloatingPointError("tangent vector collapsed/blew up")
            log_sum += np.log(nrm)
            v /= nrm
            n_renorm += 1

    total_time = n_renorm * renorm_every * dt
    return float(log_sum / total_time)


def transverse_lyapunov(p: FHNParams, lam_perp: float, gamma_of_step,
                        x0_sync: np.ndarray, dt: float, n_steps: int,
                        renorm_every: int = 10, transient_steps: int = 2000) -> float:
    """Finite-time transverse Lyapunov exponent (the minimal-system MSF Psi).

    `gamma_of_step(step) -> length-N 0/1 (or smoothed) vector` gives the active
    inter-layer coupling of the transverse block at each step. The synchronized
    trajectory S(t) is the single-layer dynamics; the transverse perturbation
    evolves under DG(S) minus sigma_12 * lam_perp * diag(gamma on activators).
    Returns Lambda_perp per unit time; <0 => stable synchronization.
    """
    M = single_layer_operator(p)
    a = p.a_vector()
    b_layer = np.zeros(2 * p.N)
    b_layer[1::2] = a

    s = x0_sync.astype(float).copy()
    for _ in range(transient_steps):
        s = _rk4_layer(s, p, M, b_layer, dt)

    rng = np.random.default_rng(1)
    dtheta = rng.standard_normal(2 * p.N)
    dtheta /= np.linalg.norm(dtheta)

    log_sum = 0.0
    n_renorm = 0
    for step in range(n_steps):
        gamma = np.asarray(gamma_of_step(step), dtype=float)
        # transverse coupling acts on activator components only
        coupling = np.zeros(2 * p.N)
        coupling[0::2] = p.sigma_inter * lam_perp * gamma
        s, dtheta = _rk4_state_tangent(s, dtheta, p, M, b_layer, dt,
                                       coupling_diag=coupling)
        if (step + 1) % renorm_every == 0:
            nrm = np.linalg.norm(dtheta)
            if nrm <= 0 or not np.isfinite(nrm):
                raise FloatingPointError("transverse perturbation collapsed/blew up")
            log_sum += np.log(nrm)
            dtheta /= nrm
            n_renorm += 1

    total_time = n_renorm * renorm_every * dt
    return float(log_sum / total_time)
