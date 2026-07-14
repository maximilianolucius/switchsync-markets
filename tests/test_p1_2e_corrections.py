"""P1.2-E correction tests. Each test fails against the v6 behaviour and passes
against v7: pre-rename validation (B), flat staging + never-raising verify (C),
full custody cycle in one handler + .invalid (D), truly common G1/G2 mask (E),
frozen G0A precedence + counters (F/G), G0B/G0C failure records (H), removed
contradictions (I) and enriched non-overwritable failure ledgers (J)."""
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

import _contract_v2 as contract
import _custody
import run_g0a_exact_v2 as g0a
import run_g0b_calibrated_v2 as g0b
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_suite_v2 as suite

REPO = Path(__file__).resolve().parents[1]


def _fr(**kw):
    base = {"exception_type": "E", "message": "m", "seed": 1, "cell": {},
            "timestamp_utc": "t"}
    base.update(kw)
    return base


def _ctx(gate, out_dir, scope="individual:G4", attempt_id="att", campaign_id="camp"):
    return contract.RunContext(
        gate=gate, runner_file="fixture", authorized=True, dry_run=False,
        out_dir=Path(out_dir), prereg=_tiny_prereg(), prereg_canonical_hash="pc",
        prereg_file_sha256="pf", execution=_tiny_exec(), execution_canonical_hash="ec",
        execution_file_sha256="ef", execution_scope=scope, execution_mode=scope,
        freeze_content_hash="fh", source_commit="src", freeze_commit="frz",
        freeze_tag="tag", runtime_head="frz", runner_sha256="rs",
        orchestrator_sha256=None, campaign_id=campaign_id, attempt_id=attempt_id,
        authorization_token_sha256="toksha", environment={"python": "x"})


def _tiny_prereg():
    return {
        "global": {"dt": 0.01},
        "tolerances": {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25},
        "fhn": {"density_ratio": 0.25},
        "seed_blocks": {"paired_selection": [41, 42, 43, 44],
                        "paired_evaluation": [81, 82, 83, 84], "g0c_msf": [31],
                        "g0a": [11], "g0b": [11, 12, 13, 14, 15]},
        "gates": {"G0A_exact_reproduction": {"cost_rule": {
            "max_wall_time_seconds": 86400, "chunk_steps": 50,
            "deciding_sizes": [16, 24], "non_deciding_sizes": [8]}}},
    }


def _tiny_exec():
    return {
        "inference": {"alpha": 0.05, "std_mult": 3.0, "n_boot": 100, "boot_seed": 20260713,
                      "floor_surrogate_gamma": 0.02, "floor_identifiability_margin": 0.05},
        "surrogate_paired": {"N": 8, "N_IL": 2, "K": 3, "H": 24, "kappa": 0.6,
                             "rho_target": 1.04, "intra_coupling": 0.06, "cycles_fast": 4,
                             "cycles_intermediate": 2, "cycles_slow": 1,
                             "variable_dwell_multiset": [4, 8, 12], "best_static_search": 4,
                             "neg_fraction_signed": 0.4, "candidate_search_seed": 900001,
                             "g2_n_perm": 5, "g2_perm_seed": 700003},
        "g0c": {"N": 2, "lam_perp": 2.0, "alpha": 5.0, "n_steps": 400, "transient_steps": 100,
                "renorm_every": 5, "sigma_grid": [0.3], "T_swt_grid": [11.0]},
        "g0a": {"sizes": [8, 16, 24], "sigma_inter": 0.1, "density_ratio": 0.25,
                "T_swt_grid": [2.0, 4.0], "total_time": 5.0, "record_every": 25,
                "chunk_steps": 50, "chaos_n_steps": 500, "chaos_transient": 100, "chaos_renorm": 5},
        "g0b": {"N": 8, "N_IL": 2, "sigma_inter": 1.5, "total_time": 5.0, "record_every": 25,
                "T_swt_grid": [2.0, 300.0]},
    }


def _build_manifest(attempt_id, inv):
    return _custody.build_attempt_manifest(
        campaign_id="camp", attempt_id=attempt_id, execution_scope="cheap-suite",
        hashes={}, head="h", tag="t", structured_command={"argv_normalized": []},
        runner_shas={}, orchestrator_sha=None, authorization_token_sha256="toksha",
        started_utc="s", ended_utc="e", exit_status=0, artifacts=inv,
        gate_verdicts={}, environment={})


def _stage_one_report(run_dir, attempt_id):
    st = _custody.staging_dir(run_dir, attempt_id)
    st.mkdir(parents=True)
    (st / "r_v2.json").write_text('{"x": 1}')
    inv = _custody.inventory_staging(st, {"r_v2.json": "report"})
    return st, inv


# ===========================================================================
# B: single pre-rename validation; an invalid manifest never reaches os.replace
# ===========================================================================
def test_b_altered_manifest_hash_fails_before_rename(tmp_path):
    st, inv = _stage_one_report(tmp_path, "attB")
    man = _build_manifest("attB", inv)
    man["manifest_content_hash"] = "0" * 64          # alter ONLY the content hash
    final = _custody.final_dir(tmp_path, "attB")
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.seal_and_publish(st, final, man)
    assert not final.exists()                        # deterministic pre-rename error
    assert st.exists()                               # staging untouched


def test_b_mismatched_inventory_fails_before_rename(tmp_path):
    st, inv = _stage_one_report(tmp_path, "attB2")
    inv["r_v2.json"]["sha256"] = "f" * 64            # claim a wrong artifact hash
    man = _build_manifest("attB2", inv)
    final = _custody.final_dir(tmp_path, "attB2")
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.seal_and_publish(st, final, man)
    assert not final.exists()


# ===========================================================================
# C: flat staging, symlink/dir/special rejection, never-raising verifier
# ===========================================================================
def test_c_subdirectory_in_staging_rejected(tmp_path):
    st = _custody.staging_dir(tmp_path, "attC1"); st.mkdir(parents=True)
    (st / "r_v2.json").write_text("{}")
    (st / "sub").mkdir()                             # extra directory => not flat
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.inventory_staging(st, {"r_v2.json": "report"})


def _publish(run_dir, attempt_id):
    st, inv = _stage_one_report(run_dir, attempt_id)
    _custody.seal_and_publish(st, _custody.final_dir(run_dir, attempt_id),
                              _build_manifest(attempt_id, inv))
    return _custody.final_dir(run_dir, attempt_id)


def test_c_symlink_to_dir_fails_verification(tmp_path):
    final = _publish(tmp_path, "attC2")
    target = tmp_path / "d"; target.mkdir()
    (final / "linkdir").symlink_to(target, target_is_directory=True)
    v = _custody.verify_sealed_attempt(final)
    assert v["ok"] is False and any("non-regular" in e or "unexpected" in e for e in v["errors"])


def test_c_extra_empty_dir_fails_verification(tmp_path):
    final = _publish(tmp_path, "attC3")
    (final / "emptydir").mkdir()
    v = _custody.verify_sealed_attempt(final)
    assert v["ok"] is False and any("non-regular" in e or "unexpected" in e for e in v["errors"])


def test_c_verify_never_raises_on_malformed_manifest(tmp_path):
    final = _publish(tmp_path, "attC4")
    (final / "attempt_manifest.json").write_text("{ this is not json ")
    v = _custody.verify_sealed_attempt(final)        # MUST NOT raise
    assert v["ok"] is False and v["errors"]
    (final / "attempt_manifest.json").write_text('"a bare string, not a dict"')
    v2 = _custody.verify_sealed_attempt(final)       # MUST NOT raise
    assert v2["ok"] is False and v2["errors"]


# ===========================================================================
# D: full custody cycle in one handler; .invalid on post-rename failure
# ===========================================================================
_ARGV = ["--i-am-authorized", "--run-dir", None, "--expect-prereg-canonical", "x",
         "--expect-prereg-file-sha", "x", "--expect-execution-contract-canonical", "x",
         "--expect-execution-contract-file-sha", "x", "--expect-freeze-content-hash", "x",
         "--expect-freeze-commit", "x", "--expect-freeze-tag", "x",
         "--authorization-token", "tok"]


def _argv(run_dir):
    a = list(_ARGV); a[2] = str(run_dir); return a


def test_d_suite_seal_failure_no_final_ledger_written(tmp_path, monkeypatch):
    run_dir = tmp_path / "runs"
    ctx0 = _ctx("suite_v2", run_dir, scope="cheap-suite", attempt_id="attSEAL")
    monkeypatch.setattr(suite, "build_context", lambda a, g, f, s: ctx0)

    def fake_run_gates(c, staging, run_list, orch):
        (staging / "x_v2.json").write_text('{"gate": "G", "verdict": "PASS"}')
        return ({"x_v2.json": "sha"}, {"G": "PASS"}, {"G": "rs"}, [])

    monkeypatch.setattr(suite, "_run_gates", fake_run_gates)
    monkeypatch.setattr(_custody, "seal_and_publish",
                        lambda *a, **k: (_ for _ in ()).throw(_custody.CheckpointCorrupt("seal boom")))
    rc = suite.main(_argv(run_dir))
    assert rc == 1
    assert not _custody.final_dir(run_dir, "attSEAL").exists()
    assert _custody.interrupted_dir(run_dir, "attSEAL").exists()
    led = _custody.failed_dir(run_dir, "attSEAL") / "failure_ledger.json"
    assert led.exists() and "seal boom" in led.read_text()


def test_d_runner_seal_failure_no_final_ledger_written(tmp_path, monkeypatch):
    run_dir = tmp_path / "runs"
    ctx = _ctx("G4", run_dir, scope="individual:G4", attempt_id="attRC")
    monkeypatch.setattr(contract, "build_context",
                        lambda args, gate, rf, scope: replace(
                            ctx, out_dir=_custody.staging_dir(run_dir, "attRC")))

    def good_compute(c):
        return {"gate": "G4", "verdict": "PASS",
                "provenance": contract.provenance(c, [], {}, "crit"), "result": {}}

    monkeypatch.setattr(_custody, "seal_and_publish",
                        lambda *a, **k: (_ for _ in ()).throw(_custody.CheckpointCorrupt("seal boom")))
    rc = contract.run_cli("G4", "fixture", lambda c: {}, good_compute, "g4_v2.json",
                          "individual:G4", argv=_argv(run_dir))
    assert rc == 1
    assert not _custody.final_dir(run_dir, "attRC").exists()
    assert _custody.interrupted_dir(run_dir, "attRC").exists()
    led = _custody.failed_dir(run_dir, "attRC") / "failure_ledger.json"
    assert led.exists()


def test_d_post_rename_failure_moves_final_to_invalid(tmp_path, monkeypatch):
    st, inv = _stage_one_report(tmp_path, "attD")
    man = _build_manifest("attD", inv)
    final = _custody.final_dir(tmp_path, "attD")
    # pre-rename validation still passes; force ONLY the post-rename re-verification
    monkeypatch.setattr(_custody, "verify_sealed_attempt",
                        lambda p: {"ok": False, "errors": ["injected post-rename failure"]})
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.seal_and_publish(st, final, man)
    assert not final.exists()                                  # never left as success
    assert _custody.invalid_dir(tmp_path, "attD").exists()     # moved to .invalid


# ===========================================================================
# E: truly common G1/G2 mask — a CANDIDATE failure drops the whole seed
# ===========================================================================
def test_e_candidate_failure_drops_whole_seed_and_is_recorded(tmp_path, monkeypatch):
    real = g1g2._gamma

    def flaky(sp, sched, seed):
        if seed == 42 and sched.label == "static":       # a static CANDIDATE, not an arm
            raise FloatingPointError("candidate boom")
        return real(sp, sched, seed)

    monkeypatch.setattr(g1g2, "_gamma", flaky)
    rep = g1g2.compute(_ctx("G1G2", tmp_path, scope="individual:G1G2"))
    # 1 of 4 selection seeds dropped => >20% => EXECUTION_INVALID (frozen policy)
    assert rep["verdict"] == "EXECUTION_INVALID"
    frs = rep["provenance"]["failures"]
    assert any(f["seed"] == 42 and "candidate" in f["cell"] for f in frs), frs


# ===========================================================================
# F: frozen G0A precedence — technical failure OUTRANKS cost
# ===========================================================================
def _cells(entries):
    out = []
    for kind, N, T, seed, res in entries:
        out.append({"cell": {"kind": kind, "N": N, "T_swt": T, "seed": seed}, "result": res})
    return out


def test_f_technical_failure_outranks_cost(tmp_path):
    cells = _cells([
        ("chaos", 16, None, 11, {"lambda_max": 0.1}),
        ("chaos", 24, None, 11, {"lambda_max": 0.1}),
        ("switch", 16, 2.0, 11, {"failed": True, "error": "X"}),   # zero-success cell
        ("switch", 16, 4.0, 11, {"synced": True}),
        # (24, 2.0, 11) MISSING
        ("switch", 24, 4.0, 11, {"synced": True}),
        ("state", None, None, None, {"state": "INTERRUPTED_BY_COST"}),
    ])
    verdict, reason, detail = g0a.gate_verdict(
        cells, [11], [2.0, 4.0], {"deciding_sizes": [16, 24]}, interrupted_by_cost=True)
    assert verdict == "EXECUTION_INVALID" and reason == "FAILED_RUNS"
    assert "cell_failed" in detail                             # the technical failure, not cost


def test_f_clean_deadline_missing_is_cost_when_no_invalidating_failure(tmp_path):
    cells = _cells([
        ("chaos", 16, None, 11, {"lambda_max": 0.1}),
        ("chaos", 24, None, 11, {"lambda_max": 0.1}),
        ("switch", 16, 2.0, 11, {"synced": True}),
        ("switch", 16, 4.0, 11, {"synced": True}),
        # (24, 2.0, 11) MISSING, no invalidating failure anywhere
        ("switch", 24, 4.0, 11, {"synced": True}),
        ("state", None, None, None, {"state": "INTERRUPTED_BY_COST"}),
    ])
    verdict, reason, _ = g0a.gate_verdict(
        cells, [11], [2.0, 4.0], {"deciding_sizes": [16, 24]}, interrupted_by_cost=True)
    assert verdict == "INCONCLUSIVE" and reason == "INCONCLUSIVE_BY_COST"


def test_f_missing_without_deadline_is_invalid(tmp_path):
    cells = _cells([
        ("chaos", 16, None, 11, {"lambda_max": 0.1}),
        ("chaos", 24, None, 11, {"lambda_max": 0.1}),
        ("switch", 16, 2.0, 11, {"synced": True}),
        ("switch", 16, 4.0, 11, {"synced": True}),
        ("switch", 24, 4.0, 11, {"synced": True}),          # (24,2.0) missing, NO deadline
    ])
    verdict, reason, _ = g0a.gate_verdict(
        cells, [11], [2.0, 4.0], {"deciding_sizes": [16, 24]}, interrupted_by_cost=False)
    assert verdict == "EXECUTION_INVALID" and reason == "FAILED_RUNS"


# ===========================================================================
# G: split counters; state record excluded from n_science_cells; monotonic budget
# ===========================================================================
def test_g_counters_present_and_state_excluded_on_complete_run(tmp_path):
    r = g0a.compute(_ctx("G0A", tmp_path, scope="individual:G0A"))["result"]
    assert {"n_ledger_records", "n_science_cells", "n_state_records",
            "soft_deadline_seconds", "elapsed_seconds", "overshoot_seconds"} <= set(r)
    assert r["n_science_cells"] == r["n_ledger_records"] - r["n_state_records"]
    assert r["n_state_records"] == 0 and r["n_science_cells"] >= 1


def test_g_state_record_excluded_from_science_count_on_cost(tmp_path, monkeypatch):
    seq = {"n": 0}

    def fake_monotonic():
        seq["n"] += 1
        return 0.0 if seq["n"] <= 3 else 1e9

    monkeypatch.setattr(g0a.time, "monotonic", fake_monotonic)
    r = g0a.compute(_ctx("G0A", tmp_path, scope="individual:G0A"))["result"]
    assert r["interrupted_by_cost"] is True
    assert r["n_state_records"] == 1
    assert r["n_science_cells"] == r["n_ledger_records"] - 1


# ===========================================================================
# H: G0B/G0C full failure records; KeyboardInterrupt propagates
# ===========================================================================
def test_h_g0c_nonfinite_psi_emits_full_failure_record(tmp_path, monkeypatch):
    monkeypatch.setattr(g0c, "transverse_lyapunov", lambda *a, **k: float("inf"))
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    frs = rep["provenance"]["failures"]
    assert frs and all({"exception_type", "message", "seed", "cell", "timestamp_utc"} <= set(f)
                       for f in frs)
    assert rep["result"]["psi"] == "nonfinite"


def test_h_g0c_prereq_technical_failure_emits_record(tmp_path, monkeypatch):
    monkeypatch.setattr(g0c, "_prereq_antiphase",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("prereq boom")))
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["reason_code"] == "PREREQ_FAIL"
    frs = rep["provenance"]["failures"]
    assert frs and {"exception_type", "message", "seed", "cell", "timestamp_utc"} <= set(frs[0])
    assert "boom" in frs[0]["message"]


def test_h_g0b_construction_failure_recorded(tmp_path, monkeypatch):
    import _repro_common_v2 as rc
    monkeypatch.setattr(rc, "random_switching",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sched boom")))
    rep = g0b.compute(_ctx("G0B", tmp_path, scope="individual:G0B"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    frs = rep["provenance"]["failures"]
    assert frs and all({"exception_type", "message", "seed", "cell", "timestamp_utc"} <= set(f)
                       for f in frs)
    assert any("boom" in f["message"] for f in frs)


def test_h_g0b_keyboardinterrupt_propagates(tmp_path, monkeypatch):
    import _repro_common_v2 as rc
    monkeypatch.setattr(rc, "simulate",
                        lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        g0b.compute(_ctx("G0B", tmp_path, scope="individual:G0B"))


# ===========================================================================
# I: no residual interruption-policy contradictions in the ACTIVE v7 files
# ===========================================================================
ACTIVE_V7_FILES = [
    "experiments/configs/synthetic_prereg_v7.json",
    "experiments/configs/synthetic_execution_contract_v5.json",
    "docs/methodology/synthetic_prereg_v7.md",
    "experiments/_custody.py", "experiments/_contract_v2.py",
    "experiments/_repro_common_v2.py", "experiments/run_g0a_exact_v2.py",
    "experiments/run_g0b_calibrated_v2.py", "experiments/run_g0c_msf_v2.py",
    "experiments/run_g1_g2_paired_v2.py", "experiments/run_g3_v2.py",
    "experiments/run_g4_v2.py", "experiments/run_suite_v2.py",
    "experiments/run_freeze_execution_v7.py",
]
FORBIDDEN_PATTERNS = [
    r"crash[-_ ]recoverab",
    r"resume[-_]authoriz",
    r"continuation requires (?:explicit )?authoriz",
    r"rename[^.\n]{0,80}->[ \t]*SEALED",          # SEALED written AFTER the rename
    r"SEALED[^.\n]{0,30}after[^.\n]{0,20}rename",
]


def test_i_active_v7_files_free_of_forbidden_strings():
    for rel in ACTIVE_V7_FILES:
        text = (REPO / rel).read_text()
        for pat in FORBIDDEN_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            assert m is None, f"{rel}: forbidden {pat!r} -> {m.group(0)!r}"


def test_i_prereg_v7_states_one_coherent_policy():
    p = json.loads((REPO / "experiments/configs/synthetic_prereg_v7.json").read_text())
    crp = p["crash_and_resume_policy"]
    assert "interrupted_is_terminal" in crp and "incomplete_cause_distinction" in crp
    fp = p["gates"]["G0A_exact_reproduction"]["cost_rule"]["failure_precedence"]
    assert "OUTRANK" in fp.upper()                 # technical failure precedes cost


# ===========================================================================
# J: enriched, non-overwritable failure ledgers
# ===========================================================================
def test_j_failure_ledger_non_overwritable_and_enriched(tmp_path):
    run_dir = tmp_path / "runs"
    meta = {"campaign_id": "camp", "attempt_id": "attJ", "execution_scope": "cheap-suite",
            "hashes": {"freeze_content_hash": "fh"}, "freeze_commit": "frz",
            "freeze_tag": "tag", "authorization_token_sha256": "toksha",
            "started_utc": "s", "phase": "custody", "terminal_state": "INTERRUPTED"}
    p1 = _custody.write_failure_ledger(run_dir, "attJ", [_fr()], meta=meta)
    p2 = _custody.write_failure_ledger(run_dir, "attJ", [_fr(seed=2)], meta=meta)
    assert p1 != p2 and p1.exists() and p2.exists()       # never overwritten
    d = json.loads(p1.read_text())
    for k in ("campaign_id", "attempt_id", "execution_scope", "hashes", "freeze_commit",
              "authorization_token_sha256", "phase", "terminal_state", "utc", "failures"):
        assert k in d, k
