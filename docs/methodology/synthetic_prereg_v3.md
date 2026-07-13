# Synthetic Pre-Registration v3 (scientific; NOT EXECUTED)

**Document kind:** SCIENTIFIC_PREREG (criteria, estimands, seed policy, statistical contract, cost rule).
**Contract file:** `experiments/configs/synthetic_prereg_v3.json`
**Canonical hash:** `a3de3d199cda7007d474e1b8c1c2d9adb515d412835c5d5761bf4894458d83f5`
**File SHA-256:** `7aa8b226ff87ea217894d22a0999418530031f12bdc561f49dcde4f254ec5af5`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v1.json` (canonical `c519857a…`, file `f9fd8c26…`), which binds this prereg by canonical hash.
**Supersedes:** `synthetic_prereg_v2.json` (canonical `7e5f1536…`, file `2607…`), restored to its frozen bytes and marked SUPERSEDED (tag `switchsync-synthetic-prereg-v2-freeze` untouched).
**Changelog:** `docs/methodology/prereg_v2_to_v3_changelog.md`.
**Status:** frozen for execution, **NOT executed**. Synthetic only; no real data.

## Why v3 exists (lineage)

P1.2 mutated the frozen prereg v2 file by appending execution parameters (a `g0a`
seed block, `surrogate_paired`, G0A `record_every`, G0C timing). The forensic diff
(P1.2-A) shows **no gate criterion, estimand, acceptance rule or tolerance
changed** — the additions were an *execution configuration* (Case 2). Separately,
the **statistical contract** (best-static selection-vs-evaluation seed separation,
effect sizes, the inferential rule, multiplicity, tie and failed-run handling) was
**never closed** in the frozen prereg. Closing it is a genuine scientific revision,
which is why a new **v3** prereg is required rather than re-freezing v2. The
operational parameters were separated into the execution contract v1.

No v2 results were ever produced, so nothing here is post-hoc.

## Separation of concerns

- **This prereg (v3, scientific):** gate goals + estimands + accept rules; frozen
  seed blocks (including the disjoint `paired_selection` / `paired_evaluation`
  split); the statistical contract; the best-static policy; the G0A cost rule; the
  outcome/reason-code vocabulary; reporting requirements.
- **Execution contract (v1, operational):** the concrete grids (sizes, T_swt grids,
  paired construction, MSF timing, G4 grid, G3 stages).

Runners require and record BOTH documents' canonical + file hashes.

## Statistical contract (closed here — see JSON for exact values)

- **Experimental unit:** one seed in the gate's frozen seed block.
- **Paired comparison:** within-seed treatment-minus-comparator differences, aggregated across the block.
- **Estimators:** surrogate transverse contraction rate γ (exact ordered product); FHN tail-mean E12; identifiability precision/recall + same-realization contraction correlation.
- **Inferential rule:** a bootstrap 95% CI (n_boot=2000, boot_seed=20260713) over the 8 evaluation seeds — chosen because a sign test on 8 seeds cannot reach p<0.05.
- **Decision rule:** band = max(3·pooled_std, floor=0.02). PASS iff mean paired diff > band AND CI-low > 0; FAIL iff mean < −band AND CI-high < 0; else INCONCLUSIVE (reason_code=TIE if |mean| ≤ band). Ties never become PASS.
- **Gate hierarchy:** G1_weak precedes G1_strict; G2 interpreted only if G1_weak PASSes; no gate borrows another's data.
- **Failed-run handling:** a seed that raises / returns non-finite is FAILED; >20% failed ⇒ EXECUTION_INVALID.

## Best-static policy (F fix)

The best admissible static subset (same N_IL edge budget) is **selected** by max
mean γ over the `paired_selection` operators, then **frozen** and **evaluated** on
the disjoint `paired_evaluation` operators — so it is never optimized and judged on
the same realization.

## G0A cost rule (frozen before measurement)

Wall-time budget 86400 s; mandatory minimum size N≥200; ≥3 completed seeds; on
timeout, STOP and write verdict=INCONCLUSIVE, reason_code=INCONCLUSIVE_BY_COST with
the completed-cell list. A partial grid may **never** be PASS or FAIL. Checkpoints
are append-only; no cell may be dropped to obtain a favorable verdict. The budget
is frozen here and may not be revised after seeing any G0A output.

## Outcome vocabulary

Report verdicts: PASS, FAIL, INCONCLUSIVE, EXECUTION_INVALID. `INCONCLUSIVE_BY_COST`
is **not** a verdict — it is `verdict=INCONCLUSIVE` with `reason_code=INCONCLUSIVE_BY_COST`.
`NOT_RUN` is a suite state (no report written), never a verdict.
