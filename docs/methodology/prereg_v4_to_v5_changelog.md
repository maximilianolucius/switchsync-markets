# Pre-registration v4 → v5 changelog (P1.2-C)

## Hash lineage

| Document | canonical | file SHA-256 |
|---|---|---|
| prereg v4 (superseded) | `847a8a8c…` | `36dd76e0…` |
| execution contract v2 (superseded) | `8738b591…` | `919a3d8b…` |
| **prereg v5** | `f1e02c50…` | `6b0de8a7…` |
| **execution contract v3** | `228f15b4…` | `f0d487a5…` |

## Changes (v4 → v5)

- **Provenance (B):** per-gate immutable child contexts in the suite (runner SHA =
  scientific module; orchestrator SHA recorded separately, set only in code);
  `--orchestrator-sha` REMOVED; individual runners record orchestrator_sha256=null
  and execution_mode="individual:<gate>".
- **Identity (C):** campaign_id (contract) + attempt_id (campaign | frozen scope |
  authorization token, token recorded only as SHA-256); scope vocabulary frozen and
  code-determined; cheap-suite and g0a-only coexist under one campaign with distinct
  attempts; campaign result bundles reference sealed attempts by hash without
  touching their bytes.
- **Custody (D):** attempt_manifest.json with its own content hash; SEALED marker;
  fsync; post-seal re-verification; flock per attempt_id; SEALED dirs refuse writes;
  individual runners publish their own sealed single-report attempts.
- **Crash/resume (E):** frozen policy — no auto-retry; `.interrupted` preservation;
  `--resume-authorized-attempt` + new authorization token + exact checkpoint
  provenance; never mix attempts; technical failure ≠ scientific result.
- **Ledger (F):** hash-chained (seq, prev_record_hash, record_hash); duplicates,
  gaps, reorders, edits, foreign provenance rejected at load; truncated tail
  detected with prefix preserved and authorization required to continue.
- **G0A deadline (G):** budget covers chaos + switching + serialization; chunked
  abort inside the Benettin chaos computation; checks before each size/seed;
  deciding sizes first; clean deadline → INTERRUPTED_BY_COST → INCONCLUSIVE_BY_COST;
  external interruption produces no verdict.
- **Failed-seed policy (H):** global frozen definition/capture/thresholds;
  successful-seeds denominator with mandatory disclosure; G0B denominator frozen as
  SUCCESSFUL_SEEDS_ONLY; G0C single-seed → EXECUTION_INVALID; per-seed exception
  capture added to G1 (selection+evaluation), G3 and G4.
- **G2 (I):** Option 1 frozen — renamed "permutation-median comparator + cross-seed
  sign test" with the cancellation limitation disclosed; the positive test runs the
  real pipeline end-to-end.

## Proof this predates any result

No gate-result file (g0a…g4…_v2.json) exists anywhere; the external run-dir is
empty; the execution contract has never been satisfied with an authorization token.
