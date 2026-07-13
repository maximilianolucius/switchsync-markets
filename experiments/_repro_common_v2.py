"""Shared FHN reproduction helper for G0A/G0B (v2). Imports only library modules
(never the superseded v1 runners)."""
from __future__ import annotations

import numpy as np

from src.dynamics.fhn import FHNParams
from src.metrics.sync import synchronized, time_averaged_error
from src.networks.switching import random_switching
from src.simulation.double_layer import SimConfig, initial_state, simulate


def frac_synced_grid(N, N_IL, sigma_inter, T_swt_grid, total_time, dt, record_every,
                     seeds, threshold, tail_frac):
    """For each T_swt: fraction of seeds that synchronize (tail E12 < threshold) and
    the mean tail E12. Deterministic given seeds."""
    p = FHNParams(N=N, sigma_inter=sigma_inter)
    cfg = SimConfig(dt=dt, total_time=total_time, record_every=record_every)
    rows = []
    for T_swt in T_swt_grid:
        dwell = int(round(T_swt / dt))
        n_epochs = int(np.ceil(total_time / T_swt)) + 2
        flags, tails = [], []
        for seed in seeds:
            x0 = initial_state(N, np.random.default_rng(1000 + seed))
            sched = random_switching(N, N_IL, dwell, n_epochs,
                                     np.random.default_rng(2000 + seed), f"T{T_swt}")
            res = simulate(p, sched, cfg, x0)
            flags.append(synchronized(res.e12, threshold, tail_frac))
            tails.append(time_averaged_error(res.e12, 1 - tail_frac))
        rows.append({"T_swt": float(T_swt), "frac_synced": float(np.mean(flags)),
                     "mean_tail_E12": float(np.mean(tails))})
    return rows
