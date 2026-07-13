"""Ring (circulant) Laplacian for intra-layer coupling."""
from __future__ import annotations

import numpy as np


def ring_laplacian(N: int, radius: int = 1) -> np.ndarray:
    """Zero-row-sum Laplacian of a ring with the given coupling radius.

    For radius=1 this is the paper's Eq. (3): -2 on the diagonal, +1 on the two
    nearest neighbours, with wrap-around. L @ 1 = 0 by construction.
    """
    if N < 2:
        raise ValueError(f"ring requires N>=2, got {N}")
    if radius < 1 or radius >= N // 2 + 1:
        raise ValueError(f"radius must be in [1, N//2], got {radius}")
    A = np.zeros((N, N))
    for k in range(1, radius + 1):
        for i in range(N):
            A[i, (i + k) % N] = 1.0
            A[i, (i - k) % N] = 1.0
    deg = A.sum(axis=1)
    L = A - np.diag(deg)
    return L


def algebraic_connectivity(L: np.ndarray) -> float:
    """lambda_2: second-smallest eigenvalue of a symmetric Laplacian.

    Note: valid only for symmetric non-negative Laplacians. For a graph Laplacian
    L = -M (M the paper's negative-definite matrix), we return the second-smallest
    eigenvalue of the positive-semidefinite graph Laplacian |diag|-A convention.
    Here inputs use the paper's zero-row-sum sign (negative diagonal); we negate to
    get the standard PSD Laplacian before taking eigenvalues.
    """
    Lpsd = -L if np.all(np.diag(L) <= 0) else L
    w = np.linalg.eigvalsh(Lpsd)
    w = np.sort(w)
    return float(w[1])
