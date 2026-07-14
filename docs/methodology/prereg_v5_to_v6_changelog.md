# Pre-registration v5 → v6 changelog (P1.2-D)

Every change is operational/custody/documentation; NO scientific hypothesis, grid,
seed, threshold or criterion changed. Classification per change:

| Change | class |
|---|---|
| Suite crash handler: initialize failure state before the fallible call; preserve the original sanitized error; ledger + `.interrupted`; no UnboundLocalError | operational |
| Integral attempt manifest: inventory every artifact (report, G0A checkpoint, evidence) with size + SHA-256 + role | custody |
| Atomic seal: manifest + SEALED written into staging, fsync, verify, SINGLE atomic rename (no final-without-seal window) | custody |
| `verify_sealed_attempt` rejects tampered checkpoint / extra file / missing artifact / wrong size-or-hash / symlink / unsafe path / tampered manifest or SEALED; requires exactly {manifest, SEALED, inventoried artifacts} | custody |
| G0A report records a RELATIVE checkpoint name + SHA (not an absolute host path); the individual G0A attempt inventories its checkpoint | custody |
| Resume removed entirely; `.interrupted` is TERMINAL; new run = new token/attempt_id from scratch; "crash-recoverable" claim removed | custody |
| `attempt_id = sha256(campaign_id | scope | token_sha)`; `authorization_token_sha256` recorded in reports + manifest; auditor recomputes attempt_id without the raw token; empty/whitespace token rejected | custody |
| `normalized_command` → structured command (interpreter+version, normalized argv, hashes/flags, scope, resolved run-dir, token masked as `<sha256:…>`) | custody |
| G0A: clean-deadline-only INCONCLUSIVE_BY_COST; missing-without-deadline or >20% failed ⇒ EXECUTION_INVALID; INTERRUPTED_BY_COST state record not a science cell; chaos+switching share the taxonomy; chaos deadline covered | operational |
| Global failed-seed policy actually enforced: selection-phase capture + common mask in G1/G2; full failure records in G0B/G0C/G4; G4 per-variant >20% + all-failure aggregation | operational |
| Report schema validates each failure record's structure | operational |
| prereg v6 (canonical CHANGED) + execution contract v4 documents; audits/changelogs; v5 SUPERSEDED sidecar | documentation |

Runners named `*_v2` are the versioned IMPLEMENTATION of the gate runners, NOT
"v2 results". No v2/v3/v4/v5/v6 scientific result exists.

## Hash lineage

| Document | canonical | file SHA-256 |
|---|---|---|
| prereg v5 (superseded) | `f1e02c50…` | `6b0de8a7…` |
| execution contract v3 (superseded) | `228f15b4…` | `f0d487a5…` |
| prereg v6 | `2d7e260f…` | `fd10a220…` |
| execution contract v4 | `eb0e80d9…` | `1861e7bb…` |
