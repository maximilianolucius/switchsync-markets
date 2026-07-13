"""Corrected minimal-system MSF switching drive (v2 fix of audit defect D7).

v1 drove the two mirror channels with g(t) and g(t + p_period) where
p_period = 2*T_swt. Since the paper's g has period p_period, g(t+p_period) = g(t):
both channels were identical (same phase), so the minimal system was never
switched. The fix shifts the second channel by HALF a period, T_swt, giving a
genuinely complementary (anti-phase) drive: while one mirror link is on, the
other is off, which is the minimal analogue of switching a single link between
two pairs.

Definitions (faithful to the paper's g, alpha=5):
    p        = 2 * T_swt                      (full period)
    g(t)     = tanh(a(t - n p)) - tanh(a(t - (n+0.5)p)) - 1,   n = floor(t/p)
    gamma_0  = 0.5 (g(t) + 1)                 (on in the first half-period)
    gamma_1  = 0.5 (g(t + T_swt) + 1)         (half-period shift => anti-phase)
Outside the smooth transitions, gamma_0 + gamma_1 ~= 1 (exactly one link on).
"""
from __future__ import annotations

import numpy as np


def paper_g(t: float, T_swt: float, alpha: float = 5.0) -> float:
    p = 2.0 * T_swt
    n = np.floor(t / p)
    return (np.tanh(alpha * (t - n * p))
            - np.tanh(alpha * (t - (n + 0.5) * p)) - 1.0)


def smooth_square_gamma_v2(N: int, T_swt: float, dt: float, alpha: float = 5.0):
    """Return gamma_of_step(step) -> length-N vector. Only pairs 0 and 1 carry the
    (anti-phase) inter-layer channels; the rest are zero (minimal N=2 system)."""
    half_period = T_swt  # = p/2

    def gamma_of_step(step: int) -> np.ndarray:
        t = step * dt
        gv = np.zeros(N)
        gv[0] = 0.5 * (paper_g(t, T_swt, alpha) + 1.0)
        gv[1] = 0.5 * (paper_g(t + half_period, T_swt, alpha) + 1.0)
        return gv

    return gamma_of_step
