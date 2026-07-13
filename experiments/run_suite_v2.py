"""Suite orchestrator for the v2 gate runners.

--dry-run prints the plan for every gate and executes NOTHING (writes no reports).
A full run requires the execution contract (auth + exact hashes + verified freeze)
and writes one *_v2.json per gate, atomically, refusing to overwrite.

Import-safe."""
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

GATES = [g0a, g0b, g0c, g1g2, g3, g4]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="v2 suite orchestrator")
    add_common_args(parser)
    args = parser.parse_args(argv)
    try:
        ctx = build_context(args, "suite_v2", __file__)
    except ContractError as e:
        print(f"CONTRACT ERROR: {e}", file=sys.stderr)
        return 2

    if ctx.dry_run:
        plans = [{"gate": m.GATE, "report": m.REPORT, "plan": m.plan(ctx)} for m in GATES]
        print(json.dumps({"suite": "v2", "dry_run": True, "wrote_reports": False,
                          "gates": plans}, indent=2, default=str))
        return 0

    written = []
    try:
        for m in GATES:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
