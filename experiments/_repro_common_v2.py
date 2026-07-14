"""Shared FHN reproduction helper for G0A/G0B (v2). Imports only library modules
(never the superseded v1 runners)."""
from __future__ import annotations

import numpy as np

from src.dynamics.fhn import FHNParams
from src.metrics.sync import synchronized, time_averaged_error
from src.networks.switching import random_switching
from src.simulation.double_layer import SimConfig, initial_state, simulate
from _contract_v2 import failure_record


def frac_synced_grid(N, N_IL, sigma_inter, T_swt_grid, total_time, dt, record_every,
                     seeds, threshold, tail_frac):
    """For each T_swt: fraction of seeds that synchronize (tail E12 < threshold) and
    the mean tail E12. Deterministic given seeds."""
    p = FHNParams(N=N, sigma_inter=sigma_inter)
    cfg = SimConfig(dt=dt, total_time=total_time, record_every=record_every)
    rows = []
    for T_swt in T_swt_grid:
        flags, tails, failed, fail_records = [], [], [], []
        for seed in seeds:
            # Contract H: cell-dependent params, initial-state and schedule
            # construction ALL inside the per-seed try, so a construction error
            # becomes a full failure record rather than escaping. KeyboardInterrupt /
            # SystemExit are BaseException and propagate as external interruptions;
            # only ordinary Exceptions/nonfinite are captured.
            try:
                dwell = int(round(T_swt / dt))
                n_epochs = int(np.ceil(total_time / T_swt)) + 2
                x0 = initial_state(N, np.random.default_rng(1000 + seed))
                sched = random_switching(N, N_IL, dwell, n_epochs,
                                         np.random.default_rng(2000 + seed), f"T{T_swt}")
                res = simulate(p, sched, cfg, x0)
                if not np.all(np.isfinite(res.e12)):
                    raise FloatingPointError("non-finite E12")
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                failed.append(int(seed))
                fail_records.append(failure_record(e, int(seed),
                                                   {"T_swt": float(T_swt)}))
                continue
            flags.append(synchronized(res.e12, threshold, tail_frac))
            tails.append(time_averaged_error(res.e12, 1 - tail_frac))
        n = len(seeds)
        rows.append({"T_swt": float(T_swt),
                     "frac_synced": float(np.mean(flags)) if flags else None,
                     "mean_tail_E12": float(np.mean(tails)) if tails else None,
                     "n_successful": len(flags),
                     "failed_seeds": failed, "failure_records": fail_records,
                     "frac_failed": len(failed) / n})
    return rows
