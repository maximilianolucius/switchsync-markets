# Synthetic Pre-Registration v7 (authoritative scientific prereg; NOT EXECUTED)

**Document kind:** SCIENTIFIC_PREREG.
**Contract file:** `experiments/configs/synthetic_prereg_v7.json`
**Canonical hash:** `7fde7def521ae3dabc1ed7bac38427fccea5dea79eeb073ef407210799dbc1e7`
**File SHA-256:** `829f4105fea1f032180b3256ca100215d7005b74a2889679aab386c38da837cb`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v5.json`
(canonical `b169c420…`, file `20c1e79f…`), binding this prereg by canonical hash.
**Supersedes:** prereg v6 (canonical `2d7e260f…`) + execution contract v4 (canonical
`eb0e80d9…`); execution freeze v6 is SUPERSEDED / NONEXECUTABLE / NEVER RUN
(`docs/audits/p1_2d_independent_audit.md`).
**Changelog:** `docs/methodology/prereg_v6_to_v7_changelog.md`.
**Status:** frozen for execution, **NOT executed**. Synthetic only; no real data.

## What v7 changes over v6 (ALL operational/custody; NO scientific change)

1. **Single pre-rename validation (B).** One `validate_manifest_and_staging()`
   checks manifest shape/types, the recomputed manifest content hash, campaign/attempt/
   scope coherence, artifact metadata (size int≥0, valid SHA-256, valid role), a FLAT
   staging containing EXACTLY the declared artifacts + manifest + SEALED, per-artifact
   size/hash, and SEALED↔manifest agreement. It runs BEFORE the rename, so an invalid
   `manifest_content_hash` can never reach `os.replace()`. A deterministic pre-rename
   error leaves `final` NONEXISTENT.
2. **Flat staging + never-raising verifier (C).** Staging is walked top-level only
   (`iterdir`); any subdirectory, symlink (even to a directory), FIFO/socket/device is
   rejected. `verify_sealed_attempt` NEVER raises on a malformed manifest — it returns
   `ok=False` with structured errors.
3. **Full custody cycle in one handler + `.invalid` (D).** compute → schema → report →
   inventory → manifest → seal → post-verify are wrapped in a SINGLE failure handler in
   both the individual runner and the suite: a custody failure yields a non-zero exit, a
   sanitized failure record + ledger, NO success bundle, and staging → `.interrupted`;
   an exceptional post-rename verification failure moves `final` → `.invalid` (never
   left as a successful attempt), with no secondary exception.
4. **Truly common G1/G2 mask over a cached matrix (E).** The frozen static-candidate
   universe is built FIRST; per selection seed ALL rate arms AND gamma for EVERY
   candidate are computed atomically into a cached matrix; any failure/nonfinite drops
   the WHOLE seed from the common mask (recording seed/phase/arm-or-candidate); arm and
   best-static are selected from the cache with no recomputation; >20% and zero-success
   are enforced.
5. **Frozen G0A failure precedence (F).** Highest first: corrupt contract →
   EXECUTION_INVALID; >20% technical failures OR zero-success in any observable required
   cell → EXECUTION_INVALID (OUTRANKS cost); else missing under a clean deadline →
   INCONCLUSIVE_BY_COST; missing without a deadline → EXECUTION_INVALID; complete grid →
   PASS/FAIL. A recorded technical failure is never laundered into cost.
6. **G0A counters / monotonic soft budget / per-seed try (G).** `n_science_cells`
   excludes the `kind=state` record; `n_ledger_records`/`n_science_cells`/
   `n_state_records` are disclosed separately; the budget is a SOFT `time.monotonic`
   budget with `elapsed_seconds`/`overshoot_seconds` recorded; RNG/initial-state,
   cell-dependent params, schedule construction, simulation and finiteness all sit
   inside the per-seed try.
7. **Full G0B/G0C failure records (H).** G0B builds initial-state/schedule inside the
   per-seed try (KeyboardInterrupt/SystemExit propagate); G0C emits a full failure
   record for a technical prerequisite failure and for a nonfinite Psi.
8. **One coherent interruption policy (I).** The residual contradictions are removed:
   no resume; `.staging`/`.interrupted`/`.invalid` terminal; a new authorization token
   yields a new attempt from scratch; the checkpoint is EVIDENCE, not a resume input;
   incomplete-by-clean-deadline-and-no-invalidating-failure → cost, incomplete-by-any-
   other-cause → invalid. A scan test forbids the stale wording in the active files.
9. **Enriched, non-overwritable failure ledgers (J).** Atomic and non-overwritable
   (numbered variants), carrying campaign/attempt/scope, freeze/prereg/contract hashes,
   token SHA, UTC, phase and terminal state; auditable but never a scientific result.

## Unchanged from v6 (frozen science)

Inference contract (exact two-sided sign test + effect band; std = sample ddof1;
α=0.05; bootstrap as descriptor), ALL gate criteria/estimands (G0A/G0B/G0C/G1_weak/
G1_strict/G2/G3/G4), the frozen grids/seeds/thresholds, the G1 arm and best-static
selection-on-selection-seeds protocol, the best-of-frozen-candidate-set comparator, the
G1 hierarchy, and the G2 "permutation-median comparator + cross-seed sign test"
terminology (with its cancellation limitation disclosed).

## Not a rescue

v7 makes the harness custody sound and its interruption policy internally consistent; it
changes no scientific criterion in a result-favoring direction. All gates may still FAIL
or be INCONCLUSIVE.
