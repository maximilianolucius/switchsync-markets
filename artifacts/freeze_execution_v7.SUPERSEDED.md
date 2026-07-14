# freeze_execution_v7.json — SUPERSEDED / NONEXECUTABLE / NEVER RUN

`artifacts/freeze_execution_v7.json` (content_hash
`9cbb3335ca98def6d38ebceeefe508db662d5862f092ee9ae2fe7247966699df`, tag
`switchsync-synthetic-execution-v7-freeze` → commit `61a63f3`) is **SUPERSEDED**.

- **NONEXECUTABLE:** prereg v7 lacked the top-level `tolerances` block
  (`{sync_threshold_E12: 0.02, sync_tail_frac: 0.25}`). `run_g0a_exact_v2` and
  `run_g0b_calibrated_v2` read `ctx.prereg["tolerances"]`, so even
  `python3 experiments/run_suite_v2.py --plan` raised `KeyError: 'tolerances'`. The
  P1.2-D/E test fixtures carried the key and masked the incompatibility. The block was
  present in prereg v3 and was accidentally dropped when prereg v4 was created, without
  being declared as a scientific change. See `docs/audits/p1_2e_independent_audit.md`.
- **NEVER RUN:** no scientific gate was executed against it; no v7 result exists.
- Its tag, commit and manifest are preserved byte-for-byte and NOT rewritten.
- Superseded by `freeze_execution_v8.json` (prereg v8 + execution contract v6), tag
  `switchsync-synthetic-execution-v8-freeze`, which restores exactly the v3 tolerances
  block and changes nothing else scientific.
