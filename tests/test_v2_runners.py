"""P1.2 runner + execution-contract tests (non-vacuous)."""
import argparse
import ast
import json
from pathlib import Path

import pytest

from src.validation.freeze_v2 import build_manifest_v2

import _contract_v2 as contract
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4
import run_suite_v2 as suite

REPO = Path(__file__).resolve().parents[1]
EXP = REPO / "experiments"

# ---------------------------------------------------------------------------
# 1. No v2 runner/module imports a superseded v1 implementation.
# ---------------------------------------------------------------------------
FORBIDDEN_MODULES = {
    "src.validation.freeze",           # v1 non-executable freeze
    "run_reproduction", "run_surrogate_causal", "run_causal_fhn",
    "run_surrogate_stages", "run_identifiability", "run_msf", "run_freeze",
}
FORBIDDEN_FROM = {
    ("src.simulation.linear_surrogate", "build_basis_operator"),  # v1 signed-buggy
    ("src.simulation.linear_surrogate", "simulate_observed"),     # v1, no d_true
}
FORBIDDEN_NAMES = {"smooth_square_gamma"}  # v1 same-phase MSF drive

V2_FILES = [
    "run_g0a_exact_v2.py", "run_g0b_calibrated_v2.py", "run_g0c_msf_v2.py",
    "run_g1_g2_paired_v2.py", "run_g3_v2.py", "run_g4_v2.py", "run_suite_v2.py",
    "_contract_v2.py", "_repro_common_v2.py",
]
V2_SRC = [
    REPO / "src/simulation/surrogate_v2.py",
    REPO / "src/networks/paired_switching.py",
    REPO / "src/dynamics/msf_switching.py",
    REPO / "src/metrics/identifiability.py",
    REPO / "src/validation/freeze_v2.py",
]


@pytest.mark.parametrize("path", [EXP / f for f in V2_FILES] + V2_SRC)
def test_no_superseded_v1_imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name not in FORBIDDEN_MODULES, f"{path.name} imports {a.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in FORBIDDEN_MODULES, f"{path.name} from {mod}"
            for a in node.names:
                assert (mod, a.name) not in FORBIDDEN_FROM, f"{path.name}: {mod}.{a.name}"
                assert a.name not in FORBIDDEN_NAMES, f"{path.name} imports {a.name}"


# ---------------------------------------------------------------------------
# helpers: tiny fixtures
# ---------------------------------------------------------------------------
def _tiny_prereg():
    return {
        "tolerances": {"gamma_significance_std_mult": 3.0,
                       "sync_threshold_E12": 0.02, "sync_tail_frac": 0.25},
        "global": {"dt": 0.01},
        "seed_blocks": {"identifiability": [61, 62], "paired_causal": [41, 42],
                        "stages": [51], "g0c_msf": [31]},
        "surrogate_paired": {"N": 8, "N_IL": 2, "K": 3, "H": 24, "kappa": 0.6,
                             "rho_target": 1.04, "intra_coupling": 0.06,
                             "cycles_fast": 4, "cycles_intermediate": 2, "cycles_slow": 1,
                             "variable_dwell_multiset": [4, 8, 12], "best_static_search": 5,
                             "neg_fraction_signed": 0.4},
        "gates": {
            "G4_identifiability": {"N": 8, "N_IL": 2, "kappa": 0.6, "rho_target": 1.04,
                                   "intra_coupling": 0.06, "horizon_steps": 60,
                                   "dwell_fast": 6, "estimator_window": 8,
                                   "obs_noise": 0.05, "factor_scale": 1.0,
                                   "async_variants": [[1, 1]]},
            "G3_robustness": {"stages": [
                {"name": "faithful", "heterogeneity": 0.0, "directed": False, "signed": False},
                {"name": "signed", "heterogeneity": 0.0, "directed": False, "signed": True}]},
            "G0C_msf_minimal": {"N": 2, "lam_perp": 2.0, "alpha": 5.0, "n_steps": 400,
                                "transient_steps": 100, "renorm_every": 5,
                                "sigma_grid": [0.3], "T_swt_grid": [11.0]},
        },
    }


def _tiny_ctx(prereg, gate, out_dir):
    return contract.RunContext(
        gate=gate, runner_file="fixture", authorized=True, dry_run=False,
        out_dir=Path(out_dir), prereg_path=Path("fixture"), prereg=prereg,
        prereg_canonical_hash="canon", prereg_file_sha256="filesha",
        freeze_path=Path("fixture"), freeze_content_hash="freezehash",
        runner_sha256="runnersha", commit_sha="commit", environment={"python": "x"})


# ---------------------------------------------------------------------------
# 10. report schema
# ---------------------------------------------------------------------------
def test_report_schema_accepts_good_and_rejects_bad():
    good = {"gate": "X", "verdict": "PASS", "result": {},
            "provenance": {k: 1 for k in
                           ["prereg_canonical_hash", "prereg_file_sha256",
                            "execution_freeze_content_hash", "runner_sha256",
                            "commit_sha", "environment", "seeds", "params", "criterion"]}}
    contract.validate_report_schema(good)
    with pytest.raises(contract.ContractError):
        contract.validate_report_schema({"gate": "X", "verdict": "MAYBE",
                                         "result": {}, "provenance": good["provenance"]})
    with pytest.raises(contract.ContractError):
        contract.validate_report_schema({"gate": "X", "verdict": "PASS", "result": {},
                                         "provenance": {}})


# ---------------------------------------------------------------------------
# 3. G1-strict FAILs when fast does not beat comparators (verdict logic)
# ---------------------------------------------------------------------------
def test_paired_verdict_fails_when_below_band():
    assert g1g2._paired_verdict([-0.2, -0.25, -0.3], 0.05)[0] == "FAIL"
    assert g1g2._paired_verdict([0.2, 0.25, 0.3], 0.05)[0] == "PASS"
    assert g1g2._paired_verdict([0.001, -0.001, 0.0], 0.05)[0] == "TIE"


# ---------------------------------------------------------------------------
# end-to-end tiny: G1/G2 produces SEPARATE weak/strict/order verdicts
# ---------------------------------------------------------------------------
def test_g1_g2_end_to_end_tiny(tmp_path):
    ctx = _tiny_ctx(_tiny_prereg(), "G1_G2_paired", tmp_path)
    rep = g1g2.compute(ctx)
    contract.validate_report_schema(rep)
    r = rep["result"]
    assert set(["G1_weak", "G1_strict", "G2_order"]).issubset(r)
    assert r["G1_weak"]["verdict"] in {"PASS", "FAIL", "TIE"}
    assert r["G1_strict"]["verdict"] in {"PASS", "FAIL", "TIE"}


# ---------------------------------------------------------------------------
# 5. signed stage has negative weights (end-to-end tiny)
# ---------------------------------------------------------------------------
def test_g3_signed_has_negative_weights_tiny(tmp_path):
    ctx = _tiny_ctx(_tiny_prereg(), "G3_robustness", tmp_path)
    rep = g3.compute(ctx)
    meta = rep["result"]["by_stage"]["signed"]["operator_meta"]
    assert meta["n_negative_offdiag"] >= 1
    faithful = rep["result"]["by_stage"]["faithful"]["operator_meta"]
    assert faithful["n_negative_offdiag"] == 0


# ---------------------------------------------------------------------------
# 6. G4 end-to-end tiny produces same-realization contraction corr + schema
# ---------------------------------------------------------------------------
def test_g4_end_to_end_tiny(tmp_path):
    ctx = _tiny_ctx(_tiny_prereg(), "G4_identifiability", tmp_path)
    rep = g4.compute(ctx)
    contract.validate_report_schema(rep)
    sync = rep["result"]["by_async_variant"]["async_1_1"]
    assert "contraction_corr_same_realization" in sync
    assert rep["verdict"] in {"PASS", "FAIL"}


# ---------------------------------------------------------------------------
# G0C end-to-end tiny (anti-phase channels; not EXECUTION_INVALID)
# ---------------------------------------------------------------------------
def test_g0c_end_to_end_tiny(tmp_path):
    ctx = _tiny_ctx(_tiny_prereg(), "G0C_msf_minimal", tmp_path)
    rep = g0c.compute(ctx)
    assert rep["verdict"] != "EXECUTION_INVALID"  # channels ARE anti-phase in v2
    assert "psi_grid" in rep["result"]


# ---------------------------------------------------------------------------
# 7/8. wrong hash and no-auth are rejected BEFORE compute; no report written
# ---------------------------------------------------------------------------
def _args(**kw):
    base = dict(i_am_authorized=False, dry_run=False,
                prereg=str(REPO / "experiments/configs/synthetic_prereg_v2.json"),
                expect_prereg_canonical=None, expect_prereg_file_sha=None,
                freeze=str(REPO / "artifacts/freeze_execution_v2.json"),
                expect_freeze_content_hash=None, out_dir=str(REPO / "experiments/reports"))
    base.update(kw)
    return argparse.Namespace(**base)


_REAL_RUNNER = str(EXP / "run_g4_v2.py")


def test_no_auth_rejected():
    with pytest.raises(contract.ContractError):
        contract.build_context(_args(i_am_authorized=False), "G", _REAL_RUNNER)


def test_wrong_prereg_hash_rejected(tmp_path):
    args = _args(i_am_authorized=True, expect_prereg_canonical="deadbeef",
                 expect_prereg_file_sha="deadbeef",
                 expect_freeze_content_hash="deadbeef", out_dir=str(tmp_path))
    with pytest.raises(contract.ContractError):
        contract.build_context(args, "G", _REAL_RUNNER)
    assert not list(tmp_path.glob("*_v2.json"))  # no report written


def test_run_cli_wrong_hash_exit2_no_report(tmp_path):
    argv = ["--i-am-authorized", "--expect-prereg-canonical", "deadbeef",
            "--expect-prereg-file-sha", "deadbeef",
            "--expect-freeze-content-hash", "deadbeef", "--out-dir", str(tmp_path)]
    rc = contract.run_cli("G4", str(EXP / "run_g4_v2.py"),
                          g4.plan, g4.compute, "g4_identifiability_v2.json", argv=argv)
    assert rc == 2
    assert not list(tmp_path.glob("*_v2.json"))


# ---------------------------------------------------------------------------
# 9. atomic write: refuse overwrite and stale .tmp
# ---------------------------------------------------------------------------
def test_atomic_write_refuses_overwrite_and_bad_name(tmp_path):
    ctx = _tiny_ctx(_tiny_prereg(), "G", tmp_path)
    rep = {"gate": "G", "verdict": "PASS", "result": {}, "provenance": {}}
    contract.atomic_write_report(ctx, "x_v2.json", rep)
    with pytest.raises(contract.ContractError):
        contract.atomic_write_report(ctx, "x_v2.json", rep)          # overwrite
    with pytest.raises(contract.ContractError):
        contract.atomic_write_report(ctx, "bad_name.json", rep)      # wrong suffix
    (tmp_path / "y_v2.json.tmp").write_text("stale")
    with pytest.raises(contract.ContractError):
        contract.atomic_write_report(ctx, "y_v2.json", rep)          # stale .tmp


# ---------------------------------------------------------------------------
# 11. suite --dry-run executes nothing
# ---------------------------------------------------------------------------
def test_suite_dry_run_writes_nothing(tmp_path):
    rc = suite.main(["--dry-run", "--out-dir", str(tmp_path)])
    assert rc == 0
    assert not list(tmp_path.glob("*_v2.json"))


# ---------------------------------------------------------------------------
# 12. full end-to-end via run_cli with a tiny fixture prereg + real freeze
# ---------------------------------------------------------------------------
def test_run_cli_end_to_end_with_fixtures(tmp_path):
    import hashlib
    # tiny fixture prereg
    prereg = _tiny_prereg()
    preg_path = tmp_path / "tiny_prereg.json"
    preg_path.write_text(json.dumps(prereg))
    raw = preg_path.read_bytes()
    from src.validation.freeze_v2 import config_canonical_hash
    canon = config_canonical_hash(json.loads(raw))
    filesha = hashlib.sha256(raw).hexdigest()
    # fixture execution freeze over a trivial REAL file (verifies against REPO root)
    spec = {"roots": [], "files": ["python-version.txt"]}
    manifest = build_manifest_v2(REPO, spec, prereg, "experiments/configs/synthetic_prereg_v2.json")
    freeze_path = tmp_path / "fixture_freeze.json"
    freeze_path.write_text(json.dumps(manifest))
    argv = ["--i-am-authorized", "--prereg", str(preg_path),
            "--expect-prereg-canonical", canon, "--expect-prereg-file-sha", filesha,
            "--freeze", str(freeze_path),
            "--expect-freeze-content-hash", manifest["content_hash"],
            "--out-dir", str(tmp_path)]
    rc = contract.run_cli("G4", str(EXP / "run_g4_v2.py"),
                          g4.plan, g4.compute, "g4_identifiability_v2.json", argv=argv)
    assert rc == 0
    out = tmp_path / "g4_identifiability_v2.json"
    assert out.exists()
    rep = json.loads(out.read_text())
    contract.validate_report_schema(rep)
    assert rep["provenance"]["prereg_canonical_hash"] == canon
    assert rep["provenance"]["execution_freeze_content_hash"] == manifest["content_hash"]
