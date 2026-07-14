# freeze_execution_v5.json — SUPERSEDED / NONEXECUTABLE / NEVER RUN

`artifacts/freeze_execution_v5.json` (content_hash
`25c51b40c833f9cbd86cd2f004e9069dc3c910fdef30e5bf27e7240f8fb535a5`, tag
`switchsync-synthetic-execution-v5-freeze` → commit `46dfd9a`) is **SUPERSEDED**.

- **NONEXECUTABLE:** suite crash handler UnboundLocalError; manifest did not
  inventory the G0A checkpoint and recorded an absolute host path; SEALED written
  after the rename (final-without-seal window); weak `verify_sealed_attempt`;
  dead resume path; attempt_id used the raw token; G0A could mislabel a technical
  failure as INCONCLUSIVE_BY_COST; selection-phase failures uncaptured; incomplete
  failed-seed policy. See `docs/audits/p1_2c_independent_audit.md`.
- **NEVER RUN:** no scientific gate was executed against it; no v5 result exists.
- Its tag, commit and manifest are preserved byte-for-byte and NOT rewritten.
- Superseded by `freeze_execution_v6.json` (prereg v6 + execution contract v4), tag
  `switchsync-synthetic-execution-v6-freeze`.
