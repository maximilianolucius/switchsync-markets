# Synthetic Pre-Registration v5 (authoritative scientific prereg; NOT EXECUTED)

**Document kind:** SCIENTIFIC_PREREG.
**Contract file:** `experiments/configs/synthetic_prereg_v5.json`
**Canonical hash:** `f1e02c508546d0286373a30960744d83e09e6013478c70e26dc3087a2023ebca`
**File SHA-256:** `6b0de8a72f6921dcca79bc7e7e34cc7519b877428ad37310e3cb05877eebe58c`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v3.json`
(canonical `228f15b4…`, file `f0d487a5…`), binding this prereg by canonical hash.
**Supersedes:** prereg v4 (`847a8a8c…`) + execution contract v2 (`8738b591…`); execution
freeze v4 is SUPERSEDED / NONEXECUTABLE / NEVER RUN (`docs/audits/p1_2b_independent_audit.md`).
**Changelog:** `docs/methodology/prereg_v4_to_v5_changelog.md`.
**Status:** frozen for execution, **NOT executed**. Synthetic only; no real data.

## What v5 adds over v4 (all defect-driven; science criteria unchanged)

1. **Provenance (B):** per-gate immutable child contexts — every report records the
   scientific runner's real SHA; the orchestrator SHA is recorded separately and can
   only be set in code (no `--orchestrator-sha`); individual runners record
   `orchestrator_sha256=null` and `execution_mode="individual:<gate>"`.
2. **Identity (C):** `campaign_id` (scientific contract) vs `attempt_id`
   (campaign | frozen code-determined scope | authorization token, token stored only
   as SHA-256). Frozen scope vocabulary: cheap-suite, full-suite, g0a-only,
   individual:G0A/G0B/G0C/G1G2/G3/G4. Attempts under one campaign coexist; campaign
   result bundles reference sealed attempts by manifest hash without touching bytes.
3. **Immutable publication (D):** `attempt_manifest.json` (ids, scope, hashes,
   HEAD/tag, normalized command, runner+orchestrator SHAs, UTC start/end, exit
   status, per-report SHA-256, checkpoint SHA, verdicts, environment, COMPLETED,
   own content hash) → fsync → atomic rename → SEALED marker → post-seal
   re-verification; SEALED dirs refuse all writes; per-attempt flock.
4. **Crash/resume (E):** no auto-retry; `.interrupted` preservation; resume only via
   `--resume-authorized-attempt` + a NEW authorization token + exact checkpoint
   provenance match; attempts never mixed; technical failure ≠ scientific verdict.
5. **Checkpoint ledger (F):** hash-chained (seq, prev_record_hash, record_hash);
   duplicates, gaps, reordering, edits and foreign provenance rejected at load;
   truncated tail detected, valid prefix preserved as evidence, continuation
   requires authorization.
6. **G0A deadline (G):** budget covers chaos + switching + serialization, polled
   before each size/seed and inside both integrations (chunked); deciding sizes
   {200,400} run first; only a CLEAN deadline converts to
   INTERRUPTED_BY_COST → INCONCLUSIVE(INCONCLUSIVE_BY_COST).
7. **Global failed-seed policy (H):** frozen failure definition (exception, technical
   timeout, wrong shape, nonfinite, missing result); sanitized per-seed capture
   (type, truncated message, seed, cell, UTC); >20% → EXECUTION_INVALID(FAILED_RUNS);
   ≤20% → successful-seeds denominator, reduced inferential n, mandatory disclosure.
   G0B `frac_synced` denominator = SUCCESSFUL_SEEDS_ONLY (frozen). G0C (single seed):
   any failure → EXECUTION_INVALID. G0A distinguishes failed cell / incomplete-by-cost
   / external interruption.
8. **G2 terminology (I, Option 1 frozen):** the method is a **permutation-median
   comparator + cross-seed sign test** — NOT a permutation test. It detects a
   systematic displacement of the observed order relative to the permutation median;
   order effects of varying sign across seeds can cancel. Limitation disclosed.

## Unchanged from v4

The inference contract (exact two-sided sign test + effect band, std = sample
ddof1, α=0.05, bootstrap as descriptor), the gate criteria/estimands (G0A/G0B/G0C/
G1_weak/G1_strict/G2/G3/G4), arm and best-static selection on selection seeds, the
best-of-frozen-candidate-set comparator, and the G1 hierarchy.

## Not a rescue

v5 does not change any scientific criterion in a result-favoring direction; it makes
execution, custody and failure handling well-defined. All gates may still FAIL or
be INCONCLUSIVE.
