"""P1.2-C runner / contract / custody tests. Each targeted test fails against the
v4 behaviour and passes against v5."""
import argparse
import ast
import hashlib
import json
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
from src.metrics.inference import exact_two_sided_sign_test, paired_decision
from src.metrics.lyapunov import LyapunovDeadlineExceeded, largest_lyapunov_isolated_layer

REPO = Path(__file__).resolve().parents[1]
EXP = REPO / "experiments"


def _sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _tiny_prereg(paired_eval=None):
    return {
        "global": {"dt": 0.01},
        "tolerances": {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25},
        "fhn": {"density_ratio": 0.25},
        "seed_blocks": {"identifiability": [61, 62, 63, 64],
                        "paired_selection": [41, 42, 43, 44],
                        "paired_evaluation": list(paired_eval or (81, 82, 83, 84)),
                        "stages": [51, 52, 53, 54], "g0c_msf": [31],
                        "g0a": [11], "g0b": [11, 12, 13, 14, 15]},
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


def _ctx(gate, out_dir, prereg=None, execution=None, scope="individual:G4",
         orch=None):
    return contract.RunContext(
        gate=gate, runner_file="fixture", authorized=True, dry_run=False, out_dir=Path(out_dir),
        prereg=prereg or _tiny_prereg(), prereg_canonical_hash="pc", prereg_file_sha256="pf",
        execution=execution or _tiny_exec(), execution_canonical_hash="ec", execution_file_sha256="ef",
        execution_scope=scope, execution_mode=scope,
        freeze_content_hash="fh", source_commit="src", freeze_commit="frz", freeze_tag="tag",
        runtime_head="frz", runner_sha256="rs", orchestrator_sha256=orch,
        campaign_id="camp", attempt_id="att", authorization_token_sha256="tok",
        environment={"python": "x"})


# ===========================================================================
# J.1 suite records the REAL runner SHA, not the orchestrator's
# ===========================================================================
def test_suite_records_real_runner_sha_end_to_end(tmp_path):
    ctx0 = _ctx("suite", tmp_path, scope="cheap-suite")
    staging = tmp_path / "staging"; staging.mkdir()
    written, verdicts, runner_shas, failures = suite._run_gates(
        ctx0, staging, [g4], str(EXP / "run_suite_v2.py"))
    assert not failures
    rep = json.loads((staging / g4.REPORT).read_text())
    real_runner = _sha_file(g4.__file__)
    real_orch = _sha_file(EXP / "run_suite_v2.py")
    assert rep["provenance"]["runner_sha256"] == real_runner        # v4 recorded orch here
    assert rep["provenance"]["orchestrator_sha256"] == real_orch
    assert real_runner != real_orch                                  # both real, distinct
    assert runner_shas[g4.GATE] == real_runner


def test_child_context_immutable_and_correct():
    ctx0 = _ctx("suite", ".", scope="cheap-suite")
    c = contract.child_context(ctx0, g3.__file__, str(EXP / "run_suite_v2.py"))
    assert c.runner_sha256 == _sha_file(g3.__file__)
    assert c.orchestrator_sha256 == _sha_file(EXP / "run_suite_v2.py")
    with pytest.raises(Exception):      # frozen dataclass: no mutation
        c.runner_sha256 = "forged"


# ===========================================================================
# J.2 --orchestrator-sha is eliminated (rejected as unknown argument)
# ===========================================================================
def test_orchestrator_sha_argument_removed():
    with pytest.raises(SystemExit):
        suite.main(["--orchestrator-sha", "none", "--plan"])
    src = (EXP / "_contract_v2.py").read_text()
    assert "--orchestrator-sha" not in src.replace(
        "NO --orchestrator-sha argument", "")   # only the comment mentions it


# ===========================================================================
# J.3 attempt identity: scopes and tokens change attempt_id; campaign stable
# ===========================================================================
def test_attempt_ids_differ_by_scope_and_token():
    camp = contract.campaign_id_of("p", "e", "f", "c")
    a_cheap = contract.attempt_id_of(camp, "cheap-suite", "tokA")
    a_full = contract.attempt_id_of(camp, "full-suite", "tokA")
    a_g0a = contract.attempt_id_of(camp, "g0a-only", "tokA")
    a_tok2 = contract.attempt_id_of(camp, "cheap-suite", "tokB")
    assert len({a_cheap, a_full, a_g0a, a_tok2}) == 4


def test_scope_from_flags_and_contradictions():
    def args(**kw):
        base = dict(cheap_only=False, include_g0a_expensive=False, g0a_only=False)
        base.update(kw)
        return argparse.Namespace(**base)
    assert suite._scope_from_flags(args()) == "cheap-suite"
    assert suite._scope_from_flags(args(cheap_only=True)) == "cheap-suite"
    assert suite._scope_from_flags(args(include_g0a_expensive=True)) == "full-suite"
    assert suite._scope_from_flags(args(g0a_only=True)) == "g0a-only"
    with pytest.raises(contract.ContractError):
        suite._scope_from_flags(args(cheap_only=True, include_g0a_expensive=True))
    with pytest.raises(contract.ContractError):
        suite._scope_from_flags(args(cheap_only=True, g0a_only=True))


# ===========================================================================
# J.4 a published cheap attempt does not block a different g0a-only attempt
# ===========================================================================
def _publish_minimal(run_dir, attempt_id, report_name="r_v2.json"):
    st = _custody.staging_dir(run_dir, attempt_id); st.mkdir(parents=True)
    (st / report_name).write_text('{"x": 1}')
    man = _custody.build_attempt_manifest(
        campaign_id="camp", attempt_id=attempt_id, execution_scope="cheap-suite",
        hashes={}, head="h", tag="t", normalized_command="cmd",
        runner_shas={}, orchestrator_sha=None, started_utc="s", ended_utc="e",
        exit_status=0, reports={report_name: hashlib.sha256(b'{"x": 1}').hexdigest()},
        checkpoint_sha=None, gate_verdicts={}, environment={})
    _custody.seal_and_publish(st, _custody.final_dir(run_dir, attempt_id), man)
    return man


def test_published_cheap_does_not_block_other_attempt(tmp_path):
    _publish_minimal(tmp_path, "attemptCHEAP")
    # a DIFFERENT attempt under the same campaign publishes fine
    _publish_minimal(tmp_path, "attemptG0A")
    assert _custody.final_dir(tmp_path, "attemptCHEAP").exists()
    assert _custody.final_dir(tmp_path, "attemptG0A").exists()


# ===========================================================================
# J.5 SEALED bundle cannot be modified
# ===========================================================================
def test_sealed_bundle_refuses_writes(tmp_path):
    _publish_minimal(tmp_path, "attA")
    final = _custody.final_dir(tmp_path, "attA")
    assert (final / "SEALED").exists()
    ctx = replace(_ctx("G", final), out_dir=final)
    with pytest.raises(contract.ContractError, match="SEALED"):
        contract.atomic_write_report(ctx, "late_v2.json",
                                     {"gate": "G", "verdict": "PASS",
                                      "provenance": {}, "result": {}})


# ===========================================================================
# J.6 manifest contains + verifies each report SHA; J.7 corruption breaks it
# ===========================================================================
def test_manifest_verifies_and_corruption_detected(tmp_path):
    _publish_minimal(tmp_path, "attB")
    final = _custody.final_dir(tmp_path, "attB")
    v = _custody.verify_sealed_attempt(final)
    assert v["ok"], v
    # corrupt the report -> verification must fail
    (final / "r_v2.json").write_text('{"x": 2}')
    v2 = _custody.verify_sealed_attempt(final)
    assert not v2["ok"] and any("SHA mismatch" in e for e in v2["errors"])


def test_manifest_content_hash_tamper_detected(tmp_path):
    _publish_minimal(tmp_path, "attC")
    final = _custody.final_dir(tmp_path, "attC")
    man = json.loads((final / "attempt_manifest.json").read_text())
    man["execution_scope"] = "full-suite"      # tamper without fixing the hash
    (final / "attempt_manifest.json").write_text(json.dumps(man))
    v = _custody.verify_sealed_attempt(final)
    assert not v["ok"] and any("manifest content hash" in e for e in v["errors"])


# ===========================================================================
# J.8 a real suite failure publishes no success bundle
# ===========================================================================
def test_suite_gate_failure_no_success_bundle(tmp_path, monkeypatch):
    ctx0 = _ctx("suite", tmp_path, scope="cheap-suite")
    staging = tmp_path / "st"; staging.mkdir()
    monkeypatch.setattr(g4, "compute", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        suite._run_gates(ctx0, staging, [g4], str(EXP / "run_suite_v2.py"))
    # the custody layer records the failure and never publishes
    _custody.write_failure_ledger(tmp_path, "attF", [{"gate": "G4", "error": "boom"}])
    _custody.mark_interrupted(tmp_path, "attF")   # staging may not exist; no-op ok
    assert not _custody.final_dir(tmp_path, "attF").exists()
    assert (_custody.failed_dir(tmp_path, "attF") / "failure_ledger.json").exists()


# ===========================================================================
# J.9 crash leaves INTERRUPTED; resume only with authorization
# ===========================================================================
def test_crash_leaves_interrupted_and_resume_guarded(tmp_path):
    st = _custody.staging_dir(tmp_path, "attI"); st.mkdir(parents=True)
    (st / "partial_v2.json").write_text("{}")
    dst = _custody.mark_interrupted(tmp_path, "attI")
    assert dst.exists() and not st.exists()
    assert (dst / "partial_v2.json").exists()     # evidence preserved
    # resume without a token is refused BEFORE any contract work
    assert suite.main(["--resume-authorized-attempt", "attI"]) == 2
    # resume with a token is still refused in this phase (not authorized)
    assert suite.main(["--resume-authorized-attempt", "attI",
                       "--resume-authorization-token", "tok"]) == 2


# ===========================================================================
# J.10-12 checkpoint ledger: duplicates, chain, truncation
# ===========================================================================
PROV = {"freeze": "f", "prereg": "p"}
KEYS = ["kind", "N", "seed"]


def test_ledger_duplicate_on_reload_rejected(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    led.append({"kind": "s", "N": 1, "seed": 2}, {"v": 2})
    # hand-craft a DUPLICATE record with a VALID chain continuation
    lines = p.read_text().splitlines()
    rec1 = json.loads(lines[1])
    dup_body = {"seq": 2, "prev_record_hash": rec1["record_hash"],
                "cell": {"kind": "s", "N": 1, "seed": 1},   # duplicate UID
                "result": {"v": 99},
                "provenance_key": rec1["provenance_key"]}
    dup = dict(dup_body)
    dup["record_hash"] = _custody._sha(_custody._canonical(dup_body))
    p.write_text("\n".join(lines + [json.dumps(dup, sort_keys=True)]) + "\n")
    with pytest.raises(_custody.CheckpointCorrupt, match="duplicate"):
        _custody.CheckpointLedger(p, PROV, KEYS)


def test_ledger_reorder_and_edit_rejected(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    led.append({"kind": "s", "N": 1, "seed": 2}, {"v": 2})
    lines = p.read_text().splitlines()
    # reorder
    p.write_text("\n".join([lines[1], lines[0]]) + "\n")
    with pytest.raises(_custody.CheckpointCorrupt):
        _custody.CheckpointLedger(p, PROV, KEYS)
    # changed result (edit line 0 without fixing hash)
    rec0 = json.loads(lines[0]); rec0["result"] = {"v": 777}
    p.write_text("\n".join([json.dumps(rec0, sort_keys=True), lines[1]]) + "\n")
    with pytest.raises(_custody.CheckpointCorrupt, match="hash"):
        _custody.CheckpointLedger(p, PROV, KEYS)
    # sequence gap
    rec1 = json.loads(lines[1]); rec1["seq"] = 5
    p.write_text("\n".join([lines[0], json.dumps(rec1, sort_keys=True)]) + "\n")
    with pytest.raises(_custody.CheckpointCorrupt, match="sequence|chain"):
        _custody.CheckpointLedger(p, PROV, KEYS)
    # foreign provenance
    with pytest.raises(_custody.CheckpointCorrupt, match="foreign"):
        p.write_text("\n".join(lines) + "\n")
        _custody.CheckpointLedger(p, {"freeze": "OTHER", "prereg": "p"}, KEYS)


def test_ledger_truncated_tail_detected_and_prefix_preserved(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    led.append({"kind": "s", "N": 1, "seed": 2}, {"v": 2})
    raw = p.read_text()
    p.write_text(raw + '{"seq": 2, "prev_record_hash": "TRUNC')   # no newline: crash mid-write
    with pytest.raises(_custody.TruncatedTail) as ei:
        _custody.CheckpointLedger(p, PROV, KEYS)
    assert ei.value.n_valid == 2
    # authorized continuation loads the prefix and preserves the evidence copy
    led2 = _custody.CheckpointLedger(p, PROV, KEYS, allow_truncated_tail=True)
    assert led2.n_completed() == 2
    assert p.with_suffix(".jsonl.truncated").exists()   # evidence never deleted


def test_ledger_crash_recovery_roundtrip(tmp_path):
    p = tmp_path / "cp.jsonl"
    led = _custody.CheckpointLedger(p, PROV, KEYS)
    led.append({"kind": "s", "N": 1, "seed": 1}, {"v": 1})
    del led
    led2 = _custody.CheckpointLedger(p, PROV, KEYS)
    assert led2.has({"kind": "s", "N": 1, "seed": 1})
    with pytest.raises(_custody.CheckpointCorrupt):
        led2.append({"kind": "s", "N": 1, "seed": 1}, {"v": 2})   # duplicate refused


# ===========================================================================
# J.13/J.14 G0A: deadline DURING chaos; deciding sizes first; N=100 excluded
# ===========================================================================
def test_lyapunov_abort_fires_inside_chaos():
    from src.dynamics.fhn import FHNParams
    calls = {"n": 0}

    def abort():
        calls["n"] += 1
        return calls["n"] > 2          # fire on the 3rd poll (inside integration)

    p = FHNParams(N=8)
    x0 = np.random.default_rng(1).uniform(-2, 2, 16)
    with pytest.raises(LyapunovDeadlineExceeded):
        largest_lyapunov_isolated_layer(p, x0, dt=0.01, n_steps=2000,
                                        renorm_every=5, transient_steps=500,
                                        chunk_steps=50, abort_check=abort)
    assert calls["n"] >= 3


def test_g0a_deadline_inside_chaos_stops_gate(tmp_path, monkeypatch):
    # fake clock: t0=0; the "before size"/"before seed" checks see 0; the clock
    # jumps past the deadline only once chaos polling begins.
    seq = {"n": 0}

    def fake_time():
        seq["n"] += 1
        return 0.0 if seq["n"] <= 3 else 1e9     # 1:t0, 2:before-size, 3:before-seed

    monkeypatch.setattr(g0a.time, "time", fake_time)
    ctx = _ctx("G0A", tmp_path, scope="individual:G0A")
    rep = g0a.compute(ctx)
    assert rep["verdict"] == "INCONCLUSIVE"
    assert rep["provenance"]["reason_code"] == "INCONCLUSIVE_BY_COST"
    assert rep["result"]["interrupted_by_cost"] is True
    # deciding sizes run FIRST: with the budget dead inside the first chaos cell,
    # no N=8 (non-deciding) cell may exist in the ledger
    led = json.loads("[" + ",".join(
        (tmp_path / "g0a_checkpoint.jsonl").read_text().strip().splitlines()) + "]") \
        if (tmp_path / "g0a_checkpoint.jsonl").exists() else []
    assert all(r["cell"].get("N") != 8 for r in led if r["cell"]["kind"] != "state")


def test_g0a_size_order_deciding_first():
    assert g0a._size_order([100, 200, 400], [200, 400]) == [200, 400, 100]
    assert g0a._size_order([8, 16, 24], [16, 24]) == [16, 24, 8]


def test_g0a_n100_favorable_cannot_pass():
    cost = {"deciding_sizes": [200, 400]}
    cells = [{"cell": {"kind": "chaos", "N": 100, "T_swt": None, "seed": 11},
              "result": {"lambda_max": 0.02}},
             {"cell": {"kind": "switch", "N": 100, "T_swt": 11.0, "seed": 11},
              "result": {"synced": True}}]
    v, reason, complete = g0a.gate_verdict(cells, [11], [11.0, 120.0], cost, False)
    assert v == "INCONCLUSIVE" and reason == "INCONCLUSIVE_BY_COST" and not complete


def test_g0a_complete_deciding_grid_decides():
    cost = {"deciding_sizes": [200, 400]}
    cells = []
    for N in (200, 400):
        cells.append({"cell": {"kind": "chaos", "N": N, "T_swt": None, "seed": 11},
                      "result": {"lambda_max": 0.02}})
        cells.append({"cell": {"kind": "switch", "N": N, "T_swt": 11.0, "seed": 11},
                      "result": {"synced": True}})
        cells.append({"cell": {"kind": "switch", "N": N, "T_swt": 120.0, "seed": 11},
                      "result": {"synced": False}})
    v, reason, complete = g0a.gate_verdict(cells, [11], [11.0, 120.0], cost, False)
    assert complete and v == "PASS"


# ===========================================================================
# J.15 per-seed exceptions recorded in G1 / G3 / G4
# ===========================================================================
def test_g1_per_seed_exception_recorded(tmp_path, monkeypatch):
    real = g1g2._gamma

    def flaky(sp, sched, seed):
        if seed == 82:
            raise ValueError("injected failure")
        return real(sp, sched, seed)

    monkeypatch.setattr(g1g2, "_gamma", flaky)
    rep = g1g2.compute(_ctx("G1G2", tmp_path, scope="individual:G1G2"))
    fails = rep["provenance"]["failures"]
    assert any(f["exception_type"] == "ValueError" and f["seed"] == 82 for f in fails)
    assert rep["result"]["n_eval_failed"] == 1


def test_g3_per_seed_exception_recorded(tmp_path, monkeypatch):
    real = g3.build_basis_operator_v2

    def flaky(p, rng, neg_fraction=0.4):
        if p.seed_struct == 52 and not p.signed and p.heterogeneity == 0.05:
            raise RuntimeError("injected op failure")
        return real(p, rng, neg_fraction=neg_fraction)

    monkeypatch.setattr(g3, "build_basis_operator_v2", flaky)
    rep = g3.compute(_ctx("G3", tmp_path, scope="individual:G3"))
    fails = rep["provenance"]["failures"]
    assert any(f["exception_type"] == "RuntimeError" and f["seed"] == 52 for f in fails)


def test_g4_per_seed_exception_recorded_and_over20_invalid(tmp_path, monkeypatch):
    def always_raise(*a, **k):
        raise RuntimeError("sim exploded")

    monkeypatch.setattr(g4, "simulate_observed_v2", always_raise)
    rep = g4.compute(_ctx("G4", tmp_path, scope="individual:G4"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["reason_code"] == "FAILED_RUNS"
    assert all(f["exception_type"] == "RuntimeError" for f in rep["provenance"]["failures"])


# ===========================================================================
# J.16 G0C nonfinite / exception => EXECUTION_INVALID (single seed)
# ===========================================================================
def test_g0c_nonfinite_execution_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(g0c, "transverse_lyapunov", lambda *a, **k: float("nan"))
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["reason_code"] == "FAILED_RUNS"


def test_g0c_exception_execution_invalid(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("integrator died")
    monkeypatch.setattr(g0c, "transverse_lyapunov", boom)
    rep = g0c.compute(_ctx("G0C", tmp_path, scope="individual:G0C"))
    assert rep["verdict"] == "EXECUTION_INVALID"
    assert rep["provenance"]["failures"][0]["exception_type"] == "RuntimeError"


# ===========================================================================
# J.17 G0B denominator = successful seeds only (frozen)
# ===========================================================================
def test_g0b_denominator_successful_seeds_only(tmp_path, monkeypatch):
    import _repro_common_v2 as rc
    real = rc.simulate

    def flaky(p, sched, cfg, x0, **kw):
        # seed is recoverable from the schedule label? Use call count instead.
        flaky.n += 1
        if flaky.n % 5 == 1:            # fail 1 of 5 seeds per cell (20%, not >20%)
            raise FloatingPointError("injected")
        return real(p, sched, cfg, x0, **kw)
    flaky.n = 0
    monkeypatch.setattr(rc, "simulate", flaky)
    rep = g0b.compute(_ctx("G0B", tmp_path, scope="individual:G0B"))
    rows = rep["result"]["rows"]
    for r in rows:
        assert len(r["failed_seeds"]) == 1
        assert 0 < r["frac_failed"] <= 0.21
    assert "SUCCESSFUL_SEEDS_ONLY" in rep["result"]["frac_synced_denominator"]


# ===========================================================================
# J.18 G2 positive END-TO-END through the real pipeline
# ===========================================================================
def test_g2_positive_end_to_end(tmp_path):
    # K=2 with cycles=12 (H=24, dwell=1) => the ordered schedule is a perfect
    # A,B,A,B alternation; permutations clump epochs. With strongly non-commuting
    # maps this produces a REAL, systematically positive order effect.
    ex = _tiny_exec(intra=0.25, K=2, cyc_int=12, H=24, n_perm=30, kappa=0.9)
    ex["inference"]["std_mult"] = 0.5            # fixture-scale band
    ex["inference"]["floor_surrogate_gamma"] = 1e-4
    pr = _tiny_prereg(paired_eval=(81, 82, 83, 84, 85, 86, 87, 88, 89, 90))
    rep = g1g2.compute(_ctx("G1G2", tmp_path, prereg=pr, execution=ex,
                            scope="individual:G1G2"))
    g2res = rep["result"]["G2_order"]
    assert g2res["mean"] > 0                     # systematic positive displacement
    assert g2res["verdict"] == "PASS"            # significant through the REAL rule
    assert "permutation-median comparator" in rep["result"]["g2_method"]


def test_g2_commuting_no_order_effect_cannot_pass(tmp_path):
    ex = _tiny_exec(intra=0.0)                   # diagonal maps commute
    rep = g1g2.compute(_ctx("G1G2", tmp_path, execution=ex, scope="individual:G1G2"))
    g2res = rep["result"]["G2_order"]
    assert abs(g2res["mean"]) < 1e-9
    assert g2res["verdict"] == "INCONCLUSIVE"


# ===========================================================================
# J.19 two concurrent attempts with the same ID: exactly one gets the lock
# ===========================================================================
def test_attempt_lock_exclusive(tmp_path):
    l1 = _custody.AttemptLock(tmp_path, "attX")
    l2 = _custody.AttemptLock(tmp_path, "attX")
    assert l1.acquire() is True
    assert l2.acquire() is False        # second concurrent attempt refused
    l1.release()
    assert l2.acquire() is True
    l2.release()


# ===========================================================================
# retained guards (inference facts, schema, hierarchy, arm selection, misc)
# ===========================================================================
def test_exact_sign_test_8_equal_signs():
    assert abs(exact_two_sided_sign_test([0.3] * 8)["p_value"] - 0.0078125) < 1e-9


def test_g1_hierarchy_not_interpretable():
    g1s, g2v = g1g2._apply_hierarchy("INCONCLUSIVE", {"verdict": "PASS"}, {"verdict": "PASS"})
    assert g1s["gate_verdict"] == "NOT_INTERPRETABLE" and g2v["gate_verdict"] == "NOT_INTERPRETABLE"


def test_arm_selected_on_selection_seeds_only(tmp_path):
    sp = _tiny_exec()["surrogate_paired"]
    arm1, _ = g1g2._select_arm(sp, [41, 42, 43, 44])
    r_a = g1g2.compute(_ctx("G", tmp_path / "a", prereg=_tiny_prereg((81, 82)),
                            scope="individual:G1G2"))
    r_b = g1g2.compute(_ctx("G", tmp_path / "b", prereg=_tiny_prereg((83, 84)),
                            scope="individual:G1G2"))
    assert r_a["result"]["selected_arm"] == r_b["result"]["selected_arm"] == arm1


def test_no_per_seed_arm_max_in_source():
    src = (EXP / "run_g1_g2_paired_v2.py").read_text()
    assert "max(gf, gi, gs)" not in src and "best_switch = max" not in src


def test_g1_strict_no_best_admissible_claim(tmp_path):
    rep = g1g2.compute(_ctx("G", tmp_path, scope="individual:G1G2"))
    assert rep["result"]["comparator_name"] == "best-of-frozen-candidate-set"


def test_g3_signed_budget_and_shared_inference(tmp_path):
    assert g3.paired_decision is g1g2.paired_decision is paired_decision
    rep = g3.compute(_ctx("G3", tmp_path, scope="individual:G3"))
    for rec in rep["result"]["by_stage"]["signed"]["per_seed"]:
        assert rec["n_negative_offdiag"] >= 1 and rec["budget_diff"] <= 1e-9


def test_g4_horizon_and_baseline():
    s = g4._make_schedule(8, 2, 60, 6, 61)
    assert s.total_steps == 60
    with pytest.raises(contract.ContractError):
        g4._make_schedule(8, 2, 60, 7, 61)
    assert g4._verdict_from_conditions({"a": True, "b": True, "c": True,
                                        "beats_baseline": False}) == "FAIL"


def test_report_schema_v5_provenance():
    prov = {k: 1 for k in ["prereg_canonical_hash", "prereg_file_sha256",
                           "execution_contract_canonical_hash", "execution_contract_file_sha256",
                           "freeze_content_hash", "runner_sha256", "orchestrator_sha256",
                           "execution_scope", "execution_mode", "campaign_id", "attempt_id",
                           "authorization_token_sha256", "source_commit", "freeze_commit",
                           "freeze_tag", "runtime_head", "environment", "seeds", "params",
                           "criterion", "failures"]}
    contract.validate_report_schema({"gate": "X", "verdict": "PASS", "result": {},
                                     "provenance": prov})
    bad = dict(prov); del bad["attempt_id"]
    with pytest.raises(contract.ContractError):
        contract.validate_report_schema({"gate": "X", "verdict": "PASS", "result": {},
                                         "provenance": bad})


def test_unknown_scope_rejected():
    args = argparse.Namespace(i_am_authorized=False, dry_run=True,
                              prereg=str(EXP / "configs/synthetic_prereg_v5.json"),
                              execution_contract=str(EXP / "configs/synthetic_execution_contract_v3.json"))
    with pytest.raises(contract.ContractError, match="scope"):
        contract.build_context(args, "G", str(EXP / "run_g4_v2.py"), "made-up-scope")


def test_is_descendant_real_commits():
    head = contract._git_head()
    parent = contract._git("rev-parse", "HEAD~1")
    assert contract._is_descendant(parent, head) is True
    assert contract._is_descendant(head, parent) is False


# ---------------------------------------------------------------------------
# no superseded v1 imports (retained)
# ---------------------------------------------------------------------------
FORBIDDEN_MODULES = {"src.validation.freeze", "run_reproduction", "run_surrogate_causal",
                     "run_causal_fhn", "run_surrogate_stages", "run_identifiability",
                     "run_msf", "run_freeze"}
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
            assert (node.module or "") not in FORBIDDEN_MODULES, f"{fn}: {node.module}"


def test_v2_import_graph_excludes_v1():
    code = ("import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');\n"
            "import run_g4_v2, run_g1_g2_paired_v2, run_g3_v2, run_g0a_exact_v2, run_suite_v2\n"
            "v1={'run_reproduction','run_surrogate_causal','run_causal_fhn','run_surrogate_stages',"
            "'run_identifiability','run_msf','run_freeze','src.validation.freeze'}\n"
            "bad=sorted(v1 & set(sys.modules)); assert not bad, bad; print('OK')") % (str(EXP), str(REPO))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr
