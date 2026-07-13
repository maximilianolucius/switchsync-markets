# Synthetic Pre-Registration v4 (authoritative scientific prereg; NOT EXECUTED)

**Document kind:** SCIENTIFIC_PREREG.
**Contract file:** `experiments/configs/synthetic_prereg_v4.json`
**Canonical hash:** `847a8a8ca484e39e900fc894934fcc5cc0d58195c84c5739d9d9e18836440cf8`
**File SHA-256:** `36dd76e0de17e68638976c7aa63aa0d523bb644edcda75e834cf832a6b7bb7c6`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v2.json`
(canonical `8738b591…`, file `919a3d8b…`), which binds this prereg by canonical hash.
**Supersedes:** prereg v3 (`a3de3d19…`) + execution contract v1 (`c519857a…`); the v3
execution freeze is SUPERSEDED / NONEXECUTABLE / NEVER RUN.
**Basis:** `docs/audits/p1_2a_independent_audit.md`, `docs/methodology/prereg_v3_to_v4_changelog.md`.
**Status:** frozen for execution, **NOT executed**. Synthetic only; no real data.

## Inference (single rule, shared)

`src/metrics/inference.py:paired_decision` — exact two-sided sign test on non-zero
paired differences (8/8 equal signs → p=0.0078125), effect band = max(3·sample_std_ddof1,
floor), zeros dropped and reported, α=0.05. Bootstrap CI is a descriptor only. Used
identically by G1_weak, G1_strict, G2, G3 and the G4 baseline test.

## Gates (see JSON for exact values)

- **G0A** exact-paper (σ=0.1): durable external checkpoint, chunked deadline, chaos
  prerequisite; PASS requires EVERY deciding size {200,400} to have all fast T_swt≤25
  synchronize and all slow T_swt≥120 not; N=100 non-deciding; partial → INCONCLUSIVE_BY_COST.
- **G0B** calibrated demonstration (σ=1.5): fast/slow "ALL" semantics; >20% failed → EXECUTION_INVALID.
- **G0C** minimal MSF: anti-phase channels only; reason codes PREREQ_FAIL / PARTIAL_NO_TSWT_DEPENDENCE.
- **G1_weak** switching vs static-sparse (arm frozen on selection seeds; shared rule).
- **G1_strict** vs average AND best-of-frozen-candidate-set (NOT best admissible); NOT_INTERPRETABLE unless G1_weak PASS.
- **G2** order via permutation null (median comparator; signed paired test); NOT_INTERPRETABLE unless G1_weak PASS.
- **G3** robustness (shared inference per stage; faithful+mild gate; genuine per-seed signed negatives + numeric budget equality).
- **G4** identifiability (exact horizon; four conditions incl. defined beats-baseline; failed handling).

## Custody

External `--run-dir`, `run_id` from the hashes, transactional suite (staging → atomic
publish, failure ledger, no partial success bundle), reports carry runner + orchestrator
SHAs, no overwrite/resume/retry. Results never inside the frozen repo.

## Not a rescue

v4 does not turn any result positive; it makes the contract executable. G1_strict,
G2 and G4 may still INCONCLUSIVE/FAIL; those are acceptable, reportable outcomes.
