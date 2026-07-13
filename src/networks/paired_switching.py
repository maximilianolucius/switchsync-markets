"""Paired rate-contrast schedules (v2 correction of audit defects D5, D6).

The v1 rate arms used different RNG draws and different horizons (242/252/300 for
a nominal 240). This module builds fast/intermediate/slow arms from ONE base
snapshot sequence per seed, by holding each base snapshot for a rate-dependent
dwell while keeping the horizon EXACT and the time-averaged coupling operator
IDENTICAL across arms.

Construction. Fix K base snapshots s_0..s_{K-1} (each a set of N_IL active pairs).
An arm with `cycles = m` repeats the base sequence m times, holding each snapshot
for `dwell = H // (K*m)` steps. Requirement: K*m must divide H exactly (asserted,
no silent +1). Then:
  * every arm has total_steps == H exactly;
  * every base snapshot occupies H/K steps in EVERY arm (m occurrences x H/(K*m)),
    so the per-pair total active time -- hence the time-averaged coupling operator
    and the per-pair occupancy -- is identical across arms;
  * only the switching RATE (and within-horizon order granularity) differs.
This isolates rate from the average operator, density, strength and horizon.
"""
from __future__ import annotations

import numpy as np

from src.networks.switching import Epoch, Schedule


def build_base_snapshots(N: int, N_IL: int, K: int,
                         rng: np.random.Generator) -> tuple[tuple[int, ...], ...]:
    """K base snapshots, each N_IL distinct active mirror pairs. Frozen per seed."""
    return tuple(tuple(sorted(rng.choice(N, size=N_IL, replace=False).tolist()))
                 for _ in range(K))


def paired_rate_schedule(base: tuple[tuple[int, ...], ...], N: int, N_IL: int,
                         cycles: int, H: int, label: str) -> Schedule:
    """Build a rate arm: repeat `base` `cycles` times, dwell = H // (K*cycles).

    Raises if K*cycles does not divide H exactly (no silent trimming/rounding)."""
    K = len(base)
    denom = K * cycles
    if H % denom != 0:
        raise ValueError(
            f"K*cycles={denom} must divide H={H} exactly (got remainder {H % denom}); "
            "choose H, K, cycles so dwell is integral and the horizon is exact.")
    dwell = H // denom
    epochs = []
    for _ in range(cycles):
        for snap in base:
            epochs.append(Epoch(dwell, snap))
    sched = Schedule(N, N_IL, tuple(epochs), label)
    assert sched.total_steps == H, "internal: horizon not exact"
    return sched


def average_operator_gamma(base: tuple[tuple[int, ...], ...], N: int) -> np.ndarray:
    """Per-pair time-average coupling weight = (#snapshots containing pair)/K.
    Identical for every paired arm derived from `base` (that is the point)."""
    K = len(base)
    occ = np.zeros(N)
    for snap in base:
        for j in snap:
            occ[j] += 1.0
    return occ / K


def invariants(sched: Schedule, N: int) -> dict:
    """Report the invariants that a paired rate contrast must preserve."""
    per_step_density = []
    total_by_pair = np.zeros(N)
    for e in sched.epochs:
        per_step_density.append(len(e.active_pairs))
        for j in e.active_pairs:
            total_by_pair[j] += e.dwell_steps
    return {
        "total_steps": sched.total_steps,
        "n_epochs": len(sched.epochs),
        "instantaneous_density_constant": len(set(per_step_density)) == 1,
        "instantaneous_density": per_step_density[0] if per_step_density else 0,
        "occupancy_by_pair": (total_by_pair / max(sched.total_steps, 1)).tolist(),
    }


def assert_paired_invariants(arms: dict[str, Schedule], N: int,
                             H: int, N_IL: int) -> None:
    """Assert every arm shares horizon, density, and the time-averaged operator."""
    ref_occ = None
    for name, sched in arms.items():
        inv = invariants(sched, N)
        assert inv["total_steps"] == H, f"{name}: horizon {inv['total_steps']} != {H}"
        assert inv["instantaneous_density"] == N_IL, f"{name}: density != {N_IL}"
        assert inv["instantaneous_density_constant"], f"{name}: density not constant"
        occ = np.array(inv["occupancy_by_pair"])
        if ref_occ is None:
            ref_occ = occ
        else:
            assert np.allclose(occ, ref_occ, atol=1e-12), \
                f"{name}: occupancy (=> average operator) differs across arms"


def order_permutations(sched: Schedule, n_perm: int,
                       rng: np.random.Generator) -> list[Schedule]:
    """`n_perm` schedules that permute the epoch ORDER of `sched` (same multiset,
    dwell, horizon and occupancy). Each permutation uses an independent draw from
    the supplied generator, so the collection is a frozen, order-invariant null for
    the G2 permutation test. A permutation equal to the identity is allowed (it is
    a valid member of the permutation group)."""
    epochs = list(sched.epochs)
    out = []
    for _ in range(n_perm):
        perm = rng.permutation(len(epochs))
        out.append(Schedule(sched.N, sched.N_IL, tuple(epochs[i] for i in perm),
                            f"orderperm[{sched.label}]"))
    return out


def variable_dwell_schedule(base: tuple[tuple[int, ...], ...], N: int, N_IL: int,
                            dwell_multiset: tuple[int, ...], label: str) -> Schedule:
    """Schedule with a genuinely NON-constant, frozen dwell distribution, so that
    shuffling the dwells (src.networks.switching.shuffle_dwell) is a real null
    (fixes audit D6). len(dwell_multiset) must equal len(base)."""
    if len(dwell_multiset) != len(base):
        raise ValueError("dwell_multiset must have one dwell per base snapshot")
    if len(set(dwell_multiset)) == 1:
        raise ValueError("dwell_multiset must be non-constant for a meaningful null")
    epochs = [Epoch(d, snap) for d, snap in zip(dwell_multiset, base)]
    return Schedule(N, N_IL, tuple(epochs), label)
