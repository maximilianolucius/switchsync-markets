"""Switching schedules for inter-layer links, and the control/null variants.

A Schedule is a list of epochs; each epoch is (dwell_steps, active_pairs), where
active_pairs are 0-based mirror-pair indices active for that many integration
steps. All generators are deterministic given an explicit numpy Generator.

The controls implement the P1.2 design: variants that hold density, occupancy,
dwell distribution, or the multiset of snapshots fixed while changing exactly one
of {rate, order, coverage, reachability}.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Epoch:
    dwell_steps: int
    active_pairs: tuple[int, ...]


@dataclass(frozen=True)
class Schedule:
    N: int
    N_IL: int
    epochs: tuple[Epoch, ...]
    label: str = "schedule"

    @property
    def total_steps(self) -> int:
        return sum(e.dwell_steps for e in self.epochs)

    def gamma_at_step(self, step: int) -> np.ndarray:
        """0/1 gamma vector active at integration step `step` (clamped)."""
        acc = 0
        for e in self.epochs:
            if step < acc + e.dwell_steps:
                g = np.zeros(self.N)
                if e.active_pairs:
                    g[list(e.active_pairs)] = 1.0
                return g
            acc += e.dwell_steps
        # past the end: hold the last epoch
        e = self.epochs[-1]
        g = np.zeros(self.N)
        if e.active_pairs:
            g[list(e.active_pairs)] = 1.0
        return g

    def occupancy(self) -> np.ndarray:
        """Fraction of horizon each mirror pair is active (length N)."""
        occ = np.zeros(self.N)
        for e in self.epochs:
            if e.active_pairs:
                occ[list(e.active_pairs)] += e.dwell_steps
        return occ / max(self.total_steps, 1)


def random_switching(N: int, N_IL: int, dwell_steps: int, n_epochs: int,
                     rng: np.random.Generator, label: str = "random_switching") -> Schedule:
    """Base mechanism: every `dwell_steps`, draw a fresh random set of N_IL pairs."""
    epochs = []
    for _ in range(n_epochs):
        pairs = tuple(sorted(rng.choice(N, size=N_IL, replace=False).tolist()))
        epochs.append(Epoch(dwell_steps, pairs))
    return Schedule(N, N_IL, tuple(epochs), label)


def static_sparse(N: int, N_IL: int, total_steps: int, rng: np.random.Generator,
                  label: str = "static_sparse") -> Schedule:
    """One randomly chosen sparse set, held for the whole horizon (no switching)."""
    pairs = tuple(sorted(rng.choice(N, size=N_IL, replace=False).tolist()))
    return Schedule(N, N_IL, (Epoch(total_steps, pairs),), label)


def shuffle_order(sched: Schedule, rng: np.random.Generator,
                  label: str | None = None) -> Schedule:
    """Same multiset of (dwell, active_pairs) epochs, permuted temporal order.

    Isolates *order* (Gate G2): occupancy, dwell distribution, snapshot multiset,
    and switching rate are all preserved; only the sequence changes.
    """
    perm = rng.permutation(len(sched.epochs))
    epochs = tuple(sched.epochs[i] for i in perm)
    return Schedule(sched.N, sched.N_IL, epochs,
                    label or f"shuffled_order[{sched.label}]")


def shuffle_dwell(sched: Schedule, rng: np.random.Generator,
                  label: str | None = None) -> Schedule:
    """Same active sets in the same order, but dwell durations permuted across
    epochs. Preserves the snapshot multiset and total occupancy-by-count but
    changes which snapshot gets which duration (occupancy weights change)."""
    dwells = [e.dwell_steps for e in sched.epochs]
    perm = rng.permutation(len(dwells))
    epochs = tuple(Epoch(dwells[perm[i]], e.active_pairs)
                   for i, e in enumerate(sched.epochs))
    return Schedule(sched.N, sched.N_IL, epochs,
                    label or f"shuffled_dwell[{sched.label}]")


def repeated_subset(N: int, N_IL: int, subset_size: int, dwell_steps: int,
                    n_epochs: int, rng: np.random.Generator,
                    label: str = "repeated_subset") -> Schedule:
    """Switch quickly but only ever among a fixed small subset of mirror pairs.

    High switching rate, LOW coverage: isolates coverage (a fast switcher that
    never visits most pairs). subset_size >= N_IL required.
    """
    if subset_size < N_IL:
        raise ValueError("subset_size must be >= N_IL")
    subset = rng.choice(N, size=subset_size, replace=False)
    epochs = []
    for _ in range(n_epochs):
        pairs = tuple(sorted(rng.choice(subset, size=N_IL, replace=False).tolist()))
        epochs.append(Epoch(dwell_steps, pairs))
    return Schedule(N, N_IL, tuple(epochs), label)


def high_sweep_low_reachability(N: int, N_IL: int, dwell_steps: int, n_epochs: int,
                                rng: np.random.Generator,
                                block_frac: float = 0.5,
                                label: str = "high_sweep_low_reach") -> Schedule:
    """Cover MANY pairs over time but confine links within a fixed node block so
    the temporal reachability graph never bridges the two blocks (see
    temporal_stability_metrics.md sec.2). High node sweep, broken reachability.
    """
    n_block = int(round(block_frac * N))
    block_a = np.arange(0, n_block)
    if n_block < N_IL:
        raise ValueError("block too small for N_IL")
    epochs = []
    for _ in range(n_epochs):
        pairs = tuple(sorted(rng.choice(block_a, size=N_IL, replace=False).tolist()))
        epochs.append(Epoch(dwell_steps, pairs))
    return Schedule(N, N_IL, tuple(epochs), label)
