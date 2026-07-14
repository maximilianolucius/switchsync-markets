# P1.2-D Independent Audit — execution freeze v6 is NON-EXECUTABLE

**Subject:** `switchsync-synthetic-execution-v6-freeze` → commit `ca55940`; prereg v6
(canonical `2d7e260f…`) + execution contract v4 (canonical `eb0e80d9…`) + freeze v6
(content_hash `c525f11f…`).
**Chain of custody / reproducibility PASSED:** the multipart package reconstructed to
bundle SHA-256 `10386f67…`; HEAD/tag v6 = `ca55940…`; 101 freeze files with no
missing/mismatch/added; 105 tests pass in a fresh clone.
**Verdict:** blocking operational/custody defects reproduced; **NOT authorizable for
execution**. Repaired in prereg v7 + execution contract v5 + freeze v7 (P1.2-E). No
v6 scientific gate was ever executed; no v6 result exists.

## Defects (all reproduced against the v6 package)

| # | Area | Defect in v6 | Repair (v7 / P1.2-E) |
|---|------|--------------|----------------------|
| B | seal | `seal_and_publish` verified individual report SHAs but let an INVALID `manifest_content_hash` (or a mismatched inventory) reach `os.replace()`, publishing an invalid `final`. | a SINGLE `validate_manifest_and_staging()` runs on the FULL staging (manifest shape/types, recomputed content hash, id coherence, artifact metadata, flat exact inventory, SEALED↔manifest) BEFORE the rename; a deterministic pre-rename error leaves `final` nonexistent. |
| C | staging/verify | staging was walked with `rglob` (subdirectories tolerated); non-regular entries (symlink to dir/file, FIFO/socket/device) were not systematically rejected; `verify_sealed_attempt` could RAISE on a malformed manifest instead of returning a verdict. | staging is FLAT (`iterdir`, `_entry_kind` via `os.lstat`+`stat`) and must contain EXACTLY the declared artifacts + manifest + SEALED; `verify_sealed_attempt` is fully defensive and NEVER raises — it returns `ok=False` with structured errors. |
| D | custody handler | inventory → manifest → seal → post-verify ran OUTSIDE the failure handler in both the individual runner and the suite; a custody failure escaped as an unhandled traceback, and a post-rename verification failure could leave a successful-looking `final`. | the ENTIRE cycle (compute→schema→report→inventory→manifest→seal→post-verify) is inside ONE handler: non-zero exit, sanitized failure record + ledger, NO success bundle, staging→`.interrupted`; an exceptional post-rename failure moves `final`→`.invalid` (never left as success). |
| E | G1/G2 mask | the "common" selection mask verified the arms + `base[0]` only, then `_select_best_static` evaluated the hundreds of best-static candidates OUTSIDE that protection, so a seed with a nonfinite candidate gamma could corrupt selection. | the frozen candidate universe is built FIRST; per selection seed ALL arms AND ALL candidates are computed atomically into a cached matrix; any failure/nonfinite drops the WHOLE seed from the common mask (recording seed/phase/arm-or-candidate); arm and best-static are chosen from the cache with no recomputation; >20% and zero-success enforced. |
| F | G0A precedence | the verdict checked missing cells (→ cost) BEFORE the >20%/zero-success failure policy, so a run with a >20%-failed cell + another missing cell + `interrupted_by_cost=True` could be laundered into `INCONCLUSIVE_BY_COST`. | FROZEN precedence: a >20% technical failure or zero-success in ANY observable required cell → `EXECUTION_INVALID`, evaluated BEFORE the missing/cost check; a recorded technical failure can never become cost. |
| G | G0A counters/clock/try | `n_completed_cells` counted the `kind=state` record as a science cell; the budget used `time.time()` (non-monotonic) and claimed to cover non-interruptible fsync; RNG/initial-state and schedule construction sat OUTSIDE the per-seed try. | `n_science_cells` excludes `kind=state`; `n_ledger_records`/`n_science_cells`/`n_state_records` reported separately; `time.monotonic()` SOFT budget with elapsed/overshoot recorded; RNG/state/params/schedule/sim/finiteness all inside the per-seed try. |
| H | G0B/G0C records | G0B built initial-state/schedule OUTSIDE the try (a construction error escaped rather than becoming a record); G0C reported a nonfinite Psi and a prerequisite failure WITHOUT a full failure record. | G0B: construction inside the per-seed try, KeyboardInterrupt/SystemExit propagate; G0C: technical prerequisite failure and nonfinite Psi each emit a full `{exception_type,message,seed,cell,timestamp_utc}` record. |
| I | contradictions | prereg v6 simultaneously asserted `crash-recoverable`, "continuation requires explicit authorization", a no-resume terminal policy, `partial_rule: any incomplete deciding cell -> INCONCLUSIVE_BY_COST`, and missing-without-deadline → EXECUTION_INVALID. | prereg v7 states ONE coherent policy: no resume; `.staging`/`.interrupted`/`.invalid` terminal; a new token → a new attempt from scratch; the checkpoint is EVIDENCE, not a resume input; incomplete-by-clean-deadline-and-no-invalidating-failure → cost, incomplete-by-any-other-cause → invalid. A scan test forbids the stale strings in the active files. |
| J | failure ledger | the failure ledger was thin and overwritable, and did not carry the campaign/scope/hash/token/phase provenance. | atomic, NON-overwritable (numbered variants), carrying campaign/attempt/scope, freeze/prereg/contract hashes, token SHA, UTC, phase and terminal state; auditable but never a scientific result. |

## Disposition

Execution freeze v6 → **SUPERSEDED / NONEXECUTABLE / NEVER RUN** (sidecar
`artifacts/freeze_execution_v6.SUPERSEDED.md`). Tag and commit preserved byte-for-byte
and NOT rewritten. Superseded by prereg v7 + execution contract v5 + freeze v7, tag
`switchsync-synthetic-execution-v7-freeze`. No v6 result was ever produced.
