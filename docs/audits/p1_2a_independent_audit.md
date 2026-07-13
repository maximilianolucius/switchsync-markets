# P1.2-A Independent Audit — execution freeze v3 is NON-EXECUTABLE

**Subject:** `switchsync-synthetic-execution-v3-freeze` → commit `69c542b`; prereg v3
(`a3de3d19…`) + execution contract v1 (`c519857a…`) + freeze v3 (`a6a9eba0…`).
**Verdict:** the freeze's internal hashes are correct and 80 tests pass, but the
contract is **NOT scientifically executable**. Passing tests were NOT sufficient
validation. Recorded defects below; repaired in prereg v4 + execution contract v2 +
freeze v4 (see `prereg_v3_to_v4_changelog.md`).

## Defects that make v3 non-executable

| # | Area | Defect in v3 | Repair (v4) |
|---|---|---|---|
| B1 | G1 | `best_switch = max(gamma_fast, gamma_intermediate, gamma_slow)` computed per EVALUATION seed = post-hoc arm selection | arm selected on SELECTION seeds only, FROZEN before evaluation |
| B2 | G1_strict | comparator called "best admissible static" but only ~248 of C(24,6)=134596 subsets searched | renamed "best-of-frozen-candidate-set"; no best-admissible claim |
| B3 | G1 | candidate set not canonically ordered / no tie-break | canonical sorted tuples + lexicographic tie-break |
| B4 | G1/G2 | hierarchy not enforced | G1_strict & G2 NOT_INTERPRETABLE unless G1_weak PASS |
| C1 | inference | doc claimed a sign test on 8 seeds "cannot reach p<0.05" — FALSE (8/8 → p=0.0078125) | corrected; exact sign test adopted |
| C2 | inference | mixed "p<0.05" with a bootstrap-CI-only rule | single rule = exact sign test + effect band; bootstrap is a descriptor only |
| C3 | inference | "std" undefined; no zero handling; two runners had separate decision code | one shared `paired_decision`; std=sample ddof1; explicit zero drop |
| D1 | G2 | `_decide(abs(gamma_ordered - gamma_shuffled))` = abs-vs-zero, not a null | permutation null (median of n_perm frozen permutations), signed paired test |
| E1 | G3 | `advantage_mean > 0` instead of an inferential rule; only last seed's metadata kept | shared inference per stage; per-seed metadata for ALL seeds; faithful+mild gate |
| E2 | G3 | signed "budget" never numerically compared | per-seed negative-weight check + numeric pre-rescale budget equality vs unsigned |
| F1 | G4 | horizon: H=600 but schedule.total_steps=606 (H//dwell+1) | exact-horizon assertion (H//dwell, total==H) at runtime |
| F2 | G4 | "beats baseline" undefined; PASS not requiring all four | 4 frozen conditions incl. paired precision-margin baseline test |
| F3 | G4 | no failed/nonfinite handling | >20% failed → EXECUTION_INVALID |
| G1 | G0A | `completed=[]` in memory = not a durable checkpoint | durable append-only JSONL outside repo (fsync, crash-recovery, dup-reject, corruption-detect) |
| G2 | G0A | deadline only checked between whole simulations | chunked deadline (abort_check every chunk_steps) |
| G3 | G0A | no frozen quantifier; a single N=100 cell could decide | deciding sizes {200,400}; N=100 non-deciding; chaos prerequisite; ALL-cells quantifier |
| I1 | custody | reports written INSIDE the frozen repo | external --run-dir, run_id from hashes |
| I2 | custody | no transactional publish / failure ledger | staging + atomic publish + failure ledger; no partial success bundle |
| I3 | custody | reports lacked orchestrator SHA; overwrite/resume unspecified | orchestrator SHA recorded; no-overwrite/resume/retry enforced |

## v3 tests that were empty / incomplete (A.4 — passing ≠ validated)

- **Tautological:** `test_v2_msf_offset_is_Tswt_not_2Tswt` asserted `np.max(np.abs(g0 - g0)) < 1e-12` — trivially true; replaced by a real T_swt-vs-2·T_swt distinction (J.15).
- **Field-existence only:** `test_g1_g2_end_to_end_tiny_separate_verdicts` merely checked keys existed; it did not test arm-selection integrity, the hierarchy, or the null. Superseded by J.1–J.7.
- **Direction-agnostic G3:** the v3 G3 test only checked `advantage_mean` sign, not an inferential decision or per-seed budget — superseded by J.8/J.9.
- **No G0A durability test, no G4 horizon test, no failed-run tests, no descendant test reaching `_is_descendant`** — all added in J.13/J.10/J.12/J.16.

## Disposition

Execution freeze v3 → **SUPERSEDED / NONEXECUTABLE / NEVER RUN** (sidecar
`artifacts/freeze_execution_v3.SUPERSEDED.md`). Its tag and commit are preserved
byte-for-byte and NOT rewritten. No v3 result was ever produced.
