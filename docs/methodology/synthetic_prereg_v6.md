# Synthetic Pre-Registration v6 (authoritative scientific prereg; NOT EXECUTED)

**Document kind:** SCIENTIFIC_PREREG.
**Contract file:** `experiments/configs/synthetic_prereg_v6.json`
**Canonical hash:** `2d7e260f7ed0fc9a320f8265eb0f29a3c637952330477cae1dbab8d8b3938cf8`
**File SHA-256:** `fd10a220c5d7fe8e720ac027819fa95a65022c5150567dc673c2989e5e59d0e1`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v4.json`
(canonical `eb0e80d9…`, file `1861e7bb…`), binding this prereg by canonical hash.
**Supersedes:** prereg v5 (`f1e02c50…`) + execution contract v3 (`228f15b4…`); execution
freeze v5 is SUPERSEDED / NONEXECUTABLE / NEVER RUN (`docs/audits/p1_2c_independent_audit.md`).
**Changelog:** `docs/methodology/prereg_v5_to_v6_changelog.md`.
**Status:** frozen for execution, **NOT executed**. Synthetic only; no real data.

## What v6 changes over v5 (ALL operational/custody; NO scientific change)

1. **Suite crash handler:** failure state is initialized before the fallible
   `_run_gates()` call; a real gate exception writes a structured failure ledger,
   preserves the sanitized original error, moves staging to `.interrupted`, and
   exits non-zero with no final/SEALED and no secondary `UnboundLocalError`.
2. **Integral manifest + atomic seal:** the attempt manifest inventories EVERY
   artifact (report, G0A checkpoint, evidence) with size + SHA-256 + role; manifest
   and SEALED are written into staging, fsynced and verified, then published by a
   SINGLE atomic rename (no final-without-SEAL window), then re-verified.
   `verify_sealed_attempt` rejects a corrupt checkpoint, an unexpected/extra file, a
   missing artifact, a wrong size/hash, a symlink/non-regular file, an unsafe path,
   or a tampered manifest/SEALED, and requires EXACTLY {manifest, SEALED, inventory}.
   The G0A report records the checkpoint by RELATIVE name + SHA (never an absolute
   host path); the individual G0A attempt inventories its checkpoint.
3. **Coherent interruption policy:** resume is removed entirely. An `.interrupted`
   attempt is TERMINAL; a new run needs a new authorization token (a different
   `attempt_id`) and starts from scratch. No "crash-recoverable" claim remains.
4. **Attempt identity + reconstructible command:** `token_sha = sha256(token)`;
   `attempt_id = sha256(campaign_id | scope | token_sha)`; `authorization_token_sha256`
   is stored in every report and in the manifest so an auditor recomputes `attempt_id`
   without the raw token; empty/whitespace tokens are rejected. The manifest carries a
   STRUCTURED command (interpreter+version, normalized argv with the token masked as
   `<sha256:…>`, hashes/flags, scope, resolved run-dir).
5. **G0A technical-vs-cost taxonomy:** only a clean frozen-deadline expiry yields
   INCONCLUSIVE(INCONCLUSIVE_BY_COST); a missing cell without a deadline, or >20%
   failed seeds in a required cell, yields EXECUTION_INVALID; the INTERRUPTED_BY_COST
   state record is never counted as a completed cell; the deadline abort covers the
   chaos/Benettin computation as well as switching.
6. **Enforced global failed-seed policy:** G1/G2 capture failures during selection
   (common complete-seed mask) and evaluation; G0B/G0C/G4 emit full failure records;
   G4 applies >20% per configured variant and aggregates all failures; the report
   schema validates each failure record's structure.

## Unchanged from v5 (frozen science)

Inference contract (exact two-sided sign test + effect band; std = sample ddof1;
α=0.05; bootstrap as descriptor), all gate criteria/estimands (G0A/G0B/G0C/G1_weak/
G1_strict/G2/G3/G4), the frozen grids/seeds/thresholds, the G1 arm and best-static
selection-on-selection-seeds protocol, the best-of-frozen-candidate-set comparator,
the G1 hierarchy, and the G2 "permutation-median comparator + cross-seed sign test"
terminology (with its cancellation limitation disclosed).

## Not a rescue

v6 makes the harness executable and its custody sound; it changes no scientific
criterion in a result-favoring direction. All gates may still FAIL or be INCONCLUSIVE.
