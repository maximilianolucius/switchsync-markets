"""Suite orchestrator for the v2 gate runners (P1.2-A).

Modes:
  --plan                    print runners, outputs, expected hashes, projected
                            runtime and dependencies; execute NO science, write
                            NO reports (no auth/freeze required).
  --cheap-only              full run of the cheap gates only (G0B, G0C, G1/G2,
                            G3, G4); G0A is NOT_RUN.
  --include-g0a-expensive   also run the expensive G0A.
Default (no G0A flag): cheap gates run; G0A is NOT_RUN (never INCONCLUSIVE).

A full run requires the execution contract. Import-safe."""
from __future__ import annotations

import argparse
import json
import sys

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
    parser.add_argument("--plan", action="store_true",
                        help="print the plan (runners, outputs, hashes, runtime, deps); run nothing")
    parser.add_argument("--cheap-only", action="store_true",
                        help="run cheap gates only (G0A NOT_RUN)")
    parser.add_argument("--include-g0a-expensive", action="store_true",
                        help="also run the expensive G0A")
    args = parser.parse_args(argv)

    if args.plan:
        args.dry_run = True  # plan implies no execution / no contract enforcement
    try:
        ctx = build_context(args, "suite_v2", __file__)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    if args.plan or ctx.dry_run:
        gates = [g0a] + CHEAP
        plan = {
            "suite": "v2", "mode": "plan", "wrote_reports": False,
            "expected_hashes": {
                "prereg_canonical": ctx.prereg_canonical_hash,
                "prereg_file_sha256": ctx.prereg_file_sha256,
                "execution_contract_canonical": ctx.execution_canonical_hash,
                "execution_contract_file_sha256": ctx.execution_file_sha256,
            },
            "dependencies": "gates are independent; G0A obeys the frozen cost rule and is "
                            "NOT_RUN unless --include-g0a-expensive.",
            "gates": [{"gate": m.GATE, "report": m.REPORT,
                       "runs_by_default": m is not g0a,
                       "plan": m.plan(ctx)} for m in gates],
        }
        print(json.dumps(plan, indent=2, default=str))
        return 0

    # ---- full run ----
    run_list = list(CHEAP)
    g0a_state = "NOT_RUN"
    if args.include_g0a_expensive:
        run_list = [g0a] + run_list
        g0a_state = "SCHEDULED"
    written = []
    try:
        for m in run_list:
            report = m.compute(ctx)
            validate_report_schema(report)
            out = atomic_write_report(ctx, m.REPORT, report)
            written.append((m.GATE, str(out), report["verdict"]))
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"EXECUTION ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    for gate, path, verdict in written:
        print(f"  {gate}: {verdict} -> {path}")
    if not args.include_g0a_expensive:
        print(f"  {g0a.GATE}: NOT_RUN (use --include-g0a-expensive)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
