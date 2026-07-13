"""Mandatory baseline metrics, including the `aggregation_connectivity_gap`
(the paper-adjacent G_switch we explicitly DEMOTE to a descriptor).

See docs/methodology/temporal_stability_metrics.md sec.1 for why G_switch is not
the mechanism: it is invariant under time-dilation (rate-blind) and under
temporal reordering. `tests/test_metric_invariances.py` demonstrates both.
"""
from __future__ import annotations

import numpy as np


def _lambda2_psd(L: np.ndarray) -> float:
    """Second-smallest eigenvalue of the PSD graph Laplacian derived from L.
    Accepts either sign convention (negative-diagonal zero-row-sum, or PSD)."""
    Lpsd = -L if np.all(np.diag(L) <= 0) else L
    w = np.sort(np.linalg.eigvalsh(Lpsd))
    return float(w[1])


def snapshot_lambda2_mean(laplacians: list[np.ndarray]) -> float:
    return float(np.mean([_lambda2_psd(L) for L in laplacians]))


def average_graph_lambda2(laplacians: list[np.ndarray]) -> float:
    Lbar = np.mean(laplacians, axis=0)
    return _lambda2_psd(Lbar)


def aggregation_connectivity_gap(laplacians: list[np.ndarray]) -> float:
    """G_switch = lambda_2(avg Laplacian) - mean_t lambda_2(L_t).

    DESCRIPTOR ONLY. Rate-blind and order-blind (see the invariance tests). Never
    use as evidence of the dynamic switching mechanism.
    """
    return average_graph_lambda2(laplacians) - snapshot_lambda2_mean(laplacians)


def graph_density(gamma_sequence: np.ndarray) -> float:
    """Mean fraction of active pairs per step (instantaneous density)."""
    return float(np.mean(gamma_sequence))


def dilate_sequence(laplacians: list[np.ndarray], factor: int) -> list[np.ndarray]:
    """Hold each snapshot `factor` steps longer (time dilation). Preserves the
    snapshot multiset and average graph exactly."""
    out = []
    for L in laplacians:
        out.extend([L] * factor)
    return out
