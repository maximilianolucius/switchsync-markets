"""Freeze v2 tampering tests (audit D1/D2/D3 repairs)."""
import json
import shutil

import pytest

from src.validation.freeze_v2 import (
    build_manifest_v2,
    compute_content_hash,
    verify_manifest_v2,
    write_manifest_atomic,
)

SPEC = {"roots": [{"dir": "src", "ext": [".py"]},
                  {"dir": "experiments", "ext": [".py"]},
                  {"dir": "tests", "ext": [".py"]}],
        "files": ["requirements.lock.txt", "cfg.json"]}


def _make_repo(root):
    (root / "src").mkdir()
    (root / "experiments").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "a.py").write_text("x = 1\n")
    (root / "experiments" / "run_x.py").write_text("y = 2\n")
    (root / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    (root / "requirements.lock.txt").write_text("numpy==2.4.4\n")
    (root / "cfg.json").write_text(json.dumps({"k": 1}))
    return {"k": 1}


def test_content_hash_stored_equals_recomputed(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    v = verify_manifest_v2(tmp_path, m)
    assert v["ok"] and v["content_hash_ok"]
    assert v["stored_content_hash"] == v["recomputed_content_hash"]


def test_tamper_file_detected(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    (tmp_path / "src" / "a.py").write_text("x = 999\n")   # tamper
    v = verify_manifest_v2(tmp_path, m)
    assert not v["ok"]
    assert "src/a.py" in v["mismatches"]


def test_runner_modification_detected(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    (tmp_path / "experiments" / "run_x.py").write_text("y = 3  # changed logic\n")
    v = verify_manifest_v2(tmp_path, m)
    assert not v["ok"] and "experiments/run_x.py" in v["mismatches"]


def test_added_executable_detected(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    (tmp_path / "src" / "evil.py").write_text("print('added after freeze')\n")
    v = verify_manifest_v2(tmp_path, m)
    assert not v["ok"]
    assert "src/evil.py" in v["added"]     # v1 could NOT detect this


def test_missing_file_detected(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    (tmp_path / "src" / "a.py").unlink()
    v = verify_manifest_v2(tmp_path, m)
    assert not v["ok"] and "src/a.py" in v["missing"]


def test_environment_mismatch_detected(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    # forge a manifest with a different env, keeping content-hash integrity intact
    m2 = dict(m)
    m2["environment"] = dict(m["environment"])
    m2["environment"]["python"] = "0.0.0-fake"
    body = {k: v for k, v in m2.items() if k != "content_hash"}
    m2["content_hash"] = compute_content_hash(body)
    v = verify_manifest_v2(tmp_path, m2)
    assert v["content_hash_ok"]            # integrity intact
    assert not v["environment_ok"]         # but env differs from the live one
    assert not v["ok"]


def test_content_hash_integrity_tamper(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    m["files"]["src/a.py"] = "0" * 64      # tamper a recorded hash without fixing content_hash
    v = verify_manifest_v2(tmp_path, m)
    assert not v["content_hash_ok"]        # stored != recomputed


def test_overwrite_refused(tmp_path):
    cfg = _make_repo(tmp_path)
    m = build_manifest_v2(tmp_path, SPEC, cfg, "cfg.json")
    out = tmp_path / "freeze.json"
    write_manifest_atomic(out, m)
    with pytest.raises(FileExistsError):
        write_manifest_atomic(out, m)


def test_path_independence_copied_repo(tmp_path):
    a = tmp_path / "repoA"; a.mkdir()
    cfg = _make_repo(a)
    m_a = build_manifest_v2(a, SPEC, cfg, "cfg.json")
    b = tmp_path / "repoB_different_path"
    shutil.copytree(a, b)
    m_b = build_manifest_v2(b, SPEC, cfg, "cfg.json")
    # git_commit may differ (no repo in tmp); compare the path-independent parts.
    assert m_a["files"] == m_b["files"]
    assert m_a["config_canonical_hash"] == m_b["config_canonical_hash"]
    # verifying A's manifest against the copied tree B succeeds (relative keys)
    v = verify_manifest_v2(b, m_a)
    assert not v["mismatches"] and not v["missing"] and not v["added"]
