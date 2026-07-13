# Synthetic Pre-Registration v2 (corrected, executable — NOT YET EXECUTED)

**Contract file:** `experiments/configs/synthetic_prereg_v2.json`
**Canonical config hash:** `7e5f1536e848bf53e3803217a00fff2cee0963d71af5099711ec7463283831d7`
**Config file SHA-256:** `2607961200a280e4097a6289787fd063a97e3e4d770747f992492be66410517e`
**Supersedes:** `synthetic_prereg_v1.md` / `.json` (canonical `abbd95…`, file `6d19cf5…`).
**Audit basis:** `docs/audits/p1_v1_independent_audit.md` (defects D1–D13).
**Status:** frozen for execution but **NOT executed**. Synthetic only; no real data.

This v2 contract repairs the confounds that made v1 unfit to certify verdicts. It records the estimands, seed blocks, tolerances, statistical tests, tie handling, and the full outcome vocabulary *before* any v2 run.

---

## What changed from v1 (defect → repair)

| Defect | v1 problem | v2 repair |
|---|---|---|
| D1 | freeze omits runners/`_common`/tests/evaluators | freeze v2 covers src + all runners + `_common` + tests + prereg + eval + lockfiles + ledger + PDF SHA |
| D2 | verifier blind to added files; no content hash | `verify_manifest_v2` re-scans the tracked spec (detects added files), verifies a stored==recomputed content hash, never regenerates |
| D3 | canonical vs raw-bytes hash conflated | every report records BOTH `config_canonical_hash` and `config_file_sha256` |
| D4 | G1 PASS recorded while artifact says fast loses to average | G1 split into **G1_weak** (vs static-sparse) and **G1_strict** (vs average graph AND best admissible static); verdict follows the artifact |
| D5 | rate arms unpaired, horizons 242/252/300 | `paired_switching`: one base sequence per seed, exact `H=240`, identical average operator, paired per-seed contrasts |
| D6 | `shuffled_dwell` a no-op (constant dwells) | `variable_dwell_schedule` with a frozen non-constant dwell distribution; null asserted non-trivial |
| D7 | MSF channels same phase (`g(t+2·T_swt)`) | `smooth_square_gamma_v2` uses a half-period shift `g(t+T_swt)`; anti-phase prerequisite tests gate G0C |
| D8 | signed stage produced 0/positive weights | `build_basis_operator_v2` introduces ≥1 strictly negative coupling, budget preserved, metadata reported |
| D9 | H3 confounds coverage and reachability | **H3 removed as a gate**; `temporal_reachability_ratio` retained as a reported descriptor, no isolation claim |
| D10 | contraction corr used an independent trajectory | `simulate_observed_v2` records `d_true` (same realization); `contraction_corr_same_realization` uses it |
| D11 | LOCF called "the Epps effect" | reported as "asynchrony/LOCF (Epps-like) degradation" only |
| D12 | σ_12=1.5 presented as reproduction | G0 split: **G0A exact-paper** (σ=0.1) vs **G0B calibrated demonstration** (σ=1.5, N=40) |
| D13 | tests caught none of the above | `tests/test_v2_corrections.py`, `tests/test_freeze_v2.py`: paired horizon, non-constant dwell, anti-phase, negative weight, same-realization corr, tamper/added/missing/env/overwrite/path-independence |

## Gates (see JSON for exact parameters)

- **G0A exact-paper reproduction** — σ_12=0.1, N∈{100,200,400}, T=4000. Outcomes: PASS / FAIL / **INCONCLUSIVE_BY_COST** (never silently replaced by G0B). Flagged EXPENSIVE.
- **G0B calibrated demonstration** — σ_12=1.5, N=40. Outcomes: DEMONSTRATED / NOT_DEMONSTRATED. May not claim N-dependence of the threshold without a multi-N switching grid.
- **G0C minimal MSF** — corrected anti-phase channels; prerequisite phase tests must pass or the gate is INVALID.
- **G1_weak** — switching vs static-sparse of equal instantaneous density (paired). PASS/FAIL/TIE.
- **G1_strict** — switching must beat the average graph AND the **best admissible static** under the same edge budget (bounded search). Prior: the FAST arm is not expected to beat the average (averaging theory); any advantage is expected at intermediate rates (Zhang–Strogatz) and is deferred to the intermediate-rate branch.
- **G2 order** — paired schedules, exact horizon, identical average operator; genuine non-constant dwell null. PASS / AGG_CONNECTIVITY_IF_TIE / FAIL.
- **G3 robustness** — implemented stresses only (heterogeneity, directed, genuine signed). LIMITED if the advantage vanishes at a stage; INVALID if a stress is not truly implemented.
- **G4 identifiability** — same-realization `d_true`; past-only estimator; async reported as Epps-like degradation. PASS/FAIL.

## Estimands, seed blocks, tolerances, ties (frozen)

- **Estimands:** paired per-seed differences in the transverse contraction rate γ (surrogate) and tail-mean E12 (FHN); precision/recall and same-realization contraction correlation (G4).
- **Seed blocks:** fixed per gate in `seed_blocks` (e.g. paired_causal = 41–48).
- **Tolerances:** sync threshold E12 < 0.02; significance requires |mean paired diff| > 3·pooled_std AND a paired sign/Wilcoxon test p<0.05.
- **Ties:** differences within 3·pooled_std are declared TIE (neither PASS nor FAIL for that comparison) — no rounding a tie into a PASS.
- **Outcome vocabulary:** PASS, FAIL, INCONCLUSIVE, INCONCLUSIVE_BY_COST, TIE, INVALID, DEMONSTRATED, NOT_DEMONSTRATED, LIMITED, AGG_CONNECTIVITY_IF_TIE.

## Reporting requirements (frozen)

Every v2 report must embed: `config_canonical_hash`, `config_file_sha256`, `freeze_content_hash`, the runner file SHA, and the git commit SHA. Atomic write, refuse-overwrite, no silent `H//dwell+1`, and any capped/dropped coverage must be logged.

## Not part of the rescue of v1

This contract does not attempt to turn any v1 result positive. G1_strict, G2 and G4 may still FAIL or TIE; those are acceptable outcomes and must be reported as such.
