"""P1.2-D runner / contract / custody tests. Each targeted test fails against the
v5 behaviour and passes against v6."""
import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import _contract_v2 as contract
import _custody
import run_g0a_exact_v2 as g0a
import run_g0b_calibrated_v2 as g0b
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4
import run_suite_v2 as suite
from src.metrics.inference import exact_two_sided_sign_test
from src.metrics.lyapunov import LyapunovDeadlineExceeded, largest_lyapunov_isolated_layer

REPO = Path(__file__).resolve().parents[1]
EXP = REPO / "experiments"


def _sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _fr(**kw):
    """A well-formed failure record (matches contract.failure_record structure)."""
    base = {"exception_type": "E", "message": "m", "seed": 1, "cell": {},
            "timestamp_utc": "t"}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _tiny_prereg(paired_eval=None):
    return {
        "global": {"dt": 0.01},
        "tolerances": {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25},
        "fhn": {"density_ratio": 0.25},
        "seed_blocks": {"identifiability": [61, 62, 63, 64], "paired_selection": [41, 42, 43, 44],
                        "paired_evaluation": list(paired_eval or (81, 82, 83, 84)),
                        "stages": [51, 52, 53, 54], "g0c_msf": [31], "g0a": [11],
                        "g0b": [11, 12, 13, 14, 15]},
        "gates": {"G0A_exact_reproduction": {"cost_rule": {
                      "max_wall_time_seconds": 86400, "chunk_steps": 50,
                      "mandatory_minimum_size": 8, "minimum_completed_seeds": 1,
                      "deciding_sizes": [16, 24], "non_deciding_sizes": [8]}},
                  "G3_robustness": {"signed_budget_tolerance": 1e-9}},
    }


def _tiny_exec(intra=0.06, K=3, cyc_int=2, H=24, n_perm=5, kappa=0.6):
    return {
        "inference": {"alpha": 0.05, "std_mult": 3.0, "n_boot": 100, "boot_seed": 20260713,
                      "floor_surrogate_gamma": 0.02, "floor_identifiability_margin": 0.05},
        "surrogate_paired": {"N": 8, "N_IL": 2, "K": K, "H": H, "kappa": kappa,
                             "rho_target": 1.04, "intra_coupling": intra, "cycles_fast": 4,
                             "cycles_intermediate": cyc_int, "cycles_slow": 1,
                             "variable_dwell_multiset": [4, 8, 12], "best_static_search": 4,
                             "neg_fraction_signed": 0.4, "candidate_search_seed": 900001,
                             "g2_n_perm": n_perm, "g2_perm_seed": 700003},
        "g4": {"N": 8, "N_IL": 2, "kappa": 0.6, "rho_target": 1.04, "intra_coupling": 0.06,
               "horizon_steps": 60, "dwell_fast": 6, "estimator_window": 8, "obs_noise": 0.05,
               "factor_scale": 1.0, "async_variants": [[1, 1]]},
        "g0c": {"N": 2, "lam_perp": 2.0, "alpha": 5.0, "n_steps": 400, "transient_steps": 100,
                "renorm_every": 5, "sigma_grid": [0.3], "T_swt_grid": [11.0]},
        "g3_stages": [{"name": "faithful", "heterogeneity": 0.0, "directed": False, "signed": False},
                      {"name": "mild_heterogeneity", "heterogeneity": 0.05, "directed": False, "signed": False},
                      {"name": "signed", "heterogeneity": 0.0, "directed": False, "signed": True}],
        "g0a": {"sizes": [8, 16, 24], "sigma_inter": 0.1, "density_ratio": 0.25,
                "T_swt_grid": [2.0, 4.0], "total_time": 5.0, "record_every": 25,
                "chunk_steps": 50, "chaos_n_steps": 500, "chaos_transient": 100, "chaos_renorm": 5},
        "g0b": {"N": 8, "N_IL": 2, "sigma_inter": 1.5, "total_time": 5.0, "record_every": 25,
                "T_swt_grid": [2.0, 300.0]},
    }


def _ctx(gate, out_dir, prereg=None, execution=None, scope="individual:G4", orch=None,
         attempt_id="att", campaign_id="camp"):
    return contract.RunContext(
        gate=gate, runner_file="fixture", authorized=True, dry_run=False, out_dir=Path(out_dir),
        prereg=prereg or _tiny_prereg(), prereg_canonical_hash="pc", prereg_file_sha256="pf",
        execution=execution or _tiny_exec(), execution_canonical_hash="ec", execution_file_sha256="ef",
        execution_scope=scope, execution_mode=scope,
        freeze_content_hash="fh", source_commit="src", freeze_commit="frz", freeze_tag="tag",
        runtime_head="frz", runner_sha256="rs", orchestrator_sha256=orch,
        campaign_id=campaign_id, attempt_id=attempt_id, authorization_token_sha256="toksha",
        environment={"python": "x"})


def _publish_attempt(run_dir, attempt_id, extra_roles=None, extra_files=None):
    """Publish a minimal sealed attempt via the real v6 custody path."""
    st = _custody.staging_dir(run_dir, attempt_id); st.mkdir(parents=True)
    (st / "r_v2.json").write_text('{"x": 1}')
    roles = {"r_v2.json": "report"}
    for name, content in (extra_files or {}).items():
        (st / name).write_text(content)
        roles[name] = (extra_roles or {}).get(name, "checkpoint")
    inv = _custody.inventory_staging(st, roles)
    man = _custody.build_attempt_manifest(
        campaign_id="camp", attempt_id=attempt_id, execution_scope="cheap-suite",
        hashes={}, head="h", tag="t", structured_command={"argv_normalized": []},
        runner_shas={}, orchestrator_sha=None, authorization_token_sha256="toksha",
        started_utc="s", ended_utc="e", exit_status=0, artifacts=inv,
        gate_verdicts={}, environment={})
    _custody.seal_and_publish(st, _custody.final_dir(run_dir, attempt_id), man)
    return man


# ===========================================================================
# B: suite crash handler (end-to-end via suite.main, real crash in _run_gates)
# ===========================================================================
def test_suite_crash_end_to_end_no_unbound_and_no_success(tmp_path, monkeypatch):
    run_dir = tmp_path / "runs"
    ctx0 = _ctx("suite_v2", run_dir, scope="cheap-suite", attempt_id="attCRASH")
    monkeypatch.setattr(suite, "build_context", lambda a, g, f, s: ctx0)
    # inject a REAL crash in the first cheap gate
    monkeypatch.setattr(g0b, "compute", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    argv = ["--i-am-authorized", "--run-dir", str(run_dir),
            "--expect-prereg-canonical", "x", "--expect-prereg-file-sha", "x",
            "--expect-execution-contract-canonical", "x", "--expect-execution-contract-file-sha", "x",
            "--expect-freeze-content-hash", "x", "--expect-freeze-commit", "x",
            "--expect-freeze-tag", "x", "--authorization-token", "tok"]
    rc = suite.main(argv)                         # must NOT raise UnboundLocalError
    assert rc == 1
    assert not _custody.final_dir(run_dir, "attCRASH").exists()          # no final
    assert not (_custody.final_dir(run_dir, "attCRASH") / "SEALED").exists()
    assert _custody.interrupted_dir(run_dir, "attCRASH").exists()        # staging preserved
    led = _custody.failed_dir(run_dir, "attCRASH") / "failure_ledger.json"
    assert led.exists()
    rec = json.loads(led.read_text())
    assert any("boom" in json.dumps(f) for f in rec["failures"])         # original error kept


def test_suite_records_real_runner_sha(tmp_path):
    ctx0 = _ctx("suite", tmp_path, scope="cheap-suite")
    staging = tmp_path / "staging"; staging.mkdir()
    written, verdicts, runner_shas, failures = suite._run_gates(
        ctx0, staging, [g4], str(EXP / "run_suite_v2.py"))
    assert not failures
    rep = json.loads((staging / g4.REPORT).read_text())
    assert rep["provenance"]["runner_sha256"] == _sha_file(g4.__file__)
    assert rep["provenance"]["orchestrator_sha256"] == _sha_file(EXP / "run_suite_v2.py")
    assert rep["provenance"]["runner_sha256"] != rep["provenance"]["orchestrator_sha256"]


def test_child_context_immutable():
    c = contract.child_context(_ctx("suite", ".", scope="cheap-suite"),
                               g3.__file__, str(EXP / "run_suite_v2.py"))
    assert c.runner_sha256 == _sha_file(g3.__file__)
    with pytest.raises(Exception):
        c.runner_sha256 = "forged"


def test_orchestrator_sha_argument_removed():
    with pytest.raises(SystemExit):
        suite.main(["--orchestrator-sha", "none", "--plan"])


def test_resume_argument_removed():
    with pytest.raises(SystemExit):
        suite.main(["--resume-authorized-attempt", "x", "--plan"])
    src = (EXP / "run_suite_v2.py").read_text()
    assert "crash-recoverable" not in src


# ===========================================================================
# C: integral manifest + atomic seal + adversarial verification
# ===========================================================================
def test_complete_publish_has_valid_sealed(tmp_path):
    _publish_attempt(tmp_path, "att1", extra_files={"g0a_checkpoint.jsonl": '{"seq":0}'})
    final = _custody.final_dir(tmp_path, "att1")
    assert (final / "SEALED").exists()
    v = _custody.verify_sealed_attempt(final)
    assert v["ok"], v
    man = json.loads((final / "attempt_manifest.json").read_text())
    # inventory records size + sha + role for every artifact
    assert set(man["artifacts"]) == {"r_v2.json", "g0a_checkpoint.jsonl"}
    for meta in man["artifacts"].values():
        assert {"size", "sha256", "role"} <= set(meta)
    # exactly manifest + SEALED + inventoried artifacts
    assert {p.name for p in final.iterdir()} == {"attempt_manifest.json", "SEALED",
                                                 "r_v2.json", "g0a_checkpoint.jsonl"}


def test_tampered_checkpoint_fails_verification(tmp_path):
    _publish_attempt(tmp_path, "att2", extra_files={"g0a_checkpoint.jsonl": '{"seq":0}'})
    final = _custody.final_dir(tmp_path, "att2")
    (final / "g0a_checkpoint.jsonl").write_text('{"seq":999}')     # tamper
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"] and any("SHA mismatch" in e for e in v["errors"])


def test_extra_file_fails_verification(tmp_path):
    _publish_attempt(tmp_path, "att3")
    final = _custody.final_dir(tmp_path, "att3")
    (final / "sneaky.json").write_text("{}")       # unexpected extra file
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"] and any("unexpected" in e for e in v["errors"])


def test_symlink_fails_verification(tmp_path):
    _publish_attempt(tmp_path, "att4")
    final = _custody.final_dir(tmp_path, "att4")
    (final / "link_v2.json").symlink_to(final / "r_v2.json")
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"] and any("symlink" in e or "unexpected" in e for e in v["errors"])


def test_manifest_inventory_tamper_detected(tmp_path):
    _publish_attempt(tmp_path, "att5")
    final = _custody.final_dir(tmp_path, "att5")
    man = json.loads((final / "attempt_manifest.json").read_text())
    man["artifacts"]["r_v2.json"]["sha256"] = "0" * 64     # tamper inventory
    (final / "attempt_manifest.json").write_text(json.dumps(man))
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"]      # manifest content hash no longer matches SEALED


def test_missing_artifact_fails_verification(tmp_path):
    _publish_attempt(tmp_path, "att6")
    final = _custody.final_dir(tmp_path, "att6")
    (final / "r_v2.json").unlink()
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"] and any("missing artifact" in e for e in v["errors"])


def test_fail_before_rename_leaves_no_final(tmp_path):
    st = _custody.staging_dir(tmp_path, "att7"); st.mkdir(parents=True)
    (st / "r_v2.json").write_text('{"x":1}')
    (st / "undeclared.json").write_text("{}")      # not in the inventory
    inv = {"r_v2.json": {"size": 8, "sha256": hashlib.sha256(b'{"x":1}').hexdigest(),
                         "role": "report"}}
    man = _custody.build_attempt_manifest(
        campaign_id="c", attempt_id="att7", execution_scope="cheap-suite", hashes={},
        head="h", tag="t", structured_command={}, runner_shas={}, orchestrator_sha=None,
        authorization_token_sha256="tk", started_utc="s", ended_utc="e", exit_status=0,
        artifacts=inv, gate_verdicts={}, environment={})
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.seal_and_publish(st, _custody.final_dir(tmp_path, "att7"), man)
    assert not _custody.final_dir(tmp_path, "att7").exists()    # no final on failure


def test_inventory_rejects_symlink_and_undeclared(tmp_path):
    st = tmp_path / "s"; st.mkdir()
    (st / "r_v2.json").write_text("{}")
    (st / "extra.json").write_text("{}")
    with pytest.raises(_custody.CheckpointCorrupt, match="unexpected"):
        _custody.inventory_staging(st, {"r_v2.json": "report"})
    (st / "extra.json").unlink()
    (st / "ln").symlink_to(st / "r_v2.json")
    with pytest.raises(_custody.CheckpointCorrupt, match="symlink|non-regular"):
        _custody.inventory_staging(st, {"r_v2.json": "report", "ln": "x"})


def test_published_attempt_immutable_and_coexists(tmp_path):
    _publish_attempt(tmp_path, "attCHEAP")
    _publish_attempt(tmp_path, "attG0A")           # different attempt, same campaign
    assert _custody.verify_sealed_attempt(_custody.final_dir(tmp_path, "attCHEAP"))["ok"]
    assert _custody.verify_sealed_attempt(_custody.final_dir(tmp_path, "attG0A"))["ok"]


def test_sealed_refuses_further_write(tmp_path):
    _publish_attempt(tmp_path, "attS")
    final = _custody.final_dir(tmp_path, "attS")
    ctx = replace(_ctx("G", final), out_dir=final)
    with pytest.raises(contract.ContractError, match="SEALED"):
        contract.atomic_write_report(ctx, "late_v2.json",
                                     {"gate": "G", "verdict": "PASS", "provenance": {}, "result": {}})


# ===========================================================================
# E: attempt identity, reconstructible command, token non-exposure
# ===========================================================================
def test_attempt_id_recomputable_from_token_sha():
    camp = contract.campaign_id_of("p", "e", "f", "c")
    tok = "MY-SECRET-TOKEN"
    tsha = contract.token_sha_of(tok)
    a1 = contract.attempt_id_of(camp, "g0a-only", tsha)
    # an auditor with only the recorded token_sha recomputes the same attempt_id
    a2 = contract.attempt_id_of(camp, "g0a-only", tsha)
    assert a1 == a2
    # a different scope or token changes it
    assert a1 != contract.attempt_id_of(camp, "cheap-suite", tsha)
    assert a1 != contract.attempt_id_of(camp, "g0a-only", contract.token_sha_of("other"))


def test_token_validation_rejects_empty_and_whitespace():
    for bad in ["", "   ", "\t\n", None, 5]:
        with pytest.raises(contract.ContractError):
            contract.validate_token(bad)
    assert contract.validate_token("ok") == "ok"


def test_structured_command_masks_token():
    ctx = _ctx("G", ".", scope="individual:G0A")
    args = argparse.Namespace(run_dir="/ext/runs")
    argv = ["--authorization-token", "SUPERSECRET", "--run-dir", "/ext/runs"]
    cmd = contract.structured_command(args, ctx, argv)
    blob = json.dumps(cmd)
    assert "SUPERSECRET" not in blob
    assert f"<sha256:{ctx.authorization_token_sha256}>" in blob
    assert cmd["python_version"] and cmd["interpreter"]


# ===========================================================================
# F: technical failure vs INCONCLUSIVE_BY_COST in G0A
# ===========================================================================
def _cell(kind, N, T, seed, res):
    return {"cell": {"kind": kind, "N": N, "T_swt": T, "seed": seed}, "result": res}


def _full_grid(seeds, T_grid, deciding, failed=None, missing=None):
    failed = failed or set(); missing = missing or set()
    cells = []
    for N in deciding:
        for s in seeds:
            if ("chaos", N, s) not in missing:
                cells.append(_cell("chaos", N, None, s, {"lambda_max": 0.02}))
            for T in T_grid:
                if ("switch", N, T, s) in missing:
                    continue
                if ("switch", N, T, s) in failed:
                    cells.append(_cell("switch", N, T, s, {"failed": True, "error": "X"}))
                else:
                    cells.append(_cell("switch", N, T, s, {"synced": T <= 25}))
    return cells


def test_g0a_technical_failure_without_deadline_not_cost():
    seeds = [1, 2, 3, 4, 5]; cost = {"deciding_sizes": [200]}
    # >20% failed in a required cell, NO deadline -> EXECUTION_INVALID (not cost)
    failed = {("switch", 200, 11.0, s) for s in (1, 2)}      # 2/5 = 40%
    cells = _full_grid(seeds, [11.0], [200], failed=failed)
    v, reason, _ = g0a.gate_verdict(cells, seeds, [11.0], cost, interrupted_by_cost=False)
    assert v == "EXECUTION_INVALID" and reason == "FAILED_RUNS"


def test_g0a_missing_without_deadline_execution_invalid():
    seeds = [1, 2]; cost = {"deciding_sizes": [200]}
    cells = _full_grid(seeds, [11.0], [200], missing={("switch", 200, 11.0, 2)})
    v, reason, _ = g0a.gate_verdict(cells, seeds, [11.0], cost, interrupted_by_cost=False)
    assert v == "EXECUTION_INVALID" and reason == "FAILED_RUNS"


def test_g0a_missing_with_clean_deadline_is_cost():
    seeds = [1, 2]; cost = {"deciding_sizes": [200]}
    cells = _full_grid(seeds, [11.0], [200], missing={("switch", 200, 11.0, 2)})
    v, reason, _ = g0a.gate_verdict(cells, seeds, [11.0], cost, interrupted_by_cost=True)
    assert v == "INCONCLUSIVE" and reason == "INCONCLUSIVE_BY_COST"


def test_g0a_state_record_not_counted_as_cell():
    seeds = [1]; cost = {"deciding_sizes": [200]}
    cells = _full_grid(seeds, [11.0, 120.0], [200])
    cells.append(_cell("state", None, None, None, {"state": "INTERRUPTED_BY_COST"}))
    v, reason, _ = g0a.gate_verdict(cells, seeds, [11.0, 120.0], cost, interrupted_by_cost=False)
    assert v == "PASS"          # the state record neither completes nor blocks


def test_g0a_le20pct_uses_successful_seeds():
    seeds = [1, 2, 3, 4, 5]; cost = {"deciding_sizes": [200]}
    failed = {("switch", 200, 11.0, 1)}          # 1/5 = 20% (allowed)
    cells = _full_grid(seeds, [11.0, 120.0], [200], failed=failed)
    v, reason, detail = g0a.gate_verdict(cells, seeds, [11.0, 120.0], cost, False)
    assert v == "PASS"
    assert detail["disclosure"]["N200_T11.0"]["n_successful"] == 4


def test_g0a_n100_favorable_cannot_decide():
    cost = {"deciding_sizes": [200, 400]}
    cells = [_cell("chaos", 100, None, 11, {"lambda_max": 0.02}),
             _cell("switch", 100, 11.0, 11, {"synced": True})]
    v, reason, _ = g0a.gate_verdict(cells, [11], [11.0, 120.0], cost, False)
    assert v == "EXECUTION_INVALID" and reason == "FAILED_RUNS"   # deciding cells missing, no cost


def test_lyapunov_abort_inside_chaos():
    from src.dynamics.fhn import FHNParams
    calls = {"n": 0}

    def abort():
        calls["n"] += 1
        return calls["n"] > 2

    with pytest.raises(LyapunovDeadlineExceeded):
        largest_lyapunov_isolated_layer(FHNParams(N=8),
                                        np.random.default_rng(1).uniform(-2, 2, 16),
                                        dt=0.01, n_steps=2000, renorm_every=5,
                                        transient_steps=500, chunk_steps=50, abort_check=abort)


def test_g0a_deadline_inside_chaos_stops_gate(tmp_path, monkeypatch):
    seq = {"n": 0}

    def fake_monotonic():                    # G: the soft budget uses time.monotonic
        seq["n"] += 1
        return 0.0 if seq["n"] <= 3 else 1e9

    monkeypatch.setattr(g0a.time, "monotonic", fake_monotonic)
    rep = g0a.compute(_ctx("G0A", tmp_path, scope="individual:G0A"))
    assert rep["verdict"] == "INCONCLUSIVE"
    assert rep["provenance"]["reason_code"] == "INCONCLUSIVE_BY_COST"
    assert rep["result"]["interrupted_by_cost"] is True
    assert rep["result"]["checkpoint_name"] == "g0a_checkpoint.jsonl"   # relative (C.3)
    assert "/" not in rep["result"]["checkpoint_name"]


def test_g0a_size_order_deciding_first():
    assert g0a._size_order([100, 200, 400], [200, 400]) == [200, 400, 100]


# ===========================================================================
# G: global failed-seed policy enforced
# ===========================================================================
def test_g1_selection_failure_recorded(tmp_path, monkeypatch):
    real = g1g2._gamma

    def flaky(sp, sched, seed):
        if seed == 42:                       # a SELECTION seed
            raise ValueError("selection boom")
        return real(sp, sched, seed)

    monkeypatch.setattr(g1g2, "_gamma", flaky)
    rep = g1g2.compute(_ctx("G1G2", tmp_path, scope="individual:G1G2"))
    fails = rep["provenance"]["failures"]
    assert any(f["cell"].get("phase") == "selection" and f["seed"] == 42 for f in fails)


def test_g1_over20pct_selection_execution_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(g1g2, "_gamma", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    rep = g1g2.compute(_ctx("G1G2", tmp_path, scope="individual:G1G2"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["reason_code"] == "FAILED_RUNS"


def test_g3_failure_records_full(tmp_path, monkeypatch):
    real = g3.build_basis_operator_v2

    def flaky(p, rng, neg_fraction=0.4):
        if p.seed_struct == 52 and not p.signed and p.heterogeneity == 0.05:
            raise RuntimeError("op boom")
        return real(p, rng, neg_fraction=neg_fraction)

    monkeypatch.setattr(g3, "build_basis_operator_v2", flaky)
    rep = g3.compute(_ctx("G3", tmp_path, scope="individual:G3"))
    assert any(f["exception_type"] == "RuntimeError" and f["seed"] == 52
               for f in rep["provenance"]["failures"])


def test_g4_per_variant_over20_and_all_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(g4, "simulate_observed_v2",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sim boom")))
    rep = g4.compute(_ctx("G4", tmp_path, scope="individual:G4"))
    assert rep["verdict"] == "EXECUTION_INVALID" and rep["provenance"]["reason_code"] == "FAILED_RUNS"
    assert rep["provenance"]["failures"] and all(
        f["exception_type"] == "RuntimeError" for f in rep["provenance"]["failures"])


def test_g0b_denominator_successful_seeds_only(tmp_path, monkeypatch):
    import _repro_common_v2 as rc
    real = rc.simulate

    def flaky(p, sched, cfg, x0, **kw):
        flaky.n += 1
        if flaky.n % 5 == 1:                 # 1 of 5 seeds per cell (20%)
            raise FloatingPointError("injected")
        return real(p, sched, cfg, x0, **kw)
    flaky.n = 0
    monkeypatch.setattr(rc, "simulate", flaky)
    rep = g0b.compute(_ctx("G0B", tmp_path, scope="individual:G0B"))
    for r in rep["result"]["rows"]:
        assert len(r["failed_seeds"]) == 1 and 0 < r["frac_failed"] <= 0.21
        assert all({"exception_type", "seed", "timestamp_utc"} <= set(fr)
                   for fr in r["failure_records"])
        assert r["n_successful"] == 4


def test_g0c_nonfinite_full_failure_record(tmp_path, monkeypatch):
    monkeypatch.setattr(g0c, "transverse_lyapunov", lambda *a, **k: float("nan"))
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"


def test_g0c_exception_full_failure_record(tmp_path, monkeypatch):
    monkeypatch.setattr(g0c, "transverse_lyapunov",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("die")))
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["failures"][0]["exception_type"] == "RuntimeError"


def test_schema_validates_failure_record_structure():
    prov = {k: 1 for k in ["prereg_canonical_hash", "prereg_file_sha256",
                           "execution_contract_canonical_hash", "execution_contract_file_sha256",
                           "freeze_content_hash", "runner_sha256", "orchestrator_sha256",
                           "execution_scope", "execution_mode", "campaign_id", "attempt_id",
                           "authorization_token_sha256", "source_commit", "freeze_commit",
                           "freeze_tag", "runtime_head", "environment", "seeds", "params",
                           "criterion"]}
    prov["failures"] = []
    ok = {"gate": "X", "verdict": "PASS", "result": {}, "provenance": dict(prov)}
    contract.validate_report_schema(ok)
    bad = dict(ok); bad["provenance"] = dict(prov); bad["provenance"]["failures"] = [{"seed": 1}]
    with pytest.raises(contract.ContractError, match="malformed failure record"):
        contract.validate_report_schema(bad)


# ===========================================================================
# F: checkpoint ledger hash chain (retained + extended)
# ===========================================================================
PROV = {"freeze": "f", "prereg": "p"}
KEYS = ["kind", "N", "seed"]


def test_ledger_crash_recovery_and_duplicate(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1}); del led
    led2 = _custody.CheckpointLedger(p, PROV, KEYS)
    assert led2.has({"kind": "s", "N": 1, "seed": 1})
    with pytest.raises(_custody.CheckpointCorrupt):
        led2.append({"kind": "s", "N": 1, "seed": 1}, {"v": 2})


def test_ledger_reorder_edit_gap_foreign_rejected(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    led.append({"kind": "s", "N": 1, "seed": 2}, {"v": 2})
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[1], lines[0]]) + "\n")            # reorder
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.CheckpointLedger(p, PROV, KEYS)
    r0 = json.loads(lines[0]); r0["result"] = {"v": 9}              # edit
    p.write_text("\n".join([json.dumps(r0, sort_keys=True), lines[1]]) + "\n")
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.CheckpointLedger(p, PROV, KEYS)
    p.write_text("\n".join(lines) + "\n")                          # foreign provenance
    with pytest.raises(_custody.CheckpointCorrupt, match="foreign"):
        _custody.CheckpointLedger(p, {"freeze": "OTHER", "prereg": "p"}, KEYS)


def test_ledger_truncated_tail(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    p.write_text(p.read_text() + '{"seq": 1, "prev')      # truncated final line
    with pytest.raises(_custody.TruncatedTail) as ei:
        _custody.CheckpointLedger(p, PROV, KEYS)
    assert ei.value.n_valid == 1
    led2 = _custody.CheckpointLedger(p, PROV, KEYS, allow_truncated_tail=True)
    assert led2.n_completed() == 1 and p.with_suffix(".jsonl.truncated").exists()


def test_attempt_lock_exclusive(tmp_path):
    l1 = _custody.AttemptLock(tmp_path, "attX"); l2 = _custody.AttemptLock(tmp_path, "attX")
    assert l1.acquire() is True and l2.acquire() is False
    l1.release()
    assert l2.acquire() is True
    l2.release()


# ===========================================================================
# retained science guards
# ===========================================================================
def test_exact_sign_test_8_equal():
    assert abs(exact_two_sided_sign_test([0.3] * 8)["p_value"] - 0.0078125) < 1e-9


def test_g1_hierarchy():
    g1s, g2v = g1g2._apply_hierarchy("INCONCLUSIVE", {"verdict": "PASS"}, {"verdict": "PASS"})
    assert g1s["gate_verdict"] == "NOT_INTERPRETABLE" and g2v["gate_verdict"] == "NOT_INTERPRETABLE"


def test_no_per_seed_arm_max():
    src = (EXP / "run_g1_g2_paired_v2.py").read_text()
    assert "max(gf, gi, gs)" not in src and "best_switch = max" not in src


def test_g1_no_best_admissible_claim(tmp_path):
    rep = g1g2.compute(_ctx("G", tmp_path, scope="individual:G1G2"))
    assert rep["result"]["comparator_name"] == "best-of-frozen-candidate-set"


def test_g3_signed_budget(tmp_path):
    rep = g3.compute(_ctx("G3", tmp_path, scope="individual:G3"))
    for rec in rep["result"]["by_stage"]["signed"]["per_seed"]:
        assert rec["n_negative_offdiag"] >= 1 and rec["budget_diff"] <= 1e-9


def test_g4_horizon_and_baseline():
    assert g4._make_schedule(8, 2, 60, 6, 61).total_steps == 60
    with pytest.raises(contract.ContractError):
        g4._make_schedule(8, 2, 60, 7, 61)
    assert g4._verdict_from_conditions({"a": True, "beats_baseline": False}) == "FAIL"


def test_g2_commuting_cannot_pass(tmp_path):
    rep = g1g2.compute(_ctx("G", tmp_path, execution=_tiny_exec(intra=0.0), scope="individual:G1G2"))
    assert abs(rep["result"]["G2_order"]["mean"]) < 1e-9
    assert rep["result"]["G2_order"]["verdict"] == "INCONCLUSIVE"


def test_g2_positive_end_to_end(tmp_path):
    ex = _tiny_exec(intra=0.25, K=2, cyc_int=12, H=24, n_perm=30, kappa=0.9)
    ex["inference"]["std_mult"] = 0.5
    ex["inference"]["floor_surrogate_gamma"] = 1e-4
    pr = _tiny_prereg(paired_eval=(81, 82, 83, 84, 85, 86, 87, 88, 89, 90))
    rep = g1g2.compute(_ctx("G1G2", tmp_path, prereg=pr, execution=ex, scope="individual:G1G2"))
    assert rep["result"]["G2_order"]["mean"] > 0
    assert rep["result"]["G2_order"]["verdict"] == "PASS"
    assert "permutation-median comparator" in rep["result"]["g2_method"]


def test_scope_from_flags_contradictions():
    def a(**kw):
        b = dict(cheap_only=False, include_g0a_expensive=False, g0a_only=False); b.update(kw)
        return argparse.Namespace(**b)
    assert suite._scope_from_flags(a()) == "cheap-suite"
    assert suite._scope_from_flags(a(g0a_only=True)) == "g0a-only"
    with pytest.raises(contract.ContractError):
        suite._scope_from_flags(a(cheap_only=True, include_g0a_expensive=True))


def test_is_descendant_real_commits():
    head = contract._git_head(); parent = contract._git("rev-parse", "HEAD~1")
    assert contract._is_descendant(parent, head) and not contract._is_descendant(head, parent)


# ---------------------------------------------------------------------------
# no superseded v1 imports
# ---------------------------------------------------------------------------
FORBIDDEN = {"src.validation.freeze", "run_reproduction", "run_surrogate_causal",
             "run_causal_fhn", "run_surrogate_stages", "run_identifiability", "run_msf", "run_freeze"}
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
                assert a.name not in FORBIDDEN, f"{fn}: {a.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in FORBIDDEN, f"{fn}: {node.module}"


def test_v2_import_graph_excludes_v1():
    code = ("import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');\n"
            "import run_g4_v2, run_g1_g2_paired_v2, run_g3_v2, run_g0a_exact_v2, run_suite_v2\n"
            "v1={'run_reproduction','run_surrogate_causal','run_causal_fhn','run_surrogate_stages',"
            "'run_identifiability','run_msf','run_freeze','src.validation.freeze'}\n"
            "bad=sorted(v1 & set(sys.modules)); assert not bad, bad; print('OK')") % (str(EXP), str(REPO))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr
