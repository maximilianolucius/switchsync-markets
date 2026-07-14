# Changelog: prereg v6 → v7 (execution contract v4 → v5)

Every change below is **operational / custody / documentation**. **NO scientific
criterion, estimand, grid, seed, threshold or inference rule changed.** The frozen
science sections (`global`, `fhn`, `seed_blocks`, `inference_contract`, and every gate
pass/fail rule) are byte-identical between v6 and v7. Reason for v7: the independent
audit of the v6 multipart package reproduced blocking operational/custody defects
(`docs/audits/p1_2d_independent_audit.md`); execution freeze v6 is SUPERSEDED /
NONEXECUTABLE / NEVER RUN.

## Hashes

| Document | Canonical | File SHA-256 |
|---|---|---|
| prereg v7 | `7fde7def…` | `829f4105…` |
| execution contract v5 | `b169c420…` | `20c1e79f…` |
| prereg v6 (superseded) | `2d7e260f…` | — |
| execution contract v4 (superseded) | `eb0e80d9…` | — |

Execution contract v5 is grid-identical to v4/v3; only `binds_prereg` /
`binds_prereg_canonical_hash` (now the v7 canonical) and the name/version/description
changed.

## Operational / custody changes (classified)

| # | Class | v6 | v7 |
|---|-------|----|----|
| B | custody | an invalid `manifest_content_hash`/inventory could reach `os.replace()` | a SINGLE pre-rename `validate_manifest_and_staging()`; a deterministic pre-rename error leaves `final` nonexistent |
| C | custody | staging tolerated subdirectories; verifier could raise on a malformed manifest | FLAT staging; symlink/dir/FIFO/socket/device rejected; verifier NEVER raises (returns `ok=False`+errors) |
| D | custody | inventory→manifest→seal ran outside the failure handler; a post-rename failure could leave a successful-looking final | the full cycle is inside one handler; post-rename failure moves `final`→`.invalid`; no success bundle on any failure |
| E | operational | the G1/G2 common mask left the best-static candidate universe unprotected | frozen candidate set + atomic per-seed cached matrix; whole-seed drop on any arm/candidate failure; select from cache |
| F | operational | G0A checked missing cells before the failure policy (technical failure could become cost) | frozen precedence: >20%/zero-success technical failure → EXECUTION_INVALID OUTRANKS cost |
| G | operational | `n_completed_cells` counted the state record; `time.time()`; per-seed try too narrow | split counters (ledger/science/state); `time.monotonic()` SOFT budget + elapsed/overshoot; per-seed try covers RNG/state/params/schedule/sim/finiteness |
| H | operational | G0B built state/schedule outside the try; G0C omitted failure records for nonfinite/prereq | construction inside the per-seed try; full failure records for G0C prerequisite and nonfinite Psi |
| I | documentation | prereg v6 simultaneously said `crash-recoverable`, "continuation requires authorization", no-resume-terminal, `partial_rule → cost`, and missing-without-deadline → invalid | ONE coherent no-resume policy; checkpoint is evidence; incomplete-by-clean-deadline-no-invalidating-failure → cost, else invalid; scan test forbids the stale strings |
| J | custody | thin, overwritable failure ledger | atomic, NON-overwritable, enriched (campaign/scope/hashes/token/phase/terminal state) |

## Not a rescue

v7 tightens custody and internal consistency; it never relaxes a scientific criterion.
All gates may still FAIL or be INCONCLUSIVE. NO real data. NOT EXECUTED.
