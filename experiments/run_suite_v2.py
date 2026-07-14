"""Transactional suite orchestrator (P1.2-C).

Scopes (contract C, code-determined): default/--cheap-only -> "cheap-suite";
--include-g0a-expensive -> "full-suite"; --g0a-only -> "g0a-only". Contradictory
flag combinations are rejected. attempt_id = sha256(campaign_id | scope | auth
token)[:16], so cheap-suite and g0a-only coexist under one campaign_id with
different attempt_ids.

Provenance (contract B): before each gate the suite derives an IMMUTABLE child
context via child_context(ctx, m.__file__, __file__), so every report records the
scientific runner's real SHA and the suite's own SHA separately. There is no CLI
argument to inject an orchestrator SHA.

Transaction (contracts B/C/D): reports are written to
<run-dir>/<attempt_id>.staging/. On FULL success the attempt manifest (which
inventories every artifact and carries its own content hash) and the SEALED marker
are written INTO staging, fsynced and fully validated, and only THEN published by a
SINGLE atomic rename staging -> <run-dir>/<attempt_id>/ (no final-without-SEAL
window), followed by post-rename re-verification. If pre-rename validation fails,
`final` is never created; if the exceptional post-rename re-verification fails, the
directory is moved to <attempt_id>.invalid (never left as a successful attempt). On a
gate-invalid result OR any custody failure a failure ledger is written and staging is
preserved as .interrupted; NO success bundle is published. There is NO resume: an
.interrupted attempt is TERMINAL, a new run needs a new authorization token (a
different attempt_id) and starts from scratch, and the checkpoint is EVIDENCE, not a
resume input. An flock prevents concurrent executions of the same attempt_id.
Import-safe."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import _custody
from _contract_v2 import (
    ContractError,
    add_common_args,
    atomic_write_report,
    build_context,
    child_context,
    failure_record,
    structured_command,
    validate_report_schema,
)

import run_g0a_exact_v2 as g0a
import run_g0b_calibrated_v2 as g0b
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4

CHEAP = [g0b, g0c, g1g2, g3, g4]


def _scope_from_flags(args) -> str:
    flags = [bool(args.cheap_only), bool(args.include_g0a_expensive), bool(args.g0a_only)]
    if sum(flags) > 1:
        raise ContractError("contradictory flags: choose ONE of --cheap-only / "
                            "--include-g0a-expensive / --g0a-only")
    if args.include_g0a_expensive:
        return "full-suite"
    if args.g0a_only:
        return "g0a-only"
    return "cheap-suite"      # default and --cheap-only


def _gates_for_scope(scope: str):
    return {"cheap-suite": list(CHEAP),
            "full-suite": list(CHEAP) + [g0a],
            "g0a-only": [g0a]}[scope]


def _run_gates(ctx0, staging: Path, run_list, orchestrator_file: str):
    """Run each gate with an IMMUTABLE per-gate child context whose runner SHA is
    the scientific module and whose orchestrator SHA is the suite (contract B).
    Returns (written_reports, verdicts, runner_shas, failures)."""
    written, verdicts, runner_shas, failures = {}, {}, {}, []
    for m in run_list:
        cctx = child_context(ctx0, m.__file__, orchestrator_file)
        cctx = replace(cctx, out_dir=staging, gate=m.GATE)
        report = m.compute(cctx)
        validate_report_schema(report)
        out = atomic_write_report(cctx, m.REPORT, report)
        written[m.REPORT] = hashlib.sha256(out.read_bytes()).hexdigest()
        verdicts[m.GATE] = report["verdict"]
        runner_shas[m.GATE] = cctx.runner_sha256
        if report["verdict"] == "EXECUTION_INVALID":
            failures.append({"gate": m.GATE, "reason": "EXECUTION_INVALID"})
            break
    return written, verdicts, runner_shas, failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v2 suite orchestrator")
    add_common_args(parser)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--cheap-only", action="store_true")
    parser.add_argument("--include-g0a-expensive", action="store_true")
    parser.add_argument("--g0a-only", action="store_true")
    # NOTE (P1.2-D, contract D): there is deliberately NO resume argument. An
    # .interrupted attempt is TERMINAL; a new run needs a new authorization token
    # (a different attempt_id) and starts from scratch.
    args = parser.parse_args(argv)

    try:
        scope = _scope_from_flags(args)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    if args.plan:
        args.dry_run = True
    try:
        ctx0 = build_context(args, "suite_v2", __file__, scope)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    orch_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    if args.plan or ctx0.dry_run:
        gates = [g0a] + CHEAP
        print(json.dumps({
            "suite": "v2", "mode": "plan", "wrote_reports": False,
            "execution_scope": scope,
            "expected_hashes": {"prereg_canonical": ctx0.prereg_canonical_hash,
                                "prereg_file_sha256": ctx0.prereg_file_sha256,
                                "execution_contract_canonical": ctx0.execution_canonical_hash,
                                "execution_contract_file_sha256": ctx0.execution_file_sha256},
            "orchestrator_sha256": orch_sha,
            "gates": [{"gate": m.GATE, "report": m.REPORT,
                       "in_scope": m in _gates_for_scope(scope),
                       "plan": m.plan(ctx0)} for m in gates]}, indent=2, default=str))
        return 0

    run_dir = Path(args.run_dir)
    lock = _custody.AttemptLock(run_dir, ctx0.attempt_id)
    if not lock.acquire():
        print(f"CONTRACT ERROR: attempt {ctx0.attempt_id} already running (lock held)",
              file=sys.stderr)
        return 2
    started = _custody.utc_now()
    try:
        final = _custody.final_dir(run_dir, ctx0.attempt_id)
        staging = _custody.staging_dir(run_dir, ctx0.attempt_id)
        if final.exists():
            print(f"CONTRACT ERROR: attempt already published (immutable): {final}",
                  file=sys.stderr)
            return 2
        if staging.exists() or _custody.interrupted_dir(run_dir, ctx0.attempt_id).exists():
            print("CONTRACT ERROR: prior staging/interrupted state exists for this "
                  "attempt_id. An .interrupted attempt is TERMINAL; a new run needs a "
                  "new authorization token (different attempt_id).", file=sys.stderr)
            return 2
        staging.mkdir(parents=True)

        def _ledger_meta(phase, terminal_state):
            # Contract J: auditable (not scientific) failure ledger with full
            # identity, hashes, token SHA, phase and terminal state.
            return {"campaign_id": ctx0.campaign_id, "attempt_id": ctx0.attempt_id,
                    "execution_scope": scope,
                    "hashes": {"prereg_canonical": ctx0.prereg_canonical_hash,
                               "prereg_file_sha256": ctx0.prereg_file_sha256,
                               "execution_contract_canonical": ctx0.execution_canonical_hash,
                               "execution_contract_file_sha256": ctx0.execution_file_sha256,
                               "freeze_content_hash": ctx0.freeze_content_hash},
                    "freeze_commit": ctx0.freeze_commit, "freeze_tag": ctx0.freeze_tag,
                    "authorization_token_sha256": ctx0.authorization_token_sha256,
                    "started_utc": started, "phase": phase,
                    "terminal_state": terminal_state}

        # initialize crash-handler state BEFORE the fallible call (fixes B: v5 hit
        # UnboundLocalError when _run_gates raised before assigning its return)
        written, verdicts, runner_shas, failures = {}, {}, {}, []
        run_list = _gates_for_scope(scope)
        # Contract D: the ENTIRE custody cycle (gates -> inventory -> manifest ->
        # seal -> post-verify) is inside ONE failure handler. Any custody failure
        # yields a non-zero exit, a sanitized failure ledger, NO success bundle, and
        # staging preserved as .interrupted (or final -> .invalid via seal_and_publish
        # on the exceptional post-rename failure) with no secondary exception.
        try:
            written, verdicts, runner_shas, failures = _run_gates(
                ctx0, staging, run_list, __file__)
            if failures:
                # a gate returned EXECUTION_INVALID: a clean scientific-invalid
                # result, NOT an exception; ledger it and publish no success bundle.
                _custody.write_failure_ledger(run_dir, ctx0.attempt_id, failures,
                                              meta=_ledger_meta("gates", "INTERRUPTED"))
                _custody.mark_interrupted(run_dir, ctx0.attempt_id)
                print(f"SUITE FAILED: {failures}; NO success bundle published",
                      file=sys.stderr)
                return 1
            roles = {name: "report" for name in written}
            if (staging / "g0a_checkpoint.jsonl").exists():
                roles["g0a_checkpoint.jsonl"] = "checkpoint"
            artifacts = _custody.inventory_staging(staging, roles)
            manifest = _custody.build_attempt_manifest(
                campaign_id=ctx0.campaign_id, attempt_id=ctx0.attempt_id,
                execution_scope=scope,
                hashes={"prereg_canonical": ctx0.prereg_canonical_hash,
                        "prereg_file_sha256": ctx0.prereg_file_sha256,
                        "execution_contract_canonical": ctx0.execution_canonical_hash,
                        "execution_contract_file_sha256": ctx0.execution_file_sha256,
                        "freeze_content_hash": ctx0.freeze_content_hash},
                head=ctx0.runtime_head, tag=ctx0.freeze_tag,
                structured_command=structured_command(args, ctx0, argv if argv is not None else sys.argv[1:]),
                runner_shas=runner_shas, orchestrator_sha=orch_sha,
                authorization_token_sha256=ctx0.authorization_token_sha256,
                started_utc=started, ended_utc=_custody.utc_now(), exit_status=0,
                artifacts=artifacts, gate_verdicts=verdicts, environment=ctx0.environment)
            _custody.seal_and_publish(staging, final, manifest)
        except KeyboardInterrupt:
            _custody.mark_interrupted(run_dir, ctx0.attempt_id)
            print("INTERRUPTED (external): staging preserved as .interrupted (terminal)",
                  file=sys.stderr)
            return 130
        except SystemExit:
            _custody.mark_interrupted(run_dir, ctx0.attempt_id)
            raise
        except Exception as e:
            failures = (failures or []) + [failure_record(e, None, "suite")]
            _custody.write_failure_ledger(run_dir, ctx0.attempt_id, failures,
                                          meta=_ledger_meta("custody", "INTERRUPTED"))
            _custody.mark_interrupted(run_dir, ctx0.attempt_id)
            print(f"SUITE FAILED: {type(e).__name__}: {str(e)[:200]}; failure ledger "
                  "written; NO success bundle published", file=sys.stderr)
            return 1
        for gate, verdict in verdicts.items():
            print(f"  {gate}: {verdict}")
        if scope == "cheap-suite":
            print(f"  {g0a.GATE}: NOT_RUN (scope cheap-suite)")
        print(f"published sealed attempt {ctx0.attempt_id} -> {final}")
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
