"""P1.2-F integration tests that consume the REAL active documents (prereg v8 +
execution contract v6), NOT reconstructed fixtures. These would have caught the
missing `tolerances` block that made freeze v7 non-executable."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

import _contract_v2 as contract
import run_g0a_exact_v2 as g0a
import run_g0b_calibrated_v2 as g0b
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "experiments" / "configs"
PREREG_V8 = CFG / "synthetic_prereg_v8.json"
EXEC_V6 = CFG / "synthetic_execution_contract_v6.json"
PREREG_V7 = CFG / "synthetic_prereg_v7.json"
EXEC_V5 = CFG / "synthetic_execution_contract_v5.json"

RUNNERS = {
    "run_g0a_exact_v2.py": g0a, "run_g0b_calibrated_v2.py": g0b,
    "run_g0c_msf_v2.py": g0c, "run_g1_g2_paired_v2.py": g1g2,
    "run_g3_v2.py": g3, "run_g4_v2.py": g4,
}


def _dry_run_ctx(prereg=PREREG_V8, execution=EXEC_V6, gate="G0A_exact_reproduction",
                 runner=None, scope="full-suite"):
    parser = argparse.ArgumentParser()
    contract.add_common_args(parser)
    args = parser.parse_args(["--dry-run", "--prereg", str(prereg),
                              "--execution-contract", str(execution)])
    return contract.build_context(args, gate, runner or g0a.__file__, scope)


# ---- B.1: prereg v8 contains exactly the two restored tolerances -----------
def test_prereg_v8_has_exact_tolerances():
    p = json.loads(PREREG_V8.read_text())
    assert p["tolerances"] == {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25}


# ---- B.2 + B.3: a real dry-run context and plan() for every gate -----------
def test_real_dryrun_context_and_all_gate_plans():
    ctx = _dry_run_ctx()
    assert ctx.dry_run and ctx.prereg["tolerances"]["sync_threshold_E12"] == 0.02
    for mod in (g0a, g0b, g0c, g1g2, g3, g4):
        plan = mod.plan(ctx)                     # must not raise KeyError
        assert isinstance(plan, dict) and plan.get("gate") == mod.GATE


# ---- B.4: every runner --dry-run by subprocess exits 0 ---------------------
@pytest.mark.parametrize("script", list(RUNNERS))
def test_runner_dry_run_subprocess_exit_zero(script):
    r = subprocess.run([sys.executable, str(REPO / "experiments" / script), "--dry-run"],
                       cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, f"{script}: rc={r.returncode}\n{r.stderr}"


# ---- B.5: run_suite_v2.py --plan exits 0 with the real defaults ------------
def test_suite_plan_subprocess_exit_zero():
    r = subprocess.run([sys.executable, str(REPO / "experiments" / "run_suite_v2.py"), "--plan"],
                       cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stderr}"
    payload = json.loads(r.stdout)
    assert payload["mode"] == "plan" and payload["wrote_reports"] is False


# ---- B.6: regression — v7 breaks, v8 works ---------------------------------
def test_v7_suite_plan_fails_v8_succeeds():
    r7 = subprocess.run([sys.executable, str(REPO / "experiments" / "run_suite_v2.py"),
                         "--plan", "--prereg", str(PREREG_V7),
                         "--execution-contract", str(EXEC_V5)],
                        cwd=str(REPO), capture_output=True, text=True)
    assert r7.returncode != 0                      # freeze v7 was NON-EXECUTABLE
    assert "tolerances" in r7.stderr or "KeyError" in r7.stderr

    r8 = subprocess.run([sys.executable, str(REPO / "experiments" / "run_suite_v2.py"),
                         "--plan", "--prereg", str(PREREG_V8),
                         "--execution-contract", str(EXEC_V6)],
                        cwd=str(REPO), capture_output=True, text=True)
    assert r8.returncode == 0, r8.stderr


def test_v7_g0a_plan_raises_keyerror_directly():
    with pytest.raises(KeyError):
        g0a.plan(_dry_run_ctx(prereg=PREREG_V7, execution=EXEC_V5))


# ---- B.7: the ONLY scientific change v7 -> v8 is the tolerances restoration -
def test_only_scientific_change_is_tolerances():
    v7 = json.loads(PREREG_V7.read_text())
    v8 = json.loads(PREREG_V8.read_text())
    meta = {"contract_name", "contract_version", "supersedes", "description", "lineage"}
    differing = {k for k in set(v7) | set(v8) if v7.get(k) != v8.get(k)}
    assert differing - meta == {"tolerances"}, differing - meta
    assert "tolerances" not in v7
    assert v8["tolerances"] == {"sync_threshold_E12": 0.02, "sync_tail_frac": 0.25}
    # every non-meta, non-tolerances key is byte-identical
    for k in set(v7) - meta:
        assert v7[k] == v8[k], f"unexpected change in {k}"


# ---- execution contract v6 is parameter-identical to v5 except the binding -
def test_exec_v6_only_rebinds():
    e5 = json.loads(EXEC_V5.read_text())
    e6 = json.loads(EXEC_V6.read_text())
    meta = {"contract_name", "contract_version", "binds_prereg",
            "binds_prereg_canonical_hash", "description"}
    differing = {k for k in set(e5) | set(e6) if e5.get(k) != e6.get(k)}
    assert differing <= meta, differing
