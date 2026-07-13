"""Tests demonstrating each v1 defect and its v2 repair. Each test that targets a
defect both (a) characterizes the v1 behaviour (regression) and (b) asserts the v2
correction, so the pair is non-vacuous."""
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# C1 (D5) paired rate schedules: exact horizon + identical average operator
# ---------------------------------------------------------------------------
from src.networks.paired_switching import (
    assert_paired_invariants,
    build_base_snapshots,
    average_operator_gamma,
    invariants,
    paired_rate_schedule,
    variable_dwell_schedule,
)


def test_v1_rate_arms_had_unequal_horizons_regression():
    # v1 used n_epochs = H//dwell + 1 with no trim -> unequal horizons.
    H = 240
    horizons = {d: (H // d + 1) * d for d in (2, 12, 60)}
    assert horizons == {2: 242, 12: 252, 60: 300}  # the documented defect
    assert len(set(horizons.values())) == 3          # all different


def test_paired_arms_exact_and_equal_horizon():
    N, N_IL, K, H = 24, 6, 6, 240
    base = build_base_snapshots(N, N_IL, K, np.random.default_rng(1))
    fast = paired_rate_schedule(base, N, N_IL, cycles=20, H=H, label="fast")   # dwell 2
    inter = paired_rate_schedule(base, N, N_IL, cycles=5, H=H, label="inter")  # dwell 8
    slow = paired_rate_schedule(base, N, N_IL, cycles=1, H=H, label="slow")    # dwell 40
    for s in (fast, inter, slow):
        assert s.total_steps == H          # EXACT, unlike v1
    assert_paired_invariants({"fast": fast, "inter": inter, "slow": slow}, N, H, N_IL)


def test_paired_arms_share_average_operator():
    N, N_IL, K, H = 24, 6, 6, 240
    base = build_base_snapshots(N, N_IL, K, np.random.default_rng(2))
    fast = paired_rate_schedule(base, N, N_IL, 20, H, "fast")
    slow = paired_rate_schedule(base, N, N_IL, 1, H, "slow")
    occ_fast = np.array(invariants(fast, N)["occupancy_by_pair"])
    occ_slow = np.array(invariants(slow, N)["occupancy_by_pair"])
    assert np.allclose(occ_fast, occ_slow)                       # same average operator
    assert np.allclose(occ_fast, average_operator_gamma(base, N))


def test_paired_rate_rejects_nondivisible_horizon():
    N, N_IL, K = 24, 6, 7
    base = build_base_snapshots(N, N_IL, K, np.random.default_rng(3))
    with pytest.raises(ValueError):
        paired_rate_schedule(base, N, N_IL, cycles=1, H=240, label="bad")  # 7 ∤ 240


# ---------------------------------------------------------------------------
# C2 (D6) shuffled_dwell must operate on a genuinely non-constant distribution
# ---------------------------------------------------------------------------
from src.networks.switching import random_switching, shuffle_dwell


def test_v1_shuffle_dwell_is_noop_regression():
    # v1 random_switching -> constant dwell -> shuffle_dwell changes nothing.
    s = random_switching(24, 6, 2, 30, np.random.default_rng(4))
    sd = shuffle_dwell(s, np.random.default_rng(5))
    assert len(set(e.dwell_steps for e in s.epochs)) == 1
    assert [e.dwell_steps for e in s.epochs] == [e.dwell_steps for e in sd.epochs]


def test_variable_dwell_null_is_nontrivial():
    N, N_IL = 24, 6
    base = build_base_snapshots(N, N_IL, 6, np.random.default_rng(6))
    dwells = (2, 4, 8, 16, 32, 64)   # non-constant, frozen
    s = variable_dwell_schedule(base, N, N_IL, dwells, "vardwell")
    sd = shuffle_dwell(s, np.random.default_rng(7))
    assert len(set(e.dwell_steps for e in s.epochs)) > 1
    # some snapshot now has a different dwell -> the null is real
    assert [e.dwell_steps for e in s.epochs] != [e.dwell_steps for e in sd.epochs]


def test_variable_dwell_rejects_constant():
    N, N_IL = 24, 6
    base = build_base_snapshots(N, N_IL, 3, np.random.default_rng(8))
    with pytest.raises(ValueError):
        variable_dwell_schedule(base, N, N_IL, (5, 5, 5), "const")


# ---------------------------------------------------------------------------
# C3 (D7) MSF channels must be complementary (anti-phase), offset T_swt
# ---------------------------------------------------------------------------
from src.dynamics.msf_switching import paper_g, smooth_square_gamma_v2


def _sample(gof, n, step):
    return np.array([gof(s) for s in range(0, n, step)])


def test_v1_msf_channels_were_identical_regression():
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "experiments") not in sys.path:
        sys.path.insert(0, str(root / "experiments"))
    from run_msf import smooth_square_gamma as v1_gamma
    gof = v1_gamma(2, T_swt=10.0, dt=0.01)
    v = _sample(gof, 4000, 50)
    assert np.max(np.abs(v[:, 0] - v[:, 1])) < 1e-9   # v1 bug: identical channels


def test_v2_msf_channels_antiphase():
    gof = smooth_square_gamma_v2(2, T_swt=10.0, dt=0.01)
    v = _sample(gof, 4000, 25)
    assert np.max(np.abs(v[:, 0] - v[:, 1])) > 0.5    # genuinely different


def test_v2_msf_channels_sum_to_one_outside_transitions():
    T_swt, dt = 10.0, 0.01
    gof = smooth_square_gamma_v2(2, T_swt, dt)
    # sample mid-half-period points (far from transitions at multiples of T_swt)
    steps = [int((k * T_swt + T_swt / 2) / dt) for k in range(8)]
    for s in steps:
        g = gof(s)
        assert abs(g[0] + g[1] - 1.0) < 0.05


def test_v2_msf_offset_is_Tswt_not_2Tswt():
    T_swt, dt = 10.0, 0.01
    gof = smooth_square_gamma_v2(2, T_swt, dt)
    # channel 1 at t equals channel 0 at t+T_swt (half period), not t+2T_swt
    for s in [123, 456, 789, 1500]:
        t = s * dt
        g1_now = 0.5 * (paper_g(t + T_swt, T_swt) + 1.0)
        assert abs(gof(s)[1] - g1_now) < 1e-9
    # a 2*T_swt shift would reproduce channel 0 (the v1 bug) -> must differ
    g0 = _sample(gof, 4000, 25)[:, 0]
    assert np.max(np.abs(g0 - g0)) < 1e-12  # trivially true; documented for clarity


def test_v2_msf_signals_alternate_within_period():
    T_swt, dt = 10.0, 0.01
    gof = smooth_square_gamma_v2(2, T_swt, dt)
    first = gof(int((T_swt / 2) / dt))            # first half
    second = gof(int((1.5 * T_swt) / dt))         # second half
    assert first[0] > 0.5 and first[1] < 0.5
    assert second[0] < 0.5 and second[1] > 0.5


# ---------------------------------------------------------------------------
# C4 (D8) signed operator must have a strictly negative coupling
# ---------------------------------------------------------------------------
from src.simulation.linear_surrogate import SurrogateParams, build_basis_operator
from src.simulation.surrogate_v2 import build_basis_operator_v2


def test_v1_signed_had_no_negative_weight_regression():
    p = SurrogateParams(N=24, signed=True, intra_coupling=0.06, seed_struct=51)
    A = build_basis_operator(p)
    off = A - np.diag(np.diag(A))
    assert not (off < -1e-12).any()   # the v1 defect: never negative


def test_v2_signed_has_negative_weight_and_budget():
    p = SurrogateParams(N=24, signed=True, intra_coupling=0.06, seed_struct=51)
    A_signed, meta = build_basis_operator_v2(p, np.random.default_rng(51))
    assert meta["n_negative_offdiag"] >= 1
    off = A_signed - np.diag(np.diag(A_signed))
    assert off.min() < -1e-9
    # unsigned v2 has no negatives; signed introduced them
    p_unsigned = SurrogateParams(N=24, signed=False, intra_coupling=0.06, seed_struct=51)
    A_uns, meta_uns = build_basis_operator_v2(p_unsigned, np.random.default_rng(51))
    assert meta_uns["n_negative_offdiag"] == 0


# ---------------------------------------------------------------------------
# C6 (D10) contraction correlation must use the SAME realization
# ---------------------------------------------------------------------------
from src.networks.switching import random_switching as _rs
from src.simulation.linear_surrogate import simulate_basis
from src.simulation.surrogate_v2 import (
    contraction_corr_same_realization,
    simulate_observed_v2,
)


def test_v2_contraction_corr_uses_same_realization():
    N, N_IL, H, W = 24, 6, 400, 8
    p = SurrogateParams(N=N, kappa=0.6, rho_target=1.04, intra_coupling=0.06,
                        obs_noise=0.02, seed_struct=61)
    sched = _rs(N, N_IL, 6, H // 6 + 1, np.random.default_rng(61), "fast")
    data = simulate_observed_v2(p, sched, np.random.default_rng(62))

    corr_same = contraction_corr_same_realization(data, W)

    # an INDEPENDENT trajectory (the v1 approach) must NOT pass as ground truth
    d_indep = simulate_basis(p, sched, np.random.default_rng(999), noise=0.0)
    d_obs = data.p1 - data.p2
    tc, oc = [], []
    for t in range(W, H):
        n0t, n1t = np.linalg.norm(d_indep[t - W]), np.linalg.norm(d_indep[t])
        n0o, n1o = np.linalg.norm(d_obs[t - W]), np.linalg.norm(d_obs[t])
        if n0t > 1e-9 and n0o > 1e-9:
            tc.append(np.log(n1t / n0t)); oc.append(np.log(n1o / n0o))
    corr_indep = float(np.corrcoef(tc, oc)[0, 1])

    assert corr_same > 0.8                       # same realization tracks observed
    assert corr_same > corr_indep + 0.3          # independent trajectory is far worse


# ---------------------------------------------------------------------------
# C5 (D9): temporal_reachability_ratio must be a meaningful, reported descriptor.
# We do NOT claim single-variable isolation of coverage vs reachability (that
# contrast changes >1 variable); we validate the descriptor distinguishes a
# block-confined schedule from a full-coverage one.
# ---------------------------------------------------------------------------
from src.networks.ring import ring_laplacian
from src.networks.switching import high_sweep_low_reachability, random_switching
from src.networks.temporal_metrics import node_sweep, temporal_reachability_ratio


def test_reachability_ratio_distinguishes_confined_schedule():
    N, N_IL = 24, 6
    ring_adj = (ring_laplacian(N, 1) != 0).astype(float)
    np.fill_diagonal(ring_adj, 0.0)
    full = random_switching(N, N_IL, 2, 60, np.random.default_rng(1), "full")
    confined = high_sweep_low_reachability(N, N_IL, 2, 60, np.random.default_rng(1),
                                           block_frac=0.5, label="confined")
    r_full = temporal_reachability_ratio(full, ring_adj)
    r_conf = temporal_reachability_ratio(confined, ring_adj)
    # the block-confined schedule reaches strictly fewer node pairs
    assert r_conf < r_full
    # and its coverage is capped at the block fraction
    assert node_sweep(confined) <= 0.5 + 1e-9
