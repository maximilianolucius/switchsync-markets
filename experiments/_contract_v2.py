"""Execution contract + custody for the v2 runners (P1.2 / P1.2-A / P1.2-B).

Two authoritative documents (defaults): the scientific prereg (synthetic_prereg_v4)
and the operational execution contract (synthetic_execution_contract_v2). A full
run also requires the execution freeze (freeze_execution_v4) and an EXTERNAL
--run-dir (never inside the frozen repo).

Full-run preflight (all required, checked BEFORE any computation):
  --i-am-authorized;
  exact prereg canonical+file SHA and execution-contract canonical+file SHA;
  exact freeze content hash; freeze IDENTITY (clean tree, HEAD==freeze_commit,
  freeze_tag derefs to freeze_commit, HEAD not a descendant); manifest verify
  (files + environment); an EXTERNAL run-dir; and the target report must not exist
  (no silent overwrite/resume/retry).

Outputs are written under <run-dir>/<run_id>/, where run_id is derived from the
hashes, so scientific results NEVER land inside the frozen repo. Reports are
*_v2.json, atomic (temp+fsync+rename), and carry full provenance including the
scientific runner SHA, the orchestrator SHA (if a suite drove it), run_id, and the
source/freeze/runtime commits. Import-safe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from src.validation.freeze_v2 import config_canonical_hash, verify_manifest_v2  # noqa: E402

DEFAULT_PREREG = REPO_ROOT / "experiments" / "configs" / "synthetic_prereg_v4.json"
DEFAULT_EXEC = REPO_ROOT / "experiments" / "configs" / "synthetic_execution_contract_v2.json"
DEFAULT_FREEZE = REPO_ROOT / "artifacts" / "freeze_execution_v4.json"

VERDICTS = {"PASS", "FAIL", "INCONCLUSIVE", "EXECUTION_INVALID", "NOT_INTERPRETABLE"}
REASON_CODES = {"INCONCLUSIVE_BY_COST", "TIE", "NOT_SIGNIFICANT",
                "PARTIAL_NO_TSWT_DEPENDENCE", "PREREQ_FAIL", "STRESS_NOT_IMPLEMENTED",
                "G1_WEAK_NOT_PASS", "FAILED_RUNS"}


class ContractError(Exception):
    """Any execution-contract violation (exit code 2)."""


@dataclass
class RunContext:
    gate: str
    runner_file: str
    authorized: bool
    dry_run: bool
    out_dir: Path
    prereg: dict
    prereg_canonical_hash: str
    prereg_file_sha256: str
    execution: dict
    execution_canonical_hash: str
    execution_file_sha256: str
    freeze_content_hash: str | None = None
    source_commit: str | None = None
    freeze_commit: str | None = None
    freeze_tag: str | None = None
    runtime_head: str = "unknown"
    runner_sha256: str = ""
    orchestrator_sha256: str | None = None
    run_id: str | None = None
    environment: dict = field(default_factory=dict)


def _sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _git(*args) -> str:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


def _git_head() -> str:
    try:
        return _git("rev-parse", "HEAD")
    except Exception:
        return "unknown"


def _tree_clean() -> bool:
    try:
        return _git("status", "--porcelain") == ""
    except Exception:
        return False


def _deref_tag(tag: str) -> str | None:
    try:
        return _git("rev-parse", f"{tag}^{{commit}}")
    except Exception:
        return None


def _is_descendant(ancestor: str, desc: str) -> bool:
    if ancestor == desc:
        return False
    try:
        subprocess.check_call(["git", "-C", str(REPO_ROOT), "merge-base",
                               "--is-ancestor", ancestor, desc],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


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


def _run_id(prereg_c, exec_c, freeze_c, freeze_commit) -> str:
    return hashlib.sha256(
        f"{prereg_c}|{exec_c}|{freeze_c}|{freeze_commit}".encode()).hexdigest()[:16]


def _is_inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


def fsync_path(p: Path) -> None:
    fd = os.open(str(p), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--i-am-authorized", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prereg", default=str(DEFAULT_PREREG))
    parser.add_argument("--execution-contract", default=str(DEFAULT_EXEC))
    parser.add_argument("--expect-prereg-canonical", default=None)
    parser.add_argument("--expect-prereg-file-sha", default=None)
    parser.add_argument("--expect-execution-contract-canonical", default=None)
    parser.add_argument("--expect-execution-contract-file-sha", default=None)
    parser.add_argument("--freeze", default=str(DEFAULT_FREEZE))
    parser.add_argument("--expect-freeze-content-hash", default=None)
    parser.add_argument("--expect-freeze-commit", default=None)
    parser.add_argument("--expect-freeze-tag", default=None)
    parser.add_argument("--run-dir", default=None,
                        help="EXTERNAL output directory (must be outside the repo)")
    parser.add_argument("--orchestrator-sha", default=None,
                        help="SHA of the suite orchestrator, recorded in reports it drives")


def _load(path_str):
    p = Path(path_str)
    if not p.exists():
        raise ContractError(f"document not found: {p}")
    raw = p.read_bytes()
    obj = json.loads(raw)
    return obj, config_canonical_hash(obj), hashlib.sha256(raw).hexdigest()


def build_context(args, gate: str, runner_file: str) -> RunContext:
    prereg, pc, pf = _load(args.prereg)
    ex, ec, ef = _load(args.execution_contract)
    ctx = RunContext(
        gate=gate, runner_file=str(runner_file), authorized=bool(args.i_am_authorized),
        dry_run=bool(args.dry_run), out_dir=Path("."), prereg=prereg,
        prereg_canonical_hash=pc, prereg_file_sha256=pf, execution=ex,
        execution_canonical_hash=ec, execution_file_sha256=ef,
        runtime_head=_git_head(), runner_sha256=_sha_file(runner_file),
        orchestrator_sha256=getattr(args, "orchestrator_sha", None), environment=_env())

    if args.dry_run:
        return ctx

    # ---- documents ----
    if not args.i_am_authorized:
        raise ContractError("full run requires --i-am-authorized (or use --dry-run)")
    req = {"--expect-prereg-canonical": args.expect_prereg_canonical,
           "--expect-prereg-file-sha": args.expect_prereg_file_sha,
           "--expect-execution-contract-canonical": args.expect_execution_contract_canonical,
           "--expect-execution-contract-file-sha": args.expect_execution_contract_file_sha,
           "--expect-freeze-content-hash": args.expect_freeze_content_hash,
           "--expect-freeze-commit": args.expect_freeze_commit,
           "--expect-freeze-tag": args.expect_freeze_tag,
           "--run-dir": args.run_dir}
    missing = [k for k, v in req.items() if v is None]
    if missing:
        raise ContractError(f"full run requires: {', '.join(missing)}")
    if args.expect_prereg_canonical != pc:
        raise ContractError(f"prereg canonical mismatch: expected {args.expect_prereg_canonical}, got {pc}")
    if args.expect_prereg_file_sha != pf:
        raise ContractError("prereg file SHA mismatch")
    if args.expect_execution_contract_canonical != ec:
        raise ContractError("execution-contract canonical mismatch")
    if args.expect_execution_contract_file_sha != ef:
        raise ContractError("execution-contract file SHA mismatch")
    if ex.get("binds_prereg_canonical_hash") not in (None, pc):
        raise ContractError("execution contract binds a different prereg canonical hash")

    # ---- freeze identity ----
    if not _tree_clean():
        raise ContractError("working tree is not clean")
    head = ctx.runtime_head
    if head != args.expect_freeze_commit:
        raise ContractError(f"HEAD ({head}) != expected freeze_commit ({args.expect_freeze_commit})")
    deref = _deref_tag(args.expect_freeze_tag)
    if deref != args.expect_freeze_commit:
        raise ContractError(f"freeze_tag {args.expect_freeze_tag} derefs to {deref}, expected {args.expect_freeze_commit}")
    if _is_descendant(args.expect_freeze_commit, head):
        raise ContractError("HEAD is a descendant of freeze_commit; refuse to run off the freeze")

    # ---- freeze manifest (files + environment) ----
    freeze_path = Path(args.freeze)
    if not freeze_path.exists():
        raise ContractError(f"execution freeze not found: {freeze_path}")
    manifest = json.loads(freeze_path.read_text())
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    if not ver["ok"]:
        raise ContractError(f"execution freeze verification failed: {ver}")
    if manifest.get("content_hash") != args.expect_freeze_content_hash:
        raise ContractError("execution-freeze content hash mismatch")

    # ---- external run-dir + run_id + no-overwrite ----
    run_dir = Path(args.run_dir)
    if _is_inside_repo(run_dir):
        raise ContractError(f"--run-dir must be OUTSIDE the repo, got {run_dir}")
    ctx.freeze_content_hash = manifest["content_hash"]
    ctx.source_commit = manifest.get("git_commit")
    ctx.freeze_commit = args.expect_freeze_commit
    ctx.freeze_tag = args.expect_freeze_tag
    ctx.run_id = _run_id(pc, ec, ctx.freeze_content_hash, ctx.freeze_commit)
    # out_dir is created lazily on first write (atomic_write_report), so a suite can
    # publish a fresh <run_id> dir by atomic rename from staging without colliding.
    ctx.out_dir = run_dir / ctx.run_id
    return ctx


def provenance(ctx: RunContext, seeds, params, criterion, reason_code=None,
               failures=None) -> dict:
    prov = {
        "prereg_canonical_hash": ctx.prereg_canonical_hash,
        "prereg_file_sha256": ctx.prereg_file_sha256,
        "execution_contract_canonical_hash": ctx.execution_canonical_hash,
        "execution_contract_file_sha256": ctx.execution_file_sha256,
        "freeze_content_hash": ctx.freeze_content_hash,
        "runner_sha256": ctx.runner_sha256,
        "orchestrator_sha256": ctx.orchestrator_sha256,
        "run_id": ctx.run_id,
        "source_commit": ctx.source_commit,
        "freeze_commit": ctx.freeze_commit,
        "freeze_tag": ctx.freeze_tag,
        "runtime_head": ctx.runtime_head,
        "environment": ctx.environment,
        "seeds": list(seeds) if not isinstance(seeds, dict) else seeds,
        "params": params,
        "criterion": criterion,
        "failures": failures or [],
    }
    if reason_code is not None:
        prov["reason_code"] = reason_code
    return prov


def validate_report_schema(report: dict) -> None:
    required = {"gate", "verdict", "provenance", "result"}
    missing = required - set(report)
    if missing:
        raise ContractError(f"report missing top-level fields: {missing}")
    if report["verdict"] not in VERDICTS:
        raise ContractError(f"invalid verdict: {report['verdict']}")
    prov_req = {"prereg_canonical_hash", "prereg_file_sha256",
                "execution_contract_canonical_hash", "execution_contract_file_sha256",
                "freeze_content_hash", "runner_sha256", "orchestrator_sha256", "run_id",
                "source_commit", "freeze_commit", "freeze_tag", "runtime_head",
                "environment", "seeds", "params", "criterion", "failures"}
    pm = prov_req - set(report.get("provenance", {}))
    if pm:
        raise ContractError(f"provenance missing fields: {pm}")
    rc = report.get("provenance", {}).get("reason_code")
    if rc is not None and rc not in REASON_CODES:
        raise ContractError(f"invalid reason_code: {rc}")


def _atomic_write(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        raise ContractError(f"refusing to run over a stale .tmp: {tmp}")
    with open(tmp, "w") as fh:
        json.dump(_native(obj), fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fsync_path(path.parent)


def atomic_write_report(ctx: RunContext, name: str, report: dict) -> Path:
    if not name.endswith("_v2.json"):
        raise ContractError(f"report name must end with _v2.json: {name}")
    out = ctx.out_dir / name
    if out.exists():
        raise ContractError(f"refusing to overwrite existing report (no resume/retry policy): {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(out, report)
    return out


def run_cli(gate: str, runner_file: str, plan_fn, compute_fn, report_name: str,
            argv=None) -> int:
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
    except Exception as e:
        print(f"EXECUTION ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"wrote {out}  verdict={report['verdict']}")
    return 0
