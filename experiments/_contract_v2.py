"""Execution contract + custody for the v2 runners (P1.2-D).

Documents (defaults): scientific prereg v6 + execution contract v4 + freeze v6.

Identity (contract C/E):
  campaign_id = sha256(prereg_canonical | exec_canonical | freeze_content | freeze_commit)[:16]
  token_sha   = sha256(token_utf8)
  attempt_id  = sha256(campaign_id | execution_scope | token_sha)[:16]
The execution scope is CODE-DETERMINED (frozen vocabulary below), never operator
text. The authorization token is supplied with --authorization-token and recorded
ONLY as its SHA-256, never in clear.

Provenance (contract B): each report records the SHA of the scientific runner file
that computed it. The orchestrator SHA is set exclusively by run_suite_v2 through
`child_context()`; there is NO CLI argument to inject it. Individual runners record
orchestrator_sha256 = null and execution_mode = "individual:<gate>".

Custody (contract D): reports are written into the attempt's staging directory;
writing into a SEALED directory is refused; there is no overwrite/resume/retry
without the explicit frozen policy (prereg v5 custody section). Import-safe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from src.validation.freeze_v2 import config_canonical_hash, verify_manifest_v2  # noqa: E402

DEFAULT_PREREG = REPO_ROOT / "experiments" / "configs" / "synthetic_prereg_v6.json"
DEFAULT_EXEC = REPO_ROOT / "experiments" / "configs" / "synthetic_execution_contract_v4.json"
DEFAULT_FREEZE = REPO_ROOT / "artifacts" / "freeze_execution_v6.json"

VERDICTS = {"PASS", "FAIL", "INCONCLUSIVE", "EXECUTION_INVALID", "NOT_INTERPRETABLE"}
REASON_CODES = {"INCONCLUSIVE_BY_COST", "TIE", "NOT_SIGNIFICANT",
                "PARTIAL_NO_TSWT_DEPENDENCE", "PREREQ_FAIL", "STRESS_NOT_IMPLEMENTED",
                "G1_WEAK_NOT_PASS", "FAILED_RUNS"}
EXECUTION_SCOPES = {"cheap-suite", "full-suite", "g0a-only",
                    "individual:G0A", "individual:G0B", "individual:G0C",
                    "individual:G1G2", "individual:G3", "individual:G4"}


class ContractError(Exception):
    """Any execution-contract violation (exit code 2)."""


@dataclass(frozen=True)
class RunContext:
    """Immutable per-gate context. The suite derives child contexts with
    child_context(); contexts are never mutated and reused ambiguously."""
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
    execution_scope: str
    execution_mode: str
    freeze_content_hash: str | None = None
    source_commit: str | None = None
    freeze_commit: str | None = None
    freeze_tag: str | None = None
    runtime_head: str = "unknown"
    runner_sha256: str = ""
    orchestrator_sha256: str | None = None
    campaign_id: str | None = None
    attempt_id: str | None = None
    authorization_token_sha256: str | None = None
    environment: dict = field(default_factory=dict)


def child_context(ctx: RunContext, module_file: str,
                  orchestrator_file: str) -> RunContext:
    """Suite-only: derive an immutable per-gate context whose runner identity is
    the SCIENTIFIC module (not the orchestrator), with the orchestrator recorded
    separately. This is the ONLY way orchestrator_sha256 gets set."""
    return replace(ctx,
                   runner_file=str(module_file),
                   runner_sha256=_sha_file(module_file),
                   orchestrator_sha256=_sha_file(orchestrator_file))


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


def campaign_id_of(prereg_c, exec_c, freeze_c, freeze_commit) -> str:
    return hashlib.sha256(
        f"{prereg_c}|{exec_c}|{freeze_c}|{freeze_commit}".encode()).hexdigest()[:16]


def token_sha_of(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def attempt_id_of(campaign_id: str, scope: str, token_sha: str) -> str:
    """attempt_id = sha256(campaign_id | scope | token_sha). Uses the token SHA,
    NOT the raw token, so an auditor can recompute attempt_id from the recorded
    authorization_token_sha256 without ever seeing the token in clear."""
    return hashlib.sha256(f"{campaign_id}|{scope}|{token_sha}".encode()).hexdigest()[:16]


def validate_token(token) -> str:
    if not isinstance(token, str) or not token.strip():
        raise ContractError("authorization token must be a non-empty, non-whitespace string")
    return token


def structured_command(args, ctx: "RunContext", argv) -> dict:
    """Reconstructible command record: resolved interpreter + version, normalized
    argv (token value masked), resolved hashes/flags, scope, resolved run-dir. The
    token is NEVER stored in clear — only as <sha256:...>."""
    masked = []
    skip = False
    for i, a in enumerate(argv or []):
        if skip:
            masked.append(f"<sha256:{ctx.authorization_token_sha256}>")
            skip = False
            continue
        if a == "--authorization-token":
            masked.append(a)
            skip = True
        elif a.startswith("--authorization-token="):
            masked.append(f"--authorization-token=<sha256:{ctx.authorization_token_sha256}>")
        else:
            masked.append(a)
    return {
        "interpreter": sys.executable,
        "python_version": sys.version.split()[0],
        "argv_normalized": masked,
        "execution_scope": ctx.execution_scope,
        "run_dir_resolved": str(Path(args.run_dir).resolve()) if args.run_dir else None,
        "hashes": {"prereg_canonical": ctx.prereg_canonical_hash,
                   "prereg_file_sha256": ctx.prereg_file_sha256,
                   "execution_contract_canonical": ctx.execution_canonical_hash,
                   "execution_contract_file_sha256": ctx.execution_file_sha256,
                   "freeze_content_hash": ctx.freeze_content_hash},
        "authorization_token": f"<sha256:{ctx.authorization_token_sha256}>",
    }


def failure_record(exc: BaseException, seed, cell) -> dict:
    """Sanitized per-seed/cell failure capture (contract H): type + truncated
    message (no traceback, no paths), seed, cell, UTC timestamp."""
    msg = str(exc).replace(str(REPO_ROOT), "<repo>")[:200]
    return {"exception_type": type(exc).__name__, "message": msg,
            "seed": seed, "cell": cell,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()}


def _is_inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


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
    parser.add_argument("--authorization-token", default=None,
                        help="explicit authorization token; recorded ONLY as its SHA-256")
    # NOTE (contract B): there is deliberately NO --orchestrator-sha argument.


def _load(path_str):
    p = Path(path_str)
    if not p.exists():
        raise ContractError(f"document not found: {p}")
    raw = p.read_bytes()
    obj = json.loads(raw)
    return obj, config_canonical_hash(obj), hashlib.sha256(raw).hexdigest()


def build_context(args, gate: str, runner_file: str,
                  execution_scope: str) -> RunContext:
    """execution_scope is CODE-DETERMINED by the caller (runner module or suite),
    never operator-supplied text."""
    if execution_scope not in EXECUTION_SCOPES:
        raise ContractError(f"unknown execution scope: {execution_scope}")
    prereg, pc, pf = _load(args.prereg)
    ex, ec, ef = _load(args.execution_contract)
    base = dict(
        gate=gate, runner_file=str(runner_file), authorized=bool(args.i_am_authorized),
        dry_run=bool(args.dry_run), out_dir=Path("."), prereg=prereg,
        prereg_canonical_hash=pc, prereg_file_sha256=pf, execution=ex,
        execution_canonical_hash=ec, execution_file_sha256=ef,
        execution_scope=execution_scope, execution_mode=execution_scope,
        runtime_head=_git_head(), runner_sha256=_sha_file(runner_file),
        orchestrator_sha256=None, environment=_env())

    if args.dry_run:
        return RunContext(**base)

    if not args.i_am_authorized:
        raise ContractError("full run requires --i-am-authorized (or use --dry-run)")
    req = {"--expect-prereg-canonical": args.expect_prereg_canonical,
           "--expect-prereg-file-sha": args.expect_prereg_file_sha,
           "--expect-execution-contract-canonical": args.expect_execution_contract_canonical,
           "--expect-execution-contract-file-sha": args.expect_execution_contract_file_sha,
           "--expect-freeze-content-hash": args.expect_freeze_content_hash,
           "--expect-freeze-commit": args.expect_freeze_commit,
           "--expect-freeze-tag": args.expect_freeze_tag,
           "--run-dir": args.run_dir,
           "--authorization-token": args.authorization_token}
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

    if not _tree_clean():
        raise ContractError("working tree is not clean")
    head = base["runtime_head"]
    if head != args.expect_freeze_commit:
        raise ContractError(f"HEAD ({head}) != expected freeze_commit ({args.expect_freeze_commit})")
    deref = _deref_tag(args.expect_freeze_tag)
    if deref != args.expect_freeze_commit:
        raise ContractError(f"freeze_tag {args.expect_freeze_tag} derefs to {deref}, "
                            f"expected {args.expect_freeze_commit}")
    if _is_descendant(args.expect_freeze_commit, head):
        raise ContractError("HEAD is a descendant of freeze_commit; refuse to run off the freeze")

    freeze_path = Path(args.freeze)
    if not freeze_path.exists():
        raise ContractError(f"execution freeze not found: {freeze_path}")
    manifest = json.loads(freeze_path.read_text())
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    if not ver["ok"]:
        raise ContractError(f"execution freeze verification failed: {ver}")
    if manifest.get("content_hash") != args.expect_freeze_content_hash:
        raise ContractError("execution-freeze content hash mismatch")

    run_dir = Path(args.run_dir)
    if _is_inside_repo(run_dir):
        raise ContractError(f"--run-dir must be OUTSIDE the repo, got {run_dir}")

    token = validate_token(args.authorization_token)
    token_sha = token_sha_of(token)
    campaign = campaign_id_of(pc, ec, manifest["content_hash"], args.expect_freeze_commit)
    attempt = attempt_id_of(campaign, execution_scope, token_sha)
    base.update(freeze_content_hash=manifest["content_hash"],
                source_commit=manifest.get("git_commit"),
                freeze_commit=args.expect_freeze_commit,
                freeze_tag=args.expect_freeze_tag,
                campaign_id=campaign, attempt_id=attempt,
                authorization_token_sha256=token_sha,
                out_dir=run_dir / f"{attempt}.staging")
    return RunContext(**base)


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
        "execution_scope": ctx.execution_scope,
        "execution_mode": ctx.execution_mode,
        "campaign_id": ctx.campaign_id,
        "attempt_id": ctx.attempt_id,
        "authorization_token_sha256": ctx.authorization_token_sha256,
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
                "freeze_content_hash", "runner_sha256", "orchestrator_sha256",
                "execution_scope", "execution_mode", "campaign_id", "attempt_id",
                "authorization_token_sha256", "source_commit", "freeze_commit",
                "freeze_tag", "runtime_head", "environment", "seeds", "params",
                "criterion", "failures"}
    pm = prov_req - set(report.get("provenance", {}))
    if pm:
        raise ContractError(f"provenance missing fields: {pm}")
    rc = report.get("provenance", {}).get("reason_code")
    if rc is not None and rc not in REASON_CODES:
        raise ContractError(f"invalid reason_code: {rc}")
    # validate the STRUCTURE of each failure record (not just field existence)
    fr_req = {"exception_type", "message", "seed", "cell", "timestamp_utc"}
    for i, f in enumerate(report["provenance"].get("failures", [])):
        if not isinstance(f, dict) or not fr_req.issubset(f):
            raise ContractError(f"malformed failure record at index {i}: {f}")


def fsync_path(p: Path) -> None:
    fd = os.open(str(p), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
    out_dir = Path(ctx.out_dir)
    if (out_dir / "SEALED").exists():
        raise ContractError(f"attempt is SEALED; refusing any further write: {out_dir}")
    out = out_dir / name
    if out.exists():
        raise ContractError(f"refusing to overwrite existing report (no resume/retry policy): {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(out, report)
    return out


def run_cli(gate: str, runner_file: str, plan_fn, compute_fn, report_name: str,
            execution_scope: str, argv=None) -> int:
    """Entry point for an INDIVIDUAL gate runner. Publishes its own sealed
    single-report attempt bundle (contract C/D)."""
    import _custody

    parser = argparse.ArgumentParser(description=f"v2 runner: {gate}")
    add_common_args(parser)
    args = parser.parse_args(argv)
    try:
        ctx = build_context(args, gate, runner_file, execution_scope)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2
    if ctx.dry_run:
        print(json.dumps({"gate": gate, "dry_run": True, "wrote_report": False,
                          "plan": plan_fn(ctx)}, indent=2, default=str))
        return 0

    run_dir = Path(args.run_dir)
    lock = _custody.AttemptLock(run_dir, ctx.attempt_id)
    if not lock.acquire():
        print(f"CONTRACT ERROR: attempt {ctx.attempt_id} already running (lock held)",
              file=sys.stderr)
        return 2
    started = _custody.utc_now()
    try:
        if _custody.final_dir(run_dir, ctx.attempt_id).exists():
            print(f"CONTRACT ERROR: attempt already published: {ctx.attempt_id}",
                  file=sys.stderr)
            return 2
        staging = _custody.staging_dir(run_dir, ctx.attempt_id)
        if staging.exists() or _custody.interrupted_dir(run_dir, ctx.attempt_id).exists():
            print("CONTRACT ERROR: prior staging/interrupted state exists. An "
                  ".interrupted attempt is TERMINAL and is never resumed or mixed; a "
                  "new run needs a new authorization token (new attempt_id) and starts "
                  "from scratch (frozen policy).", file=sys.stderr)
            return 2
        staging.mkdir(parents=True)
        try:
            report = compute_fn(ctx)
            validate_report_schema(report)
            out = atomic_write_report(ctx, report_name, report)
        except ContractError as e:
            _custody.write_failure_ledger(run_dir, ctx.attempt_id,
                                          [{"gate": gate, "error": str(e)[:200]}])
            _custody.mark_interrupted(run_dir, ctx.attempt_id)
            print(f"CONTRACT ERROR: {e}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            _custody.mark_interrupted(run_dir, ctx.attempt_id)
            print("INTERRUPTED: staging preserved as .interrupted (terminal; no retry)",
                  file=sys.stderr)
            return 130
        except Exception as e:
            _custody.write_failure_ledger(run_dir, ctx.attempt_id,
                                          [failure_record(e, None, gate)])
            _custody.mark_interrupted(run_dir, ctx.attempt_id)
            print(f"EXECUTION ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        roles = {report_name: "report"}
        if (Path(ctx.out_dir) / "g0a_checkpoint.jsonl").exists():
            roles["g0a_checkpoint.jsonl"] = "checkpoint"
        inv = _custody.inventory_staging(staging, roles)
        manifest = _custody.build_attempt_manifest(
            campaign_id=ctx.campaign_id, attempt_id=ctx.attempt_id,
            execution_scope=ctx.execution_scope,
            hashes={"prereg_canonical": ctx.prereg_canonical_hash,
                    "prereg_file_sha256": ctx.prereg_file_sha256,
                    "execution_contract_canonical": ctx.execution_canonical_hash,
                    "execution_contract_file_sha256": ctx.execution_file_sha256,
                    "freeze_content_hash": ctx.freeze_content_hash},
            head=ctx.runtime_head, tag=ctx.freeze_tag,
            structured_command=structured_command(args, ctx, argv or sys.argv[1:]),
            runner_shas={gate: ctx.runner_sha256}, orchestrator_sha=None,
            authorization_token_sha256=ctx.authorization_token_sha256,
            started_utc=started, ended_utc=_custody.utc_now(), exit_status=0,
            artifacts=inv, gate_verdicts={gate: report["verdict"]},
            environment=ctx.environment)
        _custody.seal_and_publish(staging, _custody.final_dir(run_dir, ctx.attempt_id),
                                  manifest)
        print(f"published sealed attempt {ctx.attempt_id} verdict={report['verdict']}")
        return 0
    finally:
        lock.release()
