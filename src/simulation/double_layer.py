"""Integrate the FHN double-layer system under a switching schedule and record
the inter-layer synchronization error.

Fixed-step RK4. The inter-layer operator is rebuilt only when the active link set
changes (epoch boundaries), so the per-step cost is dominated by one dense
matrix-vector product.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.dynamics.fhn import (
    FHNParams,
    build_const_operator,
    build_const_vector,
    build_inter_operator,
)
from src.metrics.sync import inter_layer_error, pair_error
from src.networks.switching import Schedule
from src.validation.checks import assert_finite


@dataclass(frozen=True)
class SimConfig:
    dt: float = 0.01
    total_time: float = 400.0
    record_every: int = 10          # subsample factor for the error time series
    record_pair: int | None = None  # if set, also record E_j for this node


@dataclass(frozen=True)
class SimResult:
    times: np.ndarray
    e12: np.ndarray
    e_pair: np.ndarray | None
    final_state: np.ndarray
    n_steps: int
    label: str


def initial_state(N: int, rng: np.random.Generator) -> np.ndarray:
    """Random ICs u,v in [-2,2] for both layers (paper p.3). Length 4N."""
    return rng.uniform(-2.0, 2.0, size=4 * N)


def simulate_fixed_gamma(p: FHNParams, gamma: np.ndarray, cfg: SimConfig,
                         x0: np.ndarray, label: str = "fixed_gamma") -> SimResult:
    """Simulate with a constant (possibly fractional) coupling-weight vector.

    Used for the average-graph baseline: gamma_j = occupancy_j gives a static
    weighted coupling with the same time-average as a switching schedule but zero
    switching. This is the mandatory 'time-averaged static topology' control.
    """
    N = p.N
    A = build_const_operator(p) + build_inter_operator(p, gamma)
    b = build_const_vector(p)
    n_steps = int(round(cfg.total_time / cfg.dt))
    dt = cfg.dt
    x = x0.astype(float).copy()

    def deriv(state):
        out = A @ state + b
        out[0 : 2 * N : 2] += (-1.0 / (3.0 * p.eps)) * state[0 : 2 * N : 2] ** 3
        out[2 * N :: 2] += (-1.0 / (3.0 * p.eps)) * state[2 * N :: 2] ** 3
        return out

    n_rec = n_steps // cfg.record_every + 1
    times = np.empty(n_rec); e12 = np.empty(n_rec); rec = 0
    for step in range(n_steps):
        if step % cfg.record_every == 0:
            times[rec] = step * dt
            e12[rec] = inter_layer_error(x, N)
            rec += 1
        k1 = deriv(x); k2 = deriv(x + 0.5 * dt * k1)
        k3 = deriv(x + 0.5 * dt * k2); k4 = deriv(x + dt * k3)
        x = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        if not np.all(np.isfinite(x)):
            raise FloatingPointError(f"non-finite state at step {step}")
    times[rec] = n_steps * dt; e12[rec] = inter_layer_error(x, N); rec += 1
    return SimResult(times[:rec], e12[:rec], None, x, n_steps, label)


class DeadlineExceeded(Exception):
    """Raised by simulate() when abort_check() returns True between chunks."""


def simulate(p: FHNParams, sched: Schedule, cfg: SimConfig, x0: np.ndarray,
             chunk_steps: int | None = None, abort_check=None) -> SimResult:
    """Integrate the FHN double layer. If `chunk_steps` and `abort_check` are given,
    `abort_check()` is polled every `chunk_steps` integration steps; if it returns
    True, DeadlineExceeded is raised so a wall-clock deadline can stop a long
    simulation mid-cell (G0A chunked deadline)."""
    N = p.N
    A_const = build_const_operator(p)
    b = build_const_vector(p)
    n_steps = int(round(cfg.total_time / cfg.dt))
    dt = cfg.dt

    x = x0.astype(float).copy()
    assert_finite(x, "initial_state")
    if x.shape != (4 * N,):
        raise ValueError(f"x0 must have shape ({4*N},), got {x.shape}")

    # Precompute the active-set gamma per step lazily: track current epoch.
    cur_gamma_key = None
    A_inter = np.zeros_like(A_const)

    def deriv(state, A_inter_local):
        out = (A_const + A_inter_local) @ state + b
        # cubic nonlinearity on activator components (indices 0,2,... in each layer)
        u1 = state[0 : 2 * N : 2]
        u2 = state[2 * N :: 2]
        out[0 : 2 * N : 2] += (-1.0 / (3.0 * p.eps)) * u1 ** 3
        out[2 * N :: 2] += (-1.0 / (3.0 * p.eps)) * u2 ** 3
        return out

    n_rec = n_steps // cfg.record_every + 1
    times = np.empty(n_rec)
    e12 = np.empty(n_rec)
    e_pair = np.empty(n_rec) if cfg.record_pair is not None else None
    rec = 0

    for step in range(n_steps):
        if chunk_steps and abort_check is not None and step > 0 and step % chunk_steps == 0:
            if abort_check():
                raise DeadlineExceeded(f"aborted at step {step}/{n_steps}")
        gamma = sched.gamma_at_step(step)
        key = gamma.tobytes()
        if key != cur_gamma_key:
            A_inter = build_inter_operator(p, gamma)
            cur_gamma_key = key

        if step % cfg.record_every == 0:
            times[rec] = step * dt
            e12[rec] = inter_layer_error(x, N)
            if e_pair is not None:
                e_pair[rec] = pair_error(x, N, cfg.record_pair)
            rec += 1

        k1 = deriv(x, A_inter)
        k2 = deriv(x + 0.5 * dt * k1, A_inter)
        k3 = deriv(x + 0.5 * dt * k2, A_inter)
        k4 = deriv(x + dt * k3, A_inter)
        x = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        if not np.all(np.isfinite(x)):
            raise FloatingPointError(
                f"non-finite state at step {step} (dt={dt} may be too large)")

    # final record
    times[rec] = n_steps * dt
    e12[rec] = inter_layer_error(x, N)
    if e_pair is not None:
        e_pair[rec] = pair_error(x, N, cfg.record_pair)
    rec += 1

    return SimResult(times[:rec], e12[:rec],
                     None if e_pair is None else e_pair[:rec],
                     x, n_steps, sched.label)
