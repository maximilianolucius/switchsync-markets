# freeze_execution_v4.json — SUPERSEDED / NONEXECUTABLE / NEVER RUN

`artifacts/freeze_execution_v4.json` (content_hash
`ba102c4a568be0cd6496619fe4b7fdaf6be22f16fabdceaaa68e02fb04c6e288`, tag
`switchsync-synthetic-execution-v4-freeze` → commit `04c33309`) is **SUPERSEDED**.

- **NONEXECUTABLE:** defects in runner provenance (orchestrator SHA recorded as the
  runner SHA; forgeable `--orchestrator-sha`), attempt identity (colliding run_id
  across scopes), custody (mutable published bundles, no manifest/seal/lock),
  crash policy (contradictory, no frozen resume), checkpoint ledger (no hash chain,
  duplicates silently accepted), and the G0A deadline (chaos prerequisite not
  covered; N=100 could consume the budget first). See
  `docs/audits/p1_2b_independent_audit.md`.
- **NEVER RUN:** no scientific gate was executed against it; no v4 result exists.
- Its tag, commit and manifest are preserved byte-for-byte and NOT rewritten.
- Superseded by `freeze_execution_v5.json` (prereg v5 + execution contract v3), tag
  `switchsync-synthetic-execution-v5-freeze`.
