"""Linear two-layer financial surrogate (P1.3) and its exact transverse operator.

Reading (see docs/methodology/financial_translation_audit.md, Translation T1):
two venues carry the SAME assets; the object of interest is the per-asset BASIS
(dislocation) d_j = p_{1,j} - p_{2,j}. A common factor drives both venues and
CANCELS in the basis, so the basis is the transverse coordinate. Absent active
arbitrage the basis dynamics are mildly EXPANDING (spectral radius > 1, encoding
'dislocations would grow'); a switched, sparse set of active arbitrage channels
applies contraction 2*kappa on the selected assets. This is the linear image of
the paper's mechanism: switching a sparse stabilizer across a set of transverse
modes.

Two entry points:
  * `difference_step_maps` — the exact per-step maps M_t of the basis system, for
    order-sensitive propagator (gamma) analysis. No simulation noise, no factor.
  * `simulate_observed` — full observable levels p1[t], p2[t] (with common factor,
    idiosyncratic means and noise) plus the ground-truth active set per step, for
    the identifiability experiment (P1.4).

Nothing runs on import.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.networks.ring import ring_laplacian
from src.networks.switching import Schedule


@dataclass(frozen=True)
class SurrogateParams:
    N: int
    kappa: float = 0.5                 # inter-layer (arbitrage) contraction strength
    rho_target: float = 1.03           # spectral radius of the uncoupled basis system
    intra_coupling: float = 0.05       # basis diffusion across assets (ring)
    # --- staged departures from the faithful case (P1.3) ---
    heterogeneity: float = 0.0         # spread in per-asset persistence
    directed: bool = False             # asymmetric intra-layer basis coupling
    signed: bool = False               # allow negative intra-layer couplings
    # --- observation model (for identifiability) ---
    factor_scale: float = 1.0          # common-factor loading scale
    factor_ar: float = 0.95
    idio_ar: float = 0.9
    obs_noise: float = 0.05
    seed_struct: int = 0               # seed for the (frozen) structural matrices

    def rng_struct(self) -> np.random.Generator:
        return np.random.default_rng(self.seed_struct)


def build_basis_operator(p: SurrogateParams) -> np.ndarray:
    """A_intra (N,N): uncoupled basis dynamics, scaled to spectral radius rho_target.

    Base = diagonal persistence + intra-layer ring diffusion. Heterogeneity spreads
    the diagonal; `directed` breaks symmetry; `signed` allows negative couplings.
    """
    N = p.N
    rng = p.rng_struct()
    L = ring_laplacian(N, radius=1)          # zero-row-sum, negative diagonal
    diffusion = p.intra_coupling * L          # diffusive (stabilizing) part
    if p.signed:
        signs = rng.choice([-1.0, 1.0], size=(N, N))
        signs = np.triu(signs, 1); signs = signs + signs.T
        diffusion = diffusion * (0.5 + 0.5 * signs)  # some couplings flipped
    if p.directed:
        asym = 0.5 * p.intra_coupling * rng.standard_normal((N, N))
        np.fill_diagonal(asym, 0.0)
        diffusion = diffusion + asym

    base_persist = np.ones(N)
    if p.heterogeneity > 0:
        base_persist = base_persist + p.heterogeneity * rng.standard_normal(N)
    A = np.diag(base_persist) + diffusion
    # rescale to the target spectral radius (use modulus for possibly-complex eigs)
    r = np.max(np.abs(np.linalg.eigvals(A)))
    if r > 0:
        A = A * (p.rho_target / r)
    return A


def difference_step_maps(p: SurrogateParams, sched: Schedule) -> list[np.ndarray]:
    """Per-step maps M_t = A_intra - 2*kappa*diag(gamma_t) over the whole schedule.

    Contraction of the ordered product of these maps is the exact transverse
    stability of the basis system (metrics.propagator.full_contraction_*).
    """
    A = build_basis_operator(p)
    maps = []
    total = sched.total_steps
    for step in range(total):
        gamma = sched.gamma_at_step(step)
        M = A.copy()
        idx = np.arange(p.N)
        M[idx, idx] -= 2.0 * p.kappa * gamma
        maps.append(M)
    return maps


def simulate_basis(p: SurrogateParams, sched: Schedule, rng: np.random.Generator,
                   noise: float = 0.0) -> np.ndarray:
    """Simulate the basis d[t] (N,) under the schedule. Returns array (T+1, N)."""
    A = build_basis_operator(p)
    T = sched.total_steps
    d = np.zeros((T + 1, p.N))
    d[0] = rng.standard_normal(p.N)
    for t in range(T):
        gamma = sched.gamma_at_step(t)
        M = A.copy(); idx = np.arange(p.N); M[idx, idx] -= 2.0 * p.kappa * gamma
        d[t + 1] = M @ d[t] + (noise * rng.standard_normal(p.N) if noise else 0.0)
    return d


@dataclass
class ObservedData:
    p1: np.ndarray           # (T+1, N) venue-1 levels
    p2: np.ndarray           # (T+1, N) venue-2 levels
    active: np.ndarray       # (T, N) 0/1 ground-truth active inter-layer pair
    factor: np.ndarray       # (T+1,) common factor
    params: SurrogateParams = field(repr=False)


def simulate_observed(p: SurrogateParams, sched: Schedule, rng: np.random.Generator,
                      async_stride: tuple[int, int] = (1, 1)) -> ObservedData:
    """Full observable two-layer levels for identifiability (P1.4).

    p_{i,j}[t] = beta_j * F[t] + m_{i,j}[t], where m carries the idiosyncratic mean
    and the basis. The basis d_j = m_{1,j} - m_{2,j} follows the switched
    contraction; the common mean m_bar follows an idiosyncratic AR(1). Observation
    noise is added. `async_stride` optionally holds each venue's last value except
    every k-th step (crude non-synchronous sampling) to induce Epps-like bias.

    IMPORTANT: `active` is the GROUND TRUTH and must never be used by an estimator
    that only sees p1, p2 (leakage guard).
    """
    N, T = p.N, sched.total_steps
    A = build_basis_operator(p)
    beta = p.factor_scale * (1.0 + 0.3 * rng.standard_normal(N))

    F = np.zeros(T + 1)
    d = np.zeros((T + 1, N))          # basis (transverse)
    mbar = np.zeros((T + 1, N))       # common idiosyncratic mean (per asset)
    d[0] = rng.standard_normal(N)
    mbar[0] = rng.standard_normal(N)
    active = np.zeros((T, N))

    for t in range(T):
        gamma = sched.gamma_at_step(t)
        active[t] = gamma
        F[t + 1] = p.factor_ar * F[t] + rng.standard_normal()
        M = A.copy(); idx = np.arange(N); M[idx, idx] -= 2.0 * p.kappa * gamma
        d[t + 1] = M @ d[t] + 0.1 * rng.standard_normal(N)
        mbar[t + 1] = p.idio_ar * mbar[t] + 0.3 * rng.standard_normal(N)

    m1 = mbar + 0.5 * d
    m2 = mbar - 0.5 * d
    p1 = beta[None, :] * F[:, None] + m1
    p2 = beta[None, :] * F[:, None] + m2
    if p.obs_noise:
        p1 = p1 + p.obs_noise * rng.standard_normal(p1.shape)
        p2 = p2 + p.obs_noise * rng.standard_normal(p2.shape)

    s1, s2 = async_stride
    if s1 > 1:
        p1 = _hold_except_every(p1, s1)
    if s2 > 1:
        p2 = _hold_except_every(p2, s2)
    return ObservedData(p1=p1, p2=p2, active=active, factor=F, params=p)


def _hold_except_every(x: np.ndarray, k: int) -> np.ndarray:
    """Crude non-synchronous sampling: value updates only every k-th step; between
    updates the last observed value is held (staleness)."""
    out = x.copy()
    last = x[0].copy()
    for t in range(x.shape[0]):
        if t % k == 0:
            last = x[t].copy()
        out[t] = last
    return out
