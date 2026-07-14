# Changelog: prereg v7 → v8 (execution contract v5 → v6)

Reason for v8: freeze v7 was NON-EXECUTABLE. prereg v7 lacked the top-level
`tolerances` block that `run_g0a_exact_v2` and `run_g0b_calibrated_v2` read, so
`python3 experiments/run_suite_v2.py --plan` raised `KeyError: 'tolerances'`
(`docs/audits/p1_2e_independent_audit.md`).

## The single scientific change: restored `tolerances`

```json
"tolerances": { "sync_threshold_E12": 0.02, "sync_tail_frac": 0.25 }
```

- Restored **verbatim from prereg v3** (present through v3, accidentally dropped at v4,
  absent v4–v7, never declared as a change).
- Changes **no** seed, grid, estimand, gate, inference rule or decision rule.
- No result v2–v7 was ever executed, so nothing downstream depended on its absence.

A key-by-key diff of prereg v7 vs v8 shows the ONLY differing keys are the metadata
`contract_name`, `contract_version`, `supersedes`, `description`, `lineage` plus the
restored `tolerances`. All frozen-science sections are byte-identical (asserted by a
test).

## Hashes

| Document | Canonical | File SHA-256 |
|---|---|---|
| prereg v8 | `a667434d…` | `89616389…` |
| execution contract v6 | `6dbe79dd…` | `80609ef5…` |
| prereg v7 (superseded) | `7fde7def…` | — |
| execution contract v5 (superseded) | `b169c420…` | — |

Execution contract v6 is parameter-identical to v5/v4/v3; only `binds_prereg` /
`binds_prereg_canonical_hash` (now v8) and the name/version/description changed.

## Not a rescue

Restoring an already-frozen value that was accidentally lost. No new hypothesis, no
grid change, no parameter search. NO real data.
