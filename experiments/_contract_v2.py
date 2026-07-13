"""Execution contract shared by all v2 runners (P1.2).

Guarantees per the P1.2 brief:
  * a full run requires --i-am-authorized AND the exact prereg canonical hash,
    prereg file SHA, and execution-freeze content hash;
  * the execution freeze is verified BEFORE any computation;
  * reports are *_v2.json, atomic, refuse to overwrite (and refuse a stale .tmp);
  * every report carries full provenance;
  * verdict is one of {PASS, FAIL, INCONCLUSIVE, EXECUTION_INVALID};
  * any contract failure exits nonzero and writes NO report;
  * import-safe: nothing runs on import.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from src.validation.freeze_v2 import (  # noqa: E402
    config_canonical_hash,
    verify_manifest_v2,
)

DEFAULT_PREREG = REPO_ROOT / "experiments" / "configs" / "synthetic_prereg_v2.json"
DEFAULT_FREEZE = REPO_ROOT / "artifacts" / "freeze_execution_v2.json"
DEFAULT_OUT = REPO_ROOT / "experiments" / "reports"

VERDICTS = {"PASS", "FAIL", "INCONCLUSIVE", "EXECUTION_INVALID"}


class ContractError(Exception):
    """Raised on any execution-contract violation (exit code 2)."""


@dataclass
class RunContext:
    gate: str
    runner_file: str
    authorized: bool
    dry_run: bool
    out_dir: Path
    prereg_path: Path
    prereg: dict
    prereg_canonical_hash: str
    prereg_file_sha256: str
    freeze_path: Path
    freeze_content_hash: str | None
    runner_sha256: str
    commit_sha: str
    environment: dict


def _sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _env() -> dict:
    mods = {}
    for n in ("numpy", "scipy", "matplotlib"):
        try:
            mods[n] = getattr(__import__(n), "__version__", "unknown")
        except Exception:
            mods[n] = "absent"
    return {"python": sys.version.split()[0],
            "platform": platform.platform(), "packages": mods}


def _native(o):
    if isinstance(o, dict):
        return {k: _native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_native(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return _native(o.tolist())
    return o


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--i-am-authorized", action="store_true",
                        help="required for a full (non-dry-run) execution")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and projected cost; execute nothing")
    parser.add_argument("--prereg", default=str(DEFAULT_PREREG))
    parser.add_argument("--expect-prereg-canonical", default=None)
    parser.add_argument("--expect-prereg-file-sha", default=None)
    parser.add_argument("--freeze", default=str(DEFAULT_FREEZE))
    parser.add_argument("--expect-freeze-content-hash", default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))


def build_context(args, gate: str, runner_file: str) -> RunContext:
    prereg_path = Path(args.prereg)
    if not prereg_path.exists():
        raise ContractError(f"prereg not found: {prereg_path}")
    raw = prereg_path.read_bytes()
    prereg = json.loads(raw)
    canon = config_canonical_hash(prereg)
    filesha = hashlib.sha256(raw).hexdigest()
    ctx = RunContext(
        gate=gate, runner_file=str(runner_file),
        authorized=bool(args.i_am_authorized), dry_run=bool(args.dry_run),
        out_dir=Path(args.out_dir), prereg_path=prereg_path, prereg=prereg,
        prereg_canonical_hash=canon, prereg_file_sha256=filesha,
        freeze_path=Path(args.freeze), freeze_content_hash=None,
        runner_sha256=_sha_file(runner_file), commit_sha=_git_commit(),
        environment=_env())

    if args.dry_run:
        return ctx  # dry-run: no auth/hash requirement, no computation

    # ---- full-run gate: auth + exact hashes + freeze verification ----
    if not args.i_am_authorized:
        raise ContractError("full run requires --i-am-authorized (or use --dry-run)")
    if (args.expect_prereg_canonical is None or args.expect_prereg_file_sha is None
            or args.expect_freeze_content_hash is None):
        raise ContractError("full run requires --expect-prereg-canonical, "
                            "--expect-prereg-file-sha and --expect-freeze-content-hash")
    if args.expect_prereg_canonical != canon:
        raise ContractError(
            f"prereg canonical hash mismatch: expected {args.expect_prereg_canonical}, got {canon}")
    if args.expect_prereg_file_sha != filesha:
        raise ContractError("prereg file SHA-256 mismatch")
    if not ctx.freeze_path.exists():
        raise ContractError(f"execution freeze not found: {ctx.freeze_path}")
    manifest = json.loads(ctx.freeze_path.read_text())
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    if not ver["ok"]:
        raise ContractError(f"execution freeze verification failed: {ver}")
    if manifest.get("content_hash") != args.expect_freeze_content_hash:
        raise ContractError("execution-freeze content hash mismatch")
    ctx.freeze_content_hash = manifest["content_hash"]
    return ctx


def provenance(ctx: RunContext, seeds, params, criterion) -> dict:
    return {
        "prereg_canonical_hash": ctx.prereg_canonical_hash,
        "prereg_file_sha256": ctx.prereg_file_sha256,
        "execution_freeze_content_hash": ctx.freeze_content_hash,
        "runner_sha256": ctx.runner_sha256,
        "commit_sha": ctx.commit_sha,
        "environment": ctx.environment,
        "seeds": list(seeds),
        "params": params,
        "criterion": criterion,
    }


def validate_report_schema(report: dict) -> None:
    required = {"gate", "verdict", "provenance", "result"}
    missing = required - set(report)
    if missing:
        raise ContractError(f"report missing top-level fields: {missing}")
    if report["verdict"] not in VERDICTS:
        raise ContractError(f"invalid verdict: {report['verdict']}")
    prov_req = {"prereg_canonical_hash", "prereg_file_sha256",
                "execution_freeze_content_hash", "runner_sha256", "commit_sha",
                "environment", "seeds", "params", "criterion"}
    pm = prov_req - set(report.get("provenance", {}))
    if pm:
        raise ContractError(f"provenance missing fields: {pm}")


def atomic_write_report(ctx: RunContext, name: str, report: dict) -> Path:
    if not name.endswith("_v2.json"):
        raise ContractError(f"report name must end with _v2.json: {name}")
    out = ctx.out_dir / name
    tmp = out.with_suffix(out.suffix + ".tmp")
    if out.exists():
        raise ContractError(f"refusing to overwrite existing report: {out}")
    if tmp.exists():
        raise ContractError(f"refusing to run over a stale .tmp: {tmp}")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(json.dumps(_native(report), indent=2, sort_keys=True))
        tmp.replace(out)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    return out


def run_cli(gate: str, runner_file: str, plan_fn, compute_fn, report_name: str,
            argv=None) -> int:
    """Standard entry point for a gate runner.

    plan_fn(ctx) -> dict describing the plan and projected cost (dry-run).
    compute_fn(ctx) -> a full report dict (must include gate/verdict/provenance/result).
    Returns an exit code (0 ok; 1 execution error; 2 contract error).
    """
    parser = argparse.ArgumentParser(description=f"v2 runner: {gate}")
    add_common_args(parser)
    args = parser.parse_args(argv)
    try:
        ctx = build_context(args, gate, runner_file)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2
    if ctx.dry_run:
        print(json.dumps({"gate": gate, "dry_run": True, "wrote_report": False,
                          "plan": plan_fn(ctx)}, indent=2, default=str))
        return 0
    try:
        report = compute_fn(ctx)
        validate_report_schema(report)
        out = atomic_write_report(ctx, report_name, report)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # science/runtime failure
        print(f"EXECUTION ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"wrote {out}  verdict={report['verdict']}")
    return 0
