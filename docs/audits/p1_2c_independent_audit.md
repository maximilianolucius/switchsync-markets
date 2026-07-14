# P1.2-C Independent Audit — execution freeze v5 is NON-EXECUTABLE

**Subject:** `switchsync-synthetic-execution-v5-freeze` → commit `46dfd9a`; prereg v5
(`f1e02c50…`) + execution contract v3 (`228f15b4…`) + freeze v5 (`25c51b40…`).
**Authenticity/reproducibility PASSED** (complete bundle, identical snapshot,
correct HEAD/tag, exact hashes, 94-file freeze verified, 95 tests in a clean clone).
**Verdict:** blocking operational + scientific defects; NOT authorizable for
execution. Repaired in prereg v6 + execution contract v4 + freeze v6.

## Defects

| # | Area | Defect in v5 | Repair (v6) |
|---|---|---|---|
| B1 | suite | if `_run_gates()` raised before its return was assigned, the crash handler used an unbound `failures` and escaped with `UnboundLocalError` (a secondary exception) | crash state initialized before the fallible call; original sanitized error preserved; failure ledger + `.interrupted`; exit≠0; no final/SEALED |
| C1 | manifest | the manifest inventoried only `reports`; the G0A checkpoint was not inventoried; the G0A report recorded an ABSOLUTE host path for the checkpoint | integral inventory of ALL artifacts (report, G0A checkpoint, evidence) with size + SHA-256 + role; G0A report records a RELATIVE checkpoint name + its SHA |
| C2 | seal | SEALED was written AFTER the rename → a final-without-SEAL window | manifest + SEALED written INTO staging, fsync, verify, then a SINGLE atomic rename; no unsealed window |
| C3 | verify | `verify_sealed_attempt` only checked report SHAs; it accepted extra files, symlinks, missing/corrupt checkpoints, `..`/absolute names | rejects tampered checkpoint, unexpected/extra file, missing artifact, wrong size/hash, symlink/non-regular, unsafe path, tampered manifest/SEALED; requires EXACTLY {manifest, SEALED, inventoried artifacts} |
| D1 | policy | v5 documented a resume path but always rejected it (dead functionality) | resume removed entirely; `.interrupted` is TERMINAL; a new run needs a new token (new attempt_id) and starts from scratch; "crash-recoverable" claim removed |
| E1 | identity | `attempt_id` used the RAW token; an auditor could not recompute it from records without the secret | `token_sha = sha256(token)`; `attempt_id = sha256(campaign\|scope\|token_sha)`; `authorization_token_sha256` stored in reports + manifest; token rejected if empty/whitespace |
| E2 | command | `normalized_command` was a bare string | structured command: resolved interpreter+version, normalized argv (token masked `<sha256:…>`), hashes/flags, scope, resolved run-dir |
| F1 | G0A | a technical failed/missing cell without a deadline could still be labelled INCONCLUSIVE_BY_COST | only a clean frozen-deadline expiry yields INCONCLUSIVE_BY_COST; missing-without-deadline or >20% failed ⇒ EXECUTION_INVALID; the INTERRUPTED_BY_COST state record is not counted as a science cell; chaos + switching share the structured taxonomy |
| G1 | G1/G2 | failures during SELECTION were not captured; arm/best-static could be chosen from partial results | selection-phase failure capture with a COMMON mask of complete selection seeds; >20% selection failures ⇒ EXECUTION_INVALID |
| G2 | G0B/G0C/G4 | G0B stored integer seed lists (not failure records); G4 applied >20% only to the synchronous variant and reported only its failures | full failure records everywhere; G4 applies >20% per configured variant and aggregates ALL failures; G0C nonfinite ⇒ full failure record |
| G3 | schema | validated only the existence of `failures`, not each record's structure | schema validates every failure record has {exception_type, message, seed, cell, timestamp_utc} |

## Disposition

Execution freeze v5 → **SUPERSEDED / NONEXECUTABLE / NEVER RUN** (sidecar
`artifacts/freeze_execution_v5.SUPERSEDED.md`). Tag and commit preserved, not
rewritten. No v5 result was ever produced.
