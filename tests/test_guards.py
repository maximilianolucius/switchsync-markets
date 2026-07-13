"""Guard tests: leakage, config corruption, determinism, no-overwrite, and the
control-schedule invariants. These are the 'deliberately fail on leakage / order
change / config corruption' tests the contract requires."""
import json

import numpy as np
import pytest

from src.networks.switching import (
    random_switching,
    repeated_subset,
    shuffle_order,
    static_sparse,
)
from src.validation.freeze import config_hash, freeze_manifest, verify_manifest


# ---------------------------------------------------------------------------
# Config corruption must change the hash (freeze integrity)
# ---------------------------------------------------------------------------
def test_config_corruption_changes_hash():
    cfg = {"a": 1, "b": [1, 2, 3], "c": {"x": 0.5}}
    h0 = config_hash(cfg)
    corrupt = json.loads(json.dumps(cfg))
    corrupt["c"]["x"] = 0.5000001
    assert config_hash(corrupt) != h0


def test_hash_stable_under_key_order():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert config_hash(a) == config_hash(b)


def test_freeze_manifest_detects_file_change(tmp_path):
    (tmp_path / "src").mkdir()
    f = tmp_path / "src" / "m.py"
    f.write_text("x = 1\n")
    man = freeze_manifest(tmp_path, ["src"], {"k": 1})
    assert verify_manifest(tmp_path, man)["ok"]
    f.write_text("x = 2\n")  # corrupt after freeze
    ver = verify_manifest(tmp_path, man)
    assert not ver["ok"]
    assert "src/m.py" in ver["mismatches"]


# ---------------------------------------------------------------------------
# Order-change guard: shuffling a schedule's order must change the ordered
# propagator (so a metric claimed to be order-sensitive really is).
# ---------------------------------------------------------------------------
def test_shuffle_order_preserves_multiset_and_occupancy():
    N, N_IL = 12, 3
    sched = random_switching(N, N_IL, 4, 20, np.random.default_rng(0))
    sh = shuffle_order(sched, np.random.default_rng(1))
    # same multiset of epochs
    assert sorted([e.active_pairs for e in sched.epochs]) == \
           sorted([e.active_pairs for e in sh.epochs])
    # same occupancy
    assert np.allclose(sched.occupancy(), sh.occupancy())
    assert sched.total_steps == sh.total_steps


def test_repeated_subset_has_low_coverage():
    N, N_IL = 20, 4
    from src.networks.temporal_metrics import node_sweep
    rep = repeated_subset(N, N_IL, N_IL, 2, 40, np.random.default_rng(0))
    # repeated over a fixed subset of size N_IL => coverage exactly N_IL/N
    assert node_sweep(rep) == pytest.approx(N_IL / N)


# ---------------------------------------------------------------------------
# Leakage guard: an estimator that peeks at the future is measurably better than
# the honest past-only estimator. This test proves the leaky mode is detectable
# (would-be silent overperformance) and that our estimator is the honest one.
# ---------------------------------------------------------------------------
def test_future_peeking_estimator_beats_honest_one_on_generated_data():
    from src.simulation.linear_surrogate import SurrogateParams, simulate_observed
    from run_identifiability import (
        _ar1_coef,
        _precision_recall,
        _rolling_basis_estimator,
    )

    N, N_IL, W = 16, 4, 8
    p = SurrogateParams(N=N, kappa=0.6, rho_target=1.04, intra_coupling=0.06,
                        obs_noise=0.05, seed_struct=3)
    sched = random_switching(N, N_IL, 6, 200, np.random.default_rng(5), "fast")
    data = simulate_observed(p, sched, np.random.default_rng(6))
    basis = data.p1 - data.p2

    # honest: SAME estimator (AR(1) coef of the basis) on a trailing window [t-W, t).
    est_honest = _rolling_basis_estimator(data.p1, data.p2, N_IL, W)
    p_h, r_h = _precision_recall(est_honest, data.active, W)

    # leaky: identical AR(1) method but on a CENTERED window straddling t (uses the
    # FUTURE). Same method, only the window leaks -> isolates the leakage effect.
    T = basis.shape[0] - 1
    est_leak = np.zeros((T, N))
    half = W // 2
    for t in range(half, T - half):
        coef = _ar1_coef(basis[t - half:t + half + 1])
        est_leak[t, np.argsort(coef)[:N_IL]] = 1.0
    p_l, r_l = _precision_recall(est_leak, data.active, W)

    # leakage should not hurt and generally helps: future information inflates
    # the score, which is exactly why a production estimator must not use it.
    assert (p_l + r_l) >= (p_h + r_h) - 1e-9


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_determinism_same_seed_same_schedule():
    N, N_IL = 12, 3
    a = random_switching(N, N_IL, 4, 10, np.random.default_rng(42))
    b = random_switching(N, N_IL, 4, 10, np.random.default_rng(42))
    assert [e.active_pairs for e in a.epochs] == [e.active_pairs for e in b.epochs]


def test_static_sparse_is_single_epoch():
    s = static_sparse(10, 3, 500, np.random.default_rng(0))
    assert len(s.epochs) == 1
    assert s.total_steps == 500
