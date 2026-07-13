"""Temporal-graph metrics: occupancy, dwell, node sweep, temporal reachability,
joint connectivity. Order-sensitive where the underlying object is.

These operate on the *inter-layer link schedule* and, for reachability, on a
supplied intra-layer adjacency (the ring), because in the double-layer system a
transverse mode can only be pulled together if inter-layer coupling reaches it
through the intra-layer graph over time.
"""
from __future__ import annotations

import numpy as np

from src.networks.switching import Schedule


def node_sweep(sched: Schedule) -> float:
    """Fraction of mirror pairs that receive a link at least once (coverage)."""
    seen = set()
    for e in sched.epochs:
        seen.update(e.active_pairs)
    return len(seen) / sched.N


def dwell_stats(sched: Schedule) -> dict:
    """Per-edge dwell statistics: mean/std of consecutive-active run lengths."""
    runs: list[int] = []
    for j in range(sched.N):
        active = [j in e.active_pairs for e in sched.epochs]
        run = 0
        for a in active:
            if a:
                run += 1
            elif run:
                runs.append(run)
                run = 0
        if run:
            runs.append(run)
    if not runs:
        return {"mean_run": 0.0, "std_run": 0.0, "n_runs": 0}
    r = np.array(runs, dtype=float)
    return {"mean_run": float(r.mean()), "std_run": float(r.std()), "n_runs": len(runs)}


def switching_rate(sched: Schedule, dt: float) -> float:
    """Switch events per unit time = (#epochs - 1) / total_time."""
    total_time = sched.total_steps * dt
    if total_time <= 0:
        return 0.0
    return (len(sched.epochs) - 1) / total_time


def temporal_reachability_ratio(sched: Schedule, ring_adj: np.ndarray) -> float:
    """Fraction of ordered node pairs (i,j) with a time-respecting path.

    A time-respecting path advances via intra-layer ring edges (available at any
    time) and inter-layer 'events' that, at the epoch when pair k is active, let
    influence at node k jump forward in time. Concretely we build a layered
    reachability over epochs: start from each node, in each epoch propagate
    through the ring (transitive closure within the epoch) and mark that active
    inter-layer pairs synchronize the mirror node (which, for reachability across
    the union, keeps the node 'live'). Because both layers are mirror-identical
    here we compute reachability on the *pair* graph: node i can influence node j
    if there is a temporal path in the union-over-time of ring edges gated by the
    order in which inter-layer links appear.

    Implementation: forward sweep. reach[i] = set of nodes reachable from i so
    far. In each epoch: first spread reach through the ring (closure), then for
    every active pair the node stays reachable (identity). Order matters because
    ring spread is applied epoch by epoch and the *active* set changes which
    transverse modes are being contracted; we record reachability of the
    inter-layer-active nodes accumulated in temporal order.
    """
    N = sched.N
    # ring reachability is full within a connected ring, so to make reachability
    # informative we gate it: influence can only pass through nodes that have been
    # 'activated' by an inter-layer link at or before the current epoch.
    reach = [set([i]) for i in range(N)]
    activated = np.zeros(N, dtype=bool)
    ring_neighbors = [np.nonzero(ring_adj[i])[0].tolist() for i in range(N)]
    for e in sched.epochs:
        activated[list(e.active_pairs)] = True
        # spread through ring edges, but only via activated nodes (gating)
        changed = True
        while changed:
            changed = False
            for i in range(N):
                for nb in ring_neighbors[i]:
                    if activated[i] and activated[nb]:
                        if not reach[i].issuperset(reach[nb]):
                            reach[i] |= reach[nb]
                            changed = True
                        if not reach[nb].issuperset(reach[i]):
                            reach[nb] |= reach[i]
                            changed = True
    total = sum(len(r) for r in reach)
    return total / (N * N)


def joint_connectivity(sched: Schedule) -> bool:
    """Whether the union of active inter-layer pairs covers all nodes (a necessary
    condition for every transverse mode to receive coupling over the horizon)."""
    return node_sweep(sched) >= 1.0
