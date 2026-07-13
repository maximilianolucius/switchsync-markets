"""FitzHugh-Nagumo double-layer dynamics (faithful to Eser et al. 2507.08007v2).

State layout (node-major, matching the paper's L_i = [u_i1, v_i1, ..., u_iN, v_iN]):

    x = [ L1 ; L2 ],   len(x) = 4N
    layer block i occupies indices [i*2N : (i+1)*2N]
    within a layer, node j (0-based) occupies [2j, 2j+1] = (u, v)

The RHS is written as a fixed linear part plus a cheap cubic nonlinearity plus a
constant, so a full simulation is dominated by one matrix-vector product per RK4
substage:

    dx/dt = (A_const + A_inter(active_set)) @ x + nonlin(x) + b

`A_const` encodes the intra-layer rotational diffusive coupling sigma*(L (x) H)
and the *linear* part of the FHN field; `A_inter` encodes the switching
inter-layer activator coupling sigma12 * (L^I (x) Gamma(t)); `nonlin` is the
-(1/(3 eps)) u^3 term; `b` carries the excitability constants a_ij.

Nothing in this module runs on import.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.networks.ring import ring_laplacian


@dataclass(frozen=True)
class FHNParams:
    """Frozen FHN + coupling parameters. Defaults are the paper's values."""

    N: int
    eps: float = 0.05
    a_odd: float = 0.87          # threshold for odd 1-based ring index (0-based even)
    a_even: float = 0.97         # threshold for even 1-based ring index (0-based odd)
    phi: float = np.pi / 2 - 0.1
    sigma_intra: float = 0.1     # sigma_1 = sigma_2
    sigma_inter: float = 0.1     # sigma_12
    radius: int = 1              # intra-layer coupling radius

    def a_vector(self) -> np.ndarray:
        """Per-node excitability a_j. 1-based odd index -> a_odd (paper p.2)."""
        idx = np.arange(self.N)                 # 0-based
        one_based = idx + 1
        return np.where(one_based % 2 == 1, self.a_odd, self.a_even).astype(float)


def rotational_coupling(phi: float) -> np.ndarray:
    """H = [[cos, sin], [-sin, cos]] (paper Eq. between (3) and (4))."""
    c, s = np.cos(phi), np.sin(phi)
    return np.array([[c, s], [-s, c]], dtype=float)


def _intra_layer_linear_operator(p: FHNParams) -> np.ndarray:
    """M_intra = sigma*(L (x) H) + I_N (x) F_lin,  shape (2N, 2N).

    F_lin is the linear part of the FHN node field:
        du/dt linear-in-(u,v): (1/eps) u - (1/eps) v
        dv/dt linear-in-(u,v): u
    i.e. F_lin = [[1/eps, -1/eps], [1, 0]].
    """
    N = p.N
    L = ring_laplacian(N, radius=p.radius)
    H = rotational_coupling(p.phi)
    LxH = np.kron(L, H)                          # (2N, 2N)
    F_lin = np.array([[1.0 / p.eps, -1.0 / p.eps], [1.0, 0.0]])
    IxF = np.kron(np.eye(N), F_lin)
    return p.sigma_intra * LxH + IxF


def build_const_operator(p: FHNParams) -> np.ndarray:
    """A_const (4N, 4N): block-diagonal identical intra-layer operators."""
    M = _intra_layer_linear_operator(p)
    A = np.zeros((4 * p.N, 4 * p.N))
    A[: 2 * p.N, : 2 * p.N] = M
    A[2 * p.N :, 2 * p.N :] = M
    return A


def build_const_vector(p: FHNParams) -> np.ndarray:
    """b (4N,): the constant a_ij term entering each dv/dt = u + a."""
    a = p.a_vector()
    b_layer = np.zeros(2 * p.N)
    b_layer[1::2] = a                            # v-equations
    return np.concatenate([b_layer, b_layer])


def u_indices(N: int) -> tuple[np.ndarray, np.ndarray]:
    """Global indices of activator (u) components for layer 1 and layer 2."""
    u1 = 2 * np.arange(N)
    u2 = 2 * N + 2 * np.arange(N)
    return u1, u2


def build_inter_operator(p: FHNParams, gamma: np.ndarray) -> np.ndarray:
    """A_inter (4N, 4N) from a per-pair coupling-weight vector gamma (length N).

    sigma12 * (L^I (x) Gamma), L^I = [[-1,1],[1,-1]], Gamma = diag over u of mirror
    nodes weighted by gamma_j. For pair j:
        du_{1j}/dt += sigma12 gamma_j (u_{2j} - u_{1j})
        du_{2j}/dt += sigma12 gamma_j (u_{1j} - u_{2j})

    Switching schedules pass a 0/1 gamma; the time-averaged (average-graph)
    baseline passes gamma_j = occupancy_j in [0,1].
    """
    N = p.N
    gamma = np.asarray(gamma, dtype=float)
    if gamma.shape != (N,):
        raise ValueError(f"gamma must have shape ({N},), got {gamma.shape}")
    A = np.zeros((4 * N, 4 * N))
    s = p.sigma_inter
    u1, u2 = u_indices(N)
    for j in range(N):
        g = gamma[j]
        if g == 0.0:
            continue
        i1, i2 = u1[j], u2[j]
        A[i1, i1] -= s * g
        A[i1, i2] += s * g
        A[i2, i2] -= s * g
        A[i2, i1] += s * g
    return A


def gamma_from_pairs(N: int, active_pairs: np.ndarray) -> np.ndarray:
    """0/1 coupling-weight vector from a set of active mirror-pair indices."""
    g = np.zeros(N)
    ap = np.asarray(active_pairs, dtype=int)
    if ap.size:
        g[ap] = 1.0
    return g


def nonlinearity(x: np.ndarray, p: FHNParams) -> np.ndarray:
    """The -(1/(3 eps)) u^3 term, on activator components only."""
    out = np.zeros_like(x)
    u1, u2 = u_indices(p.N)
    coef = -1.0 / (3.0 * p.eps)
    out[u1] = coef * x[u1] ** 3
    out[u2] = coef * x[u2] ** 3
    return out


def make_rhs(p: FHNParams, A_const: np.ndarray, b: np.ndarray):
    """Return f(x, A_inter) -> dx/dt. A_inter is passed in so the caller controls
    switching (rebuilt only on switch events)."""

    def rhs(x: np.ndarray, A_inter: np.ndarray) -> np.ndarray:
        return (A_const + A_inter) @ x + b + nonlinearity(x, p)

    return rhs


# ---------------------------------------------------------------------------
# Single-layer field and Jacobian (for chaos / Lyapunov and variational eqs)
# ---------------------------------------------------------------------------

def single_layer_operator(p: FHNParams) -> np.ndarray:
    """Linear operator M_intra for one isolated layer (2N, 2N)."""
    return _intra_layer_linear_operator(p)


def single_layer_rhs(x: np.ndarray, p: FHNParams, M: np.ndarray, b_layer: np.ndarray) -> np.ndarray:
    """dx/dt for one isolated layer (sigma_12 = 0). x has length 2N."""
    out = M @ x + b_layer
    out[0::2] += (-1.0 / (3.0 * p.eps)) * x[0::2] ** 3
    return out


def single_layer_jacobian(x: np.ndarray, p: FHNParams, M: np.ndarray) -> np.ndarray:
    """Jacobian DG of the isolated-layer field at state x (2N, 2N).

    Equals M with the activator self-coupling (1/eps) replaced by the nonlinear
    derivative (1/eps)(1 - u^2) at each node.
    """
    J = M.copy()
    u = x[0::2]
    # diagonal u-rows are indices 0,2,4,...; F_lin contributed (1/eps) there.
    add = (1.0 / p.eps) * (1.0 - u ** 2) - (1.0 / p.eps)
    for k in range(p.N):
        J[2 * k, 2 * k] += add[k]
    return J
