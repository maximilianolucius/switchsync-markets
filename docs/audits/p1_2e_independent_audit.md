# P1.2-E Independent Audit — execution freeze v7 is NON-EXECUTABLE

**Subject:** `switchsync-synthetic-execution-v7-freeze` → commit `61a63f3`; prereg v7
(canonical `7fde7def…`) + execution contract v5 (canonical `b169c420…`) + freeze v7
(content_hash `9cbb3335…`).
**Chain of custody / reproducibility PASSED:** the multipart package reconstructed to
bundle SHA-256 `531c1a89…`; HEAD/tag v7 = `61a63f3…`; freeze v7 verified (109 files, no
missing/mismatch/added); 127 tests pass; prior history and tags intact.
**Verdict:** a single blocking defect, reproduced with the REAL documents; **NOT
executable**. Repaired minimally in prereg v8 + execution contract v6 + freeze v8
(P1.2-F). No v7 scientific gate was ever executed; no v7 result exists.

## Defect (reproduced with the real active documents)

```
$ python3 experiments/run_suite_v2.py --plan
...
  File ".../experiments/run_g0a_exact_v2.py", line 47, in _cfg
    ctx.prereg["global"]["dt"], ctx.prereg["tolerances"],
KeyError: 'tolerances'
```

| # | Area | Defect in v7 | Repair (v8 / P1.2-F) |
|---|------|--------------|----------------------|
| T | prereg schema | prereg v7 has no top-level `tolerances` block. `run_g0a_exact_v2._cfg` and `run_g0b_calibrated_v2._cfg` read `ctx.prereg["tolerances"]` (→ `sync_threshold_E12`, `sync_tail_frac`), so even `--plan` raises `KeyError`. The block existed in prereg v3 and was accidentally dropped when prereg v4 was created, never declared as a scientific change. The P1.2-D/E test fixtures embedded the key and masked the gap. | prereg v8 restores exactly the v3 block `{sync_threshold_E12: 0.02, sync_tail_frac: 0.25}`. Nothing else scientific changes. New tests consume the REAL active documents (not fixtures): they assert the two tolerances, build a real dry-run context, call `plan()` for every gate, run every runner `--dry-run` by subprocess (exit 0), require `run_suite_v2.py --plan` exit 0, and include a regression that v7 raises `KeyError` while v8 succeeds. |

## Root cause of the masking

The runner tests used reconstructed fixtures (`_tiny_prereg`) that always contained a
`tolerances` block, so the incompatibility between the runners and the REAL prereg
files v4–v7 was never exercised. P1.2-F adds integration tests that consume the real
active documents.

## Disposition

Execution freeze v7 → **SUPERSEDED / NONEXECUTABLE / NEVER RUN** (sidecar
`artifacts/freeze_execution_v7.SUPERSEDED.md`). Tag and commit preserved byte-for-byte
and NOT rewritten. Superseded by prereg v8 + execution contract v6 + freeze v8, tag
`switchsync-synthetic-execution-v8-freeze`. No v7 result was ever produced.
