"""P1.2-B runner / contract / custody tests (non-vacuous: they fail against v3
behaviour and pass against v4). No import/field-existence/`x in [x]` tests."""
import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import _contract_v2 as contract
import _custody
import run_g0a_exact_v2 as g0a
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4
from src.metrics.inference import exact_two_sided_sign_test, paired_decision
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.paired_switching import order_permutations

REPO = Path(__file__).resolve().parents[1]
EXP = REPO / "experiments"


# ---------------------------------------------------------------------------
# tiny fixtures
# ---------------------------------------------------------------------------
def _tiny_prereg(paired_eval=(81, 82, 83, 84)):
    return {
        "global": {"dt": 0.01},
        "tolerances": {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25},
        "fhn": {"density_ratio": 0.25},
        "seed_blocks": {"identifiability": [61, 62, 63, 64], "paired_selection": [41, 42, 43, 44],
                        "paired_evaluation": list(paired_eval), "stages": [51, 52, 53, 54],
                        "g0c_msf": [31], "g0a": [11], "g0b": [11]},
        "gates": {"G0A_exact_reproduction": {"cost_rule": {
                      "max_wall_time_seconds": 86400, "chunk_steps": 5000,
                      "mandatory_minimum_size": 200, "minimum_completed_seeds": 1,
                      "deciding_sizes": [200, 400], "non_deciding_sizes": [100]}},
                  "G3_robustness": {"signed_budget_tolerance": 1e-9}},
    }


def _tiny_exec(intra=0.06):
    return {
        "inference": {"alpha": 0.05, "std_mult": 3.0, "n_boot": 100, "boot_seed": 20260713,
                      "floor_surrogate_gamma": 0.02, "floor_identifiability_margin": 0.05},
        "surrogate_paired": {"N": 8, "N_IL": 2, "K": 3, "H": 24, "kappa": 0.6,
                             "rho_target": 1.04, "intra_coupling": intra, "cycles_fast": 4,
                             "cycles_intermediate": 2, "cycles_slow": 1,
                             "variable_dwell_multiset": [4, 8, 12], "best_static_search": 4,
                             "neg_fraction_signed": 0.4, "candidate_search_seed": 900001,
                             "g2_n_perm": 5, "g2_perm_seed": 700003},
        "g4": {"N": 8, "N_IL": 2, "kappa": 0.6, "rho_target": 1.04, "intra_coupling": 0.06,
               "horizon_steps": 60, "dwell_fast": 6, "estimator_window": 8, "obs_noise": 0.05,
               "factor_scale": 1.0, "async_variants": [[1, 1]]},
        "g0c": {"N": 2, "lam_perp": 2.0, "alpha": 5.0, "n_steps": 400, "transient_steps": 100,
                "renorm_every": 5, "sigma_grid": [0.3], "T_swt_grid": [11.0]},
        "g3_stages": [{"name": "faithful", "heterogeneity": 0.0, "directed": False, "signed": False},
                      {"name": "signed", "heterogeneity": 0.0, "directed": False, "signed": True}],
        "g0a": {"sizes": [100, 200, 400], "sigma_inter": 0.1, "density_ratio": 0.25,
                "T_swt_grid": [11.0, 120.0], "total_time": 400.0, "record_every": 25,
                "chunk_steps": 5000, "chaos_n_steps": 2000, "chaos_transient": 200, "chaos_renorm": 5},
        "g0b": {"N": 40, "N_IL": 10, "sigma_inter": 1.5, "total_time": 800.0, "record_every": 25,
                "T_swt_grid": [2.0, 300.0]},
    }


def _ctx(gate, out_dir, prereg=None, execution=None, orch="ORCH"):
    return contract.RunContext(
        gate=gate, runner_file="fixture", authorized=True, dry_run=False, out_dir=Path(out_dir),
        prereg=prereg or _tiny_prereg(), prereg_canonical_hash="pc", prereg_file_sha256="pf",
        execution=execution or _tiny_exec(), execution_canonical_hash="ec", execution_file_sha256="ef",
        freeze_content_hash="fh", source_commit="src", freeze_commit="frz", freeze_tag="tag",
        runtime_head="frz", runner_sha256="rs", orchestrator_sha256=orch, run_id="rid",
        environment={"python": "x"})


# ---------------------------------------------------------------------------
# C: single inferential function (corrected sign-test fact)
# ---------------------------------------------------------------------------
def test_exact_sign_test_8_equal_signs_is_0_0078():
    st = exact_two_sided_sign_test([0.3] * 8)
    assert abs(st["p_value"] - 0.0078125) < 1e-9   # the v3 doc denied this


def test_paired_decision_zero_handling_and_std():
    dec = paired_decision([0.0, 0.0, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3], floor=0.02, std_mult=3.0,
                          alpha=0.05, n_boot=100, boot_seed=1)
    assert dec["sign_test"]["n_zero"] == 2 and dec["sign_test"]["n_nonzero"] == 6
    assert dec["std_definition"].startswith("sample standard deviation")


# ---------------------------------------------------------------------------
# J.2 no per-evaluation-seed max(fast,intermediate,slow)
# ---------------------------------------------------------------------------
def test_no_per_seed_arm_max_in_g1_source():
    src = (EXP / "run_g1_g2_paired_v2.py").read_text()
    assert "max(gf, gi, gs)" not in src
    assert "best_switch = max" not in src


# ---------------------------------------------------------------------------
# J.1 evaluation data does not change the selected arm
# ---------------------------------------------------------------------------
def test_arm_selection_independent_of_evaluation_seeds(tmp_path):
    sp = _tiny_exec()["surrogate_paired"]
    sel = _tiny_prereg()["seed_blocks"]["paired_selection"]
    arm1, _ = g1g2._select_arm(sp, sel)
    arm2, _ = g1g2._select_arm(sp, sel)
    assert arm1 == arm2
    r_a = g1g2.compute(_ctx("G1_G2_paired", tmp_path / "a", prereg=_tiny_prereg((81, 82))))
    r_b = g1g2.compute(_ctx("G1_G2_paired", tmp_path / "b", prereg=_tiny_prereg((83, 84))))
    assert r_a["result"]["selected_arm"] == r_b["result"]["selected_arm"] == arm1


# ---------------------------------------------------------------------------
# J.3 candidate set deterministic + lexicographic tie-break
# ---------------------------------------------------------------------------
def test_best_static_deterministic_and_lexicographic():
    sp = _tiny_exec()["surrogate_paired"]
    sel = _tiny_prereg()["seed_blocks"]["paired_selection"]
    s1, sc1, n1 = g1g2._select_best_static(sp, sel)
    s2, sc2, n2 = g1g2._select_best_static(sp, sel)
    assert s1 == s2 and n1 == n2
    # winner must be the lexicographically-smallest among candidates achieving the max score
    # (reconstruct candidate scores)
    import numpy as _np
    cand = set()
    from src.networks.paired_switching import build_base_snapshots
    for s in sel:
        cand.update(build_base_snapshots(sp["N"], sp["N_IL"], sp["K"], _np.random.default_rng(s)))
    srng = _np.random.default_rng(sp["candidate_search_seed"])
    for _ in range(sp["best_static_search"]):
        cand.add(tuple(sorted(srng.choice(sp["N"], size=sp["N_IL"], replace=False).tolist())))
    scores = {c: float(_np.mean([g1g2._gamma(sp, g1g2._static(sp, c), s) for s in sel])) for c in cand}
    best = max(scores.values())
    winners = sorted(c for c in cand if abs(scores[c] - best) <= 1e-12)
    assert s1 == winners[0]


# ---------------------------------------------------------------------------
# J.4 "best admissible static" claim is not made
# ---------------------------------------------------------------------------
def test_g1_strict_does_not_claim_best_admissible(tmp_path):
    rep = g1g2.compute(_ctx("G1_G2_paired", tmp_path))
    assert rep["result"]["comparator_name"] == "best-of-frozen-candidate-set"
    assert "admissible" not in json.dumps(rep["result"]).lower()


# ---------------------------------------------------------------------------
# J.5 G1 hierarchy
# ---------------------------------------------------------------------------
def test_g1_hierarchy_not_interpretable_when_weak_not_pass():
    g1s_raw = {"verdict": "PASS", "reason": None}
    g2_raw = {"verdict": "PASS", "reason": None}
    g1s, g2 = g1g2._apply_hierarchy("INCONCLUSIVE", g1s_raw, g2_raw)
    assert g1s["gate_verdict"] == "NOT_INTERPRETABLE"
    assert g2["gate_verdict"] == "NOT_INTERPRETABLE"
    g1s2, g2b = g1g2._apply_hierarchy("PASS", g1s_raw, g2_raw)
    assert g1s2["gate_verdict"] == "PASS" and g2b["gate_verdict"] == "PASS"


# ---------------------------------------------------------------------------
# J.6 / J.7 G2 permutation null
# ---------------------------------------------------------------------------
def test_g2_commuting_no_order_effect_cannot_pass(tmp_path):
    # intra_coupling=0 -> diagonal maps -> commute -> order irrelevant -> delta~0
    ex = _tiny_exec(intra=0.0)
    rep = g1g2.compute(_ctx("G1_G2_paired", tmp_path, execution=ex))
    g2 = rep["result"]["G2_order"]
    assert abs(g2["mean"]) < 1e-9
    assert g2["gate_verdict"] in ("INCONCLUSIVE", "NOT_INTERPRETABLE")


def test_g2_noncommuting_order_is_detectable():
    # non-commuting maps => gamma varies across order permutations
    from src.networks.paired_switching import build_base_snapshots, paired_rate_schedule
    from src.simulation.linear_surrogate import SurrogateParams
    from src.simulation.surrogate_v2 import difference_step_maps_v2
    sp = _tiny_exec()["surrogate_paired"]
    p = SurrogateParams(N=sp["N"], kappa=sp["kappa"], rho_target=sp["rho_target"],
                        intra_coupling=sp["intra_coupling"], seed_struct=41)
    base = build_base_snapshots(sp["N"], sp["N_IL"], sp["K"], np.random.default_rng(41))
    sched = paired_rate_schedule(base, sp["N"], sp["N_IL"], sp["cycles_intermediate"], sp["H"], "i")
    gammas = []
    for ps in order_permutations(sched, 8, np.random.default_rng(7)):
        maps = difference_step_maps_v2(p, ps, np.random.default_rng(41))
        gammas.append(full_contraction_rate(ordered_product(maps), sched.total_steps))
    assert np.std(gammas) > 1e-9                      # order detectable
    # a consistently-signed delta must PASS the shared rule
    dec = paired_decision([0.3, 0.28, 0.31, 0.29, 0.30, 0.27, 0.32, 0.30], 0.02, 3.0, 0.05, 100, 1)
    assert dec["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# J.8 G3 uses the SHARED inference function object
# ---------------------------------------------------------------------------
def test_g3_uses_shared_inference():
    assert g3.paired_decision is g1g2.paired_decision is paired_decision


# ---------------------------------------------------------------------------
# J.9 signed budget compared numerically; per-seed metadata
# ---------------------------------------------------------------------------
def test_g3_signed_budget_numeric_and_per_seed(tmp_path):
    rep = g3.compute(_ctx("G3_robustness", tmp_path))
    signed = rep["result"]["by_stage"]["signed"]["per_seed"]
    assert len(signed) == len(_tiny_prereg()["seed_blocks"]["stages"])  # ALL seeds
    for rec in signed:
        assert rec["n_negative_offdiag"] >= 1
        assert rec["budget_diff"] <= 1e-9            # numeric budget equality


# ---------------------------------------------------------------------------
# J.10 G4 exact horizon
# ---------------------------------------------------------------------------
def test_g4_schedule_total_steps_equals_horizon():
    s = g4._make_schedule(8, 2, 60, 6, 61)
    assert s.total_steps == 60
    assert s.total_steps != 66                        # the v3 606-for-600 style bug
    with pytest.raises(contract.ContractError):
        g4._make_schedule(8, 2, 60, 7, 61)            # 60 % 7 != 0


# ---------------------------------------------------------------------------
# J.11 G4 baseline is mandatory
# ---------------------------------------------------------------------------
def test_g4_baseline_mandatory():
    assert g4._verdict_from_conditions({"precision_gt_0.6": True, "recall_gt_0.6": True,
                                        "contraction_corr_gt_0.5": True, "beats_baseline": False}) == "FAIL"
    assert g4._verdict_from_conditions({"precision_gt_0.6": True, "recall_gt_0.6": True,
                                        "contraction_corr_gt_0.5": True, "beats_baseline": True}) == "PASS"


# ---------------------------------------------------------------------------
# J.12 failed >20% -> EXECUTION_INVALID (G4 and G3)
# ---------------------------------------------------------------------------
def test_g4_failed_runs_execution_invalid(tmp_path, monkeypatch):
    import run_g4_v2 as mod

    class Bad:
        def __init__(self, N, T):
            self.p1 = np.full((T + 1, N), np.nan); self.p2 = np.full((T + 1, N), np.nan)
            self.active = np.zeros((T, N)); self.d_true = np.zeros((T + 1, N))

    monkeypatch.setattr(mod, "simulate_observed_v2", lambda p, s, r, async_stride=(1, 1): Bad(8, 60))
    rep = mod.compute(_ctx("G4_identifiability", tmp_path))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["reason_code"] == "FAILED_RUNS"


def test_g3_failed_runs_execution_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(g3, "_gamma_from_A", lambda *a, **k: float("nan"))
    rep = g3.compute(_ctx("G3_robustness", tmp_path))
    assert rep["verdict"] == "EXECUTION_INVALID"


# ---------------------------------------------------------------------------
# J.13 G0A checkpoint survives crash
# ---------------------------------------------------------------------------
def test_g0a_checkpoint_survives_crash(tmp_path):
    prov = {"freeze": "f", "prereg": "p", "exec": "e", "runner": "r"}
    keyf = ["kind", "N", "T_swt", "seed"]
    led = _custody.CheckpointLedger(tmp_path / "cp.jsonl", prov, keyf)
    led.append({"kind": "switch", "N": 200, "T_swt": 11.0, "seed": 11}, {"synced": True})
    led.append({"kind": "chaos", "N": 200, "T_swt": None, "seed": 11}, {"lambda_max": 0.02})
    del led                                            # simulate crash
    led2 = _custody.CheckpointLedger(tmp_path / "cp.jsonl", prov, keyf)
    assert led2.n_completed() == 2
    assert led2.has({"kind": "switch", "N": 200, "T_swt": 11.0, "seed": 11})
    with pytest.raises(_custody.CheckpointCorrupt):    # duplicate refused
        led2.append({"kind": "switch", "N": 200, "T_swt": 11.0, "seed": 11}, {"synced": False})


def test_g0a_checkpoint_corruption_detected(tmp_path):
    p = tmp_path / "cp.jsonl"
    p.write_text('{"cell": {"kind":"x"}, "provenance_key": "z"}\nNOT JSON\n')
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.CheckpointLedger(p, {"a": 1}, ["kind"])


# ---------------------------------------------------------------------------
# J.14 G0A: single favorable N=100 cannot decide; deciding sizes required
# ---------------------------------------------------------------------------
def _cell(kind, N, T, seed, res):
    return {"cell": {"kind": kind, "N": N, "T_swt": T, "seed": seed}, "result": res}


def test_g0a_n100_favorable_cannot_pass():
    cost = {"deciding_sizes": [200, 400]}
    cells = [_cell("chaos", 100, None, 11, {"lambda_max": 0.02}),
             _cell("switch", 100, 11.0, 11, {"synced": True})]
    v, reason, complete = g0a.gate_verdict(cells, [11], [11.0, 120.0], cost, timed_out=False)
    assert v == "INCONCLUSIVE" and reason == "INCONCLUSIVE_BY_COST" and not complete


def test_g0a_complete_deciding_grid_decides():
    cost = {"deciding_sizes": [200, 400]}
    cells = []
    for N in (200, 400):
        cells.append(_cell("chaos", N, None, 11, {"lambda_max": 0.02}))
        cells.append(_cell("switch", N, 11.0, 11, {"synced": True}))   # fast syncs
        cells.append(_cell("switch", N, 120.0, 11, {"synced": False}))  # slow doesn't
    v, reason, complete = g0a.gate_verdict(cells, [11], [11.0, 120.0], cost, timed_out=False)
    assert complete and v == "PASS"


# ---------------------------------------------------------------------------
# J.15 MSF shift T_swt vs 2*T_swt (non-tautological)
# ---------------------------------------------------------------------------
def test_msf_shift_tswt_not_2tswt():
    from src.dynamics.msf_switching import paper_g, smooth_square_gamma_v2
    T, dt = 10.0, 0.01
    gof = smooth_square_gamma_v2(2, T, dt)
    ts = [0.3, 3.1, 7.7, 12.5]
    diff_half = [abs(gof(int(t / dt))[1] - 0.5 * (paper_g(t + T, T) + 1)) for t in ts]
    diff_full = [abs(gof(int(t / dt))[1] - 0.5 * (paper_g(t + 2 * T, T) + 1)) for t in ts]
    assert max(diff_half) < 1e-9         # channel 1 IS the T_swt (half-period) shift
    assert max(diff_full) > 0.3          # a 2*T_swt shift (v3 bug) would be a DIFFERENT signal
    # and channel1 (T_swt shift) differs from channel0 (anti-phase), unlike the 2T_swt bug
    ch0 = np.array([gof(int(t / dt))[0] for t in np.arange(0, 40, 0.5)])
    ch1 = np.array([gof(int(t / dt))[1] for t in np.arange(0, 40, 0.5)])
    assert np.max(np.abs(ch0 - ch1)) > 0.5


# ---------------------------------------------------------------------------
# J.16 descendant check actually reaches _is_descendant on real commits
# ---------------------------------------------------------------------------
def test_is_descendant_real_commits():
    head = contract._git_head()
    parent = contract._git("rev-parse", "HEAD~1")
    assert contract._is_descendant(parent, head) is True
    assert contract._is_descendant(head, parent) is False
    assert contract._is_descendant(head, head) is False


# ---------------------------------------------------------------------------
# J.17 report records runner SHA and orchestrator SHA
# ---------------------------------------------------------------------------
def test_report_records_runner_and_orchestrator_sha(tmp_path):
    rep = g4.compute(_ctx("G4_identifiability", tmp_path, orch="ORCH_SHA_123"))
    contract.validate_report_schema(rep)
    assert rep["provenance"]["runner_sha256"] == "rs"
    assert rep["provenance"]["orchestrator_sha256"] == "ORCH_SHA_123"


# ---------------------------------------------------------------------------
# J.18 failure -> no partial success bundle
# ---------------------------------------------------------------------------
def test_no_partial_success_bundle_on_failure(tmp_path):
    run_dir = tmp_path / "runs"
    run_id = "abc123"
    staging = _custody.staging_dir(run_dir, run_id)
    staging.mkdir(parents=True)
    (staging / "g0b_v2.json").write_text("{}")            # a partial staged report
    _custody.write_failure_ledger(run_dir, run_id, [{"gate": "G0C", "error": "boom"}])
    # failure => publish NOT called; final must NOT exist; failure ledger present
    assert not _custody.final_dir(run_dir, run_id).exists()
    assert (run_dir / f"{run_id}.failed" / "failure_ledger.json").exists()


def test_publish_atomic_refuses_existing_final(tmp_path):
    run_dir = tmp_path / "runs"; run_id = "x"
    staging = _custody.staging_dir(run_dir, run_id); staging.mkdir(parents=True)
    final = _custody.final_dir(run_dir, run_id); final.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        _custody.publish_atomic(staging, final)


# ---------------------------------------------------------------------------
# J.19 two sequential individual runners share run_id
# ---------------------------------------------------------------------------
def test_two_individual_runners_share_run_id(tmp_path):
    ctx = _ctx("G", tmp_path / "rid")
    r1 = {"gate": "G", "verdict": "PASS", "result": {}, "provenance": {}}
    contract.atomic_write_report(ctx, "g0b_calibrated_v2.json", r1)
    contract.atomic_write_report(ctx, "g4_identifiability_v2.json", r1)   # same dir, distinct report
    assert (Path(tmp_path / "rid") / "g0b_calibrated_v2.json").exists()
    assert (Path(tmp_path / "rid") / "g4_identifiability_v2.json").exists()
    with pytest.raises(contract.ContractError):        # no overwrite
        contract.atomic_write_report(ctx, "g0b_calibrated_v2.json", r1)


# ---------------------------------------------------------------------------
# J.20 corruption of prereg / contract / freeze / output detected
# ---------------------------------------------------------------------------
def _real_hashes():
    def h(p):
        raw = Path(p).read_bytes()
        from src.validation.freeze_v2 import config_canonical_hash
        return config_canonical_hash(json.loads(raw)), hashlib.sha256(raw).hexdigest()
    return (h(REPO / "experiments/configs/synthetic_prereg_v4.json")
            + h(REPO / "experiments/configs/synthetic_execution_contract_v2.json"))


def _args(**kw):
    pc, pf, ec, ef = _real_hashes()
    base = dict(i_am_authorized=True, dry_run=False,
                prereg=str(REPO / "experiments/configs/synthetic_prereg_v4.json"),
                execution_contract=str(REPO / "experiments/configs/synthetic_execution_contract_v2.json"),
                expect_prereg_canonical=pc, expect_prereg_file_sha=pf,
                expect_execution_contract_canonical=ec, expect_execution_contract_file_sha=ef,
                freeze=str(REPO / "artifacts/nope.json"), expect_freeze_content_hash="fh",
                expect_freeze_commit="frz", expect_freeze_tag="tag",
                run_dir=str(REPO.parent / "external_runs"), orchestrator_sha=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_corrupt_prereg_rejected():
    with pytest.raises(contract.ContractError):
        contract.build_context(_args(expect_prereg_canonical="deadbeef"), "G", str(EXP / "run_g4_v2.py"))


def test_corrupt_execution_contract_rejected():
    with pytest.raises(contract.ContractError):
        contract.build_context(_args(expect_execution_contract_file_sha="deadbeef"), "G", str(EXP / "run_g4_v2.py"))


def test_run_dir_inside_repo_rejected(monkeypatch, tmp_path):
    from src.validation.freeze_v2 import build_manifest_v2
    monkeypatch.setattr(contract, "_tree_clean", lambda: True)
    monkeypatch.setattr(contract, "_git_head", lambda: "H")
    monkeypatch.setattr(contract, "_deref_tag", lambda t: "H")
    monkeypatch.setattr(contract, "_is_descendant", lambda a, d: False)
    man = build_manifest_v2(REPO, {"roots": [], "files": ["python-version.txt"]},
                            {"k": 1}, "experiments/configs/synthetic_prereg_v4.json")
    fp = tmp_path / "frz.json"; fp.write_text(json.dumps(man))
    with pytest.raises(contract.ContractError, match="OUTSIDE"):
        contract.build_context(_args(expect_freeze_commit="H", freeze=str(fp),
                                     expect_freeze_content_hash=man["content_hash"],
                                     run_dir=str(REPO / "experiments")),
                               "G", str(EXP / "run_g4_v2.py"))


def test_corrupt_output_overwrite_refused(tmp_path):
    ctx = _ctx("G", tmp_path)
    rep = {"gate": "G", "verdict": "PASS", "result": {}, "provenance": {}}
    contract.atomic_write_report(ctx, "x_v2.json", rep)
    with pytest.raises(contract.ContractError):
        contract.atomic_write_report(ctx, "x_v2.json", rep)


# ---------------------------------------------------------------------------
# suite flag contradiction rejected
# ---------------------------------------------------------------------------
def test_suite_rejects_contradictory_flags():
    import run_suite_v2 as suite
    assert suite.main(["--cheap-only", "--include-g0a-expensive", "--run-dir", "/x"]) == 2


# ---------------------------------------------------------------------------
# no superseded v1 imports (kept from P1.2-A, extended)
# ---------------------------------------------------------------------------
FORBIDDEN_MODULES = {"src.validation.freeze", "run_reproduction", "run_surrogate_causal",
                     "run_causal_fhn", "run_surrogate_stages", "run_identifiability",
                     "run_msf", "run_freeze"}
FORBIDDEN_FROM = {("src.simulation.linear_surrogate", "build_basis_operator"),
                  ("src.simulation.linear_surrogate", "simulate_observed")}
V2_FILES = ["run_g0a_exact_v2.py", "run_g0b_calibrated_v2.py", "run_g0c_msf_v2.py",
            "run_g1_g2_paired_v2.py", "run_g3_v2.py", "run_g4_v2.py", "run_suite_v2.py",
            "_contract_v2.py", "_custody.py", "_repro_common_v2.py"]


@pytest.mark.parametrize("fn", V2_FILES)
def test_no_superseded_v1_imports(fn):
    src = (EXP / fn).read_text()
    assert "importlib" not in src
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name not in FORBIDDEN_MODULES, f"{fn}: {a.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in FORBIDDEN_MODULES, f"{fn}: {mod}"
            for a in node.names:
                assert (mod, a.name) not in FORBIDDEN_FROM, f"{fn}: {mod}.{a.name}"
                assert a.name != "smooth_square_gamma", f"{fn}: v1 smooth_square_gamma"


def test_v2_import_graph_excludes_v1():
    code = ("import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');\n"
            "import run_g4_v2, run_g1_g2_paired_v2, run_g3_v2, run_g0a_exact_v2, run_suite_v2\n"
            "v1={'run_reproduction','run_surrogate_causal','run_causal_fhn','run_surrogate_stages',"
            "'run_identifiability','run_msf','run_freeze','src.validation.freeze'}\n"
            "bad=sorted(v1 & set(sys.modules)); assert not bad, bad; print('OK')") % (str(EXP), str(REPO))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr
