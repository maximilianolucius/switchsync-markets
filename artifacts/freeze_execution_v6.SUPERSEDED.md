# freeze_execution_v6.json — SUPERSEDED / NONEXECUTABLE / NEVER RUN

`artifacts/freeze_execution_v6.json` (content_hash
`c525f11f7b3485589f4141d5055ac76ec3b60f17f4974d7b55dc9cfa4eda782d`, tag
`switchsync-synthetic-execution-v6-freeze` → commit `ca55940`) is **SUPERSEDED**.

- **NONEXECUTABLE:** an invalid `manifest_content_hash`/inventory could reach
  `os.replace()` (no single pre-rename validation); staging was not required flat and
  the verifier could raise on a malformed manifest; the inventory→manifest→seal cycle
  ran outside the failure handler (a custody failure escaped, a post-rename failure
  could leave a successful-looking final); the G1/G2 "common" mask left the best-static
  candidate universe unprotected; the G0A verdict checked missing-cells before the
  failure policy (a technical failure could be laundered into INCONCLUSIVE_BY_COST) and
  counted the state record as a science cell on a non-monotonic clock; G0B/G0C did not
  always emit full failure records; and prereg v6 still carried the contradictory
  `crash-recoverable` / continuation-requires-authorization / partial-rule wording.
  See `docs/audits/p1_2d_independent_audit.md`.
- **NEVER RUN:** no scientific gate was executed against it; no v6 result exists.
- Its tag, commit and manifest are preserved byte-for-byte and NOT rewritten.
- Superseded by `freeze_execution_v7.json` (prereg v7 + execution contract v5), tag
  `switchsync-synthetic-execution-v7-freeze`.
