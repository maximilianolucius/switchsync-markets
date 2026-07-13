"""Synchronization-error measures (paper Eqs. 4 and 9)."""
from __future__ import annotations

import numpy as np


def inter_layer_error(x: np.ndarray, N: int) -> float:
    """E^{12}(t) = (1/N) || L1(t) - L2(t) ||  (Eq. 4). x is the full 4N state."""
    L1 = x[: 2 * N]
    L2 = x[2 * N :]
    return float(np.linalg.norm(L1 - L2) / N)


def pair_error(x: np.ndarray, N: int, j: int) -> float:
    """E_j = sqrt((u1j-u2j)^2 + (v1j-v2j)^2), distance between mirror node j."""
    u1, v1 = x[2 * j], x[2 * j + 1]
    u2, v2 = x[2 * N + 2 * j], x[2 * N + 2 * j + 1]
    return float(np.hypot(u1 - u2, v1 - v2))


def time_averaged_error(err_ts: np.ndarray, t0_frac: float = 0.5) -> float:
    """Mean of E^{12}(t) over the last (1 - t0_frac) of the series (Eq. 9 spirit:
    discard transient, average the tail)."""
    n = len(err_ts)
    start = int(t0_frac * n)
    return float(np.mean(err_ts[start:]))


def synchronized(err_ts: np.ndarray, threshold: float, tail_frac: float = 0.25) -> bool:
    """Declare inter-layer synchronization if the tail-mean error is below
    threshold (default tail = last 25% of the run)."""
    n = len(err_ts)
    start = int((1 - tail_frac) * n)
    return bool(np.mean(err_ts[start:]) < threshold)


def time_to_sync(err_ts: np.ndarray, dt: float, subsample: int, threshold: float,
                 hold_steps: int = 50) -> float | None:
    """First time E^{12} drops below threshold and stays below for `hold_steps`
    recorded samples. Returns None if never achieved."""
    n = len(err_ts)
    below = err_ts < threshold
    for i in range(n - hold_steps):
        if below[i] and np.all(below[i : i + hold_steps]):
            return i * subsample * dt
    return None
