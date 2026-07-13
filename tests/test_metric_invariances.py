"""Deliberate demonstrations (temporal_stability_metrics.md sec.1):

1. G_switch (aggregation_connectivity_gap) is INVARIANT under time-dilation and
   under temporal reordering -> it cannot be the switching mechanism.
2. The order-sensitive propagator gamma is NOT invariant -> it is order-sensitive.

If a future refactor made G_switch order/rate sensitive, or made gamma
order-blind, these tests would fail, which is the point.
"""
import numpy as np

from src.metrics.baselines import (
    aggregation_connectivity_gap,
    dilate_sequence,
)
from src.metrics.propagator import (
    full_contraction_rate,
    ordered_product,
    transverse_contraction_rate,
)


def _random_laplacians(n, k, seed):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(k):
        A = rng.random((n, n))
        A = np.triu(A, 1)
        A = A + A.T
        L = np.diag(A.sum(1)) - A
        out.append(L)
    return out


def test_gswitch_invariant_under_time_dilation():
    Ls = _random_laplacians(6, 5, seed=1)
    g0 = aggregation_connectivity_gap(Ls)
    g_dilated = aggregation_connectivity_gap(dilate_sequence(Ls, 7))
    assert abs(g0 - g_dilated) < 1e-9  # rate-blind


def test_gswitch_invariant_under_reordering():
    Ls = _random_laplacians(6, 5, seed=2)
    g0 = aggregation_connectivity_gap(Ls)
    perm = [3, 0, 4, 1, 2]
    g_perm = aggregation_connectivity_gap([Ls[i] for i in perm])
    assert abs(g0 - g_perm) < 1e-9  # order-blind


def test_ordered_propagator_is_order_sensitive():
    # Laplacian maps preserve the all-ones (consensus) direction, so the TRANSVERSE
    # contraction rate (which projects that direction off) is the meaningful,
    # order-sensitive quantity. Non-commuting maps => order changes it.
    Ls = _random_laplacians(6, 5, seed=3)
    maps = [np.eye(6) - 0.1 * L for L in Ls]
    perm = [3, 0, 4, 1, 2]
    maps_perm = [maps[i] for i in perm]
    g0 = transverse_contraction_rate(ordered_product(maps), len(maps))
    gp = transverse_contraction_rate(ordered_product(maps_perm), len(maps_perm))
    assert abs(g0 - gp) > 1e-6


def test_ordered_propagator_rate_sensitive_when_generators_noncommuting():
    # Dilating (holding each map longer) changes the continuous contraction only
    # through the product length; the per-map contraction accumulates differently
    # than the average. Here we verify dilation changes the *factor* (not the
    # normalized rate necessarily), i.e. gamma is not trivially invariant.
    Ls = _random_laplacians(6, 4, seed=4)
    maps = [np.eye(6) - 0.15 * L for L in Ls]
    from src.metrics.baselines import dilate_sequence as dil
    maps_dil = dil(maps, 3)
    f0 = ordered_product(maps)
    f1 = ordered_product(maps_dil)
    assert not np.allclose(f0, f1)
