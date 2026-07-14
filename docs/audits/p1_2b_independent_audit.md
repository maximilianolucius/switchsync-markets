# P1.2-B Independent Audit — execution freeze v4 is NON-EXECUTABLE

**Subject:** `switchsync-synthetic-execution-v4-freeze` → commit `04c33309`; prereg v4
(`847a8a8c…`) + execution contract v2 (`8738b591…`) + freeze v4 (`ba102c4a…`).
**Verdict:** hashes and most scientific corrections are valid, but critical
provenance/custody/failure/G0A defects prevent authorizing an execution. Repaired
in prereg v5 + execution contract v3 + freeze v5.

## Defects

| # | Area | Defect in v4 | Repair (v5) |
|---|---|---|---|
| B1 | provenance | `run_suite_v2` built ONE context from its own file and passed it to every `m.compute(ctx)`: every report recorded the ORCHESTRATOR's SHA as `runner_sha256` | immutable per-gate `child_context(ctx, m.__file__, suite_file)`: runner SHA = scientific module, orchestrator SHA recorded separately |
| B2 | provenance | `--orchestrator-sha` was free operator text (`--orchestrator-sha none` forged provenance) | CLI argument REMOVED; orchestrator SHA is set only by the suite in code; individual runners record null + `execution_mode="individual:<gate>"` |
| C1 | identity | `run_id` depended only on prereg/contract/freeze/commit → identical for cheap-suite, full-suite, g0a-only and individual runners (collisions; published bundles modifiable) | `campaign_id` (contract) + `attempt_id` = sha256(campaign \| scope \| auth token); frozen scope vocabulary; token recorded only as SHA |
| D1 | custody | published run dir was mutable; no manifest, no seal, no lock | `attempt_manifest.json` (own content hash), SEALED marker, fsync, post-seal re-verification, flock per attempt_id, immutable final dir |
| E1 | custody | contradictory crash policy: G0A "crash-recoverable" but the suite rejected any prior staging; no frozen resume policy | frozen policy: no auto-retry; staging preserved as `.interrupted`; resume requires `--resume-authorized-attempt` + a NEW authorization token + exact checkpoint provenance; never mix attempts; technical failure ≠ scientific result |
| F1 | ledger | `_load()` accepted duplicate keys (last record silently overwrote the first); no sequence numbers; no hash chain; truncated tail undetected | hash-chained ledger: seq + prev_record_hash + record_hash; duplicates/gaps/reorders/changed results/foreign provenance rejected at load; truncated tail detected, prefix preserved, continuation requires authorization |
| G1 | G0A | deadline only polled inside `simulate()`; `largest_lyapunov_isolated_layer` had no abort → chaos could overrun the budget unbounded | chunked abort in the Benettin integration too; deadline checked before each size/seed and during chaos + switching + serialization |
| G2 | G0A | N=100 could consume budget before the deciding sizes | deciding sizes {200,400} run FIRST |
| G3 | G0A | deadline expiry and external interruption were indistinguishable | clean DeadlineExceeded → checkpoint + INTERRUPTED_BY_COST → INCONCLUSIVE_BY_COST; external signal/crash propagates with NO verdict |
| H1 | policy | no global failed-seed policy (G1 had no capture; G3/G4 caught only NaN; G0B denominator undefined; G0C undefined) | frozen global policy: failure definition, sanitized per-seed capture, >20% → EXECUTION_INVALID, ≤20% → successful-seeds denominator + disclosure; G0B = SUCCESSFUL_SEEDS_ONLY; G0C single-seed → EXECUTION_INVALID |
| I1 | G2 | called a "permutation null / permutation test" but computed `delta = gamma_ordered − median(perms)` + cross-seed sign test (no per-seed p-value) | Option 1 frozen: renamed "permutation-median comparator + cross-seed sign test", limitation (sign-varying effects can cancel) disclosed; positive test runs the REAL pipeline end-to-end |

## v4 tests that were insufficient

- The "suite records runner+orchestrator SHA" test passed a FIXTURE orchestrator string; it never executed the suite path, so B1 went undetected.
- No test covered attempt identity across scopes, sealing, resume policy, ledger chaining, deadline-in-chaos, or a real G2 end-to-end positive.

## Disposition

Execution freeze v4 → **SUPERSEDED / NONEXECUTABLE / NEVER RUN** (sidecar
`artifacts/freeze_execution_v4.SUPERSEDED.md`). Tag and commit preserved, not
rewritten. No v4 result was ever produced.
