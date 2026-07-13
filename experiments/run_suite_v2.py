"""Transactional suite orchestrator for the v2 gate runners (P1.2-B, contract I).

Modes:
  --plan                    print runners, outputs, expected hashes, projected
                            runtime and dependencies; run nothing.
  --cheap-only              full run of cheap gates (G0B, G0C, G1/G2, G3, G4);
                            G0A NOT_RUN.
  --include-g0a-expensive   also run G0A.
Supplying BOTH --cheap-only and --include-g0a-expensive is a contradiction and is
rejected.

Transaction: reports are written to <run-dir>/<run_id>.staging/; on FULL success
the bundle is published to <run-dir>/<run_id>/ by atomic rename (fsync). If any
gate raises or returns EXECUTION_INVALID, a failure ledger is written and NO
success bundle is published. Each report records the scientific runner SHA and the
orchestrator (suite) SHA. Import-safe."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import _custody
from _contract_v2 import (
    ContractError,
    add_common_args,
    atomic_write_report,
    build_context,
    validate_report_schema,
)

import run_g0a_exact_v2 as g0a
import run_g0b_calibrated_v2 as g0b
import run_g0c_msf_v2 as g0c
import run_g1_g2_paired_v2 as g1g2
import run_g3_v2 as g3
import run_g4_v2 as g4

CHEAP = [g0b, g0c, g1g2, g3, g4]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v2 suite orchestrator")
    add_common_args(parser)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--cheap-only", action="store_true")
    parser.add_argument("--include-g0a-expensive", action="store_true")
    args = parser.parse_args(argv)

    if args.cheap_only and args.include_g0a_expensive:
        print("CONTRACT ERROR: --cheap-only and --include-g0a-expensive are contradictory",
              file=sys.stderr)
        return 2
    if args.plan:
        args.dry_run = True
    try:
        ctx = build_context(args, "suite_v2", __file__)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    ctx.orchestrator_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    if args.plan or ctx.dry_run:
        gates = [g0a] + CHEAP
        print(json.dumps({
            "suite": "v2", "mode": "plan", "wrote_reports": False,
            "expected_hashes": {"prereg_canonical": ctx.prereg_canonical_hash,
                                "prereg_file_sha256": ctx.prereg_file_sha256,
                                "execution_contract_canonical": ctx.execution_canonical_hash,
                                "execution_contract_file_sha256": ctx.execution_file_sha256},
            "orchestrator_sha256": ctx.orchestrator_sha256,
            "dependencies": "gates independent; G0A obeys the frozen cost rule and is NOT_RUN "
                            "unless --include-g0a-expensive",
            "gates": [{"gate": m.GATE, "report": m.REPORT, "runs_by_default": m is not g0a,
                       "plan": m.plan(ctx)} for m in gates]}, indent=2, default=str))
        return 0

    # ---- transactional full run ----
    run_dir = Path(args.run_dir)
    staging = _custody.staging_dir(run_dir, ctx.run_id)
    final = _custody.final_dir(run_dir, ctx.run_id)
    if final.exists():
        print(f"CONTRACT ERROR: run already published: {final}", file=sys.stderr)
        return 2
    if staging.exists():
        print(f"CONTRACT ERROR: stale staging exists (no resume policy): {staging}", file=sys.stderr)
        return 2
    staging.mkdir(parents=True)
    ctx.out_dir = staging                       # gates write into staging

    run_list = list(CHEAP) + ([g0a] if args.include_g0a_expensive else [])
    written, failures = [], []
    for m in run_list:
        try:
            report = m.compute(ctx)
            validate_report_schema(report)
            atomic_write_report(ctx, m.REPORT, report)
            written.append((m.GATE, report["verdict"]))
            if report["verdict"] == "EXECUTION_INVALID":
                failures.append({"gate": m.GATE, "reason": "EXECUTION_INVALID"})
                break
        except Exception as e:
            failures.append({"gate": m.GATE, "error": f"{type(e).__name__}: {e}"})
            break

    if failures:
        led = _custody.write_failure_ledger(run_dir, ctx.run_id, failures)
        print(f"SUITE FAILED: {failures}; failure ledger {led}; NO success bundle published",
              file=sys.stderr)
        return 1

    _custody.publish_atomic(staging, final)
    for gate, verdict in written:
        print(f"  {gate}: {verdict}")
    if not args.include_g0a_expensive:
        print(f"  {g0a.GATE}: NOT_RUN (use --include-g0a-expensive)")
    print(f"published -> {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
