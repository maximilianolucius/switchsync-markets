# Pre-registration v3 → v4 changelog (P1.2-B)

Prereg v3 stayed scientifically sound in its criteria but the v3 EXECUTION freeze
was non-executable (see `docs/audits/p1_2a_independent_audit.md`). v4 splits into a
scientific prereg (v4) and an operational execution contract (v2) and closes the
defects. Because estimands, selection and inference changed, this is a genuine
prereg revision (v4), not a re-freeze.

## Hash lineage

| Document | canonical | file SHA-256 |
|---|---|---|
| prereg v3 (superseded) | `a3de3d19…` | `7aa8b226…` |
| execution contract v1 (superseded) | `c519857a…` | `f9fd8c26…` |
| **prereg v4** | `847a8a8c…` | `36dd76e0…` |
| **execution contract v2** | `8738b591…` | `919a3d8b…` |

## Changes (v3 → v4)

- **Inference (C):** single shared `paired_decision` (exact two-sided sign test +
  effect band; std = sample ddof1 of paired differences; explicit zero drop). The
  false "8 seeds cannot reach p<0.05" claim is corrected (8/8 → 0.0078125). Bootstrap
  demoted to a descriptor with a small-n caveat; the rule no longer mixes p<0.05 with
  a bootstrap-CI rule.
- **G1 (B):** rate ARM selected on `paired_selection` and FROZEN before evaluation
  (no per-eval-seed `max`); static comparator renamed **best-of-frozen-candidate-set**
  (no "best admissible" claim over the 134596-subset universe); canonical candidate
  ordering + lexicographic tie-break; G1_strict & G2 NOT_INTERPRETABLE unless G1_weak
  PASS.
- **G2 (D):** permutation null (median of `g2_n_perm` frozen order-permutations per
  seed) + signed paired test on `gamma_ordered − median_perm`; no abs-vs-zero.
- **G3 (E):** shared inference per stage; per-seed paired diffs and per-seed operator
  metadata for ALL seeds; failed-run handling; gate PASS iff faithful AND mild both
  PASS; signed stage verified per seed for a strictly negative weight AND numeric
  pre-rescale budget equality vs the unsigned comparator.
- **G4 (F):** exact-horizon assertion (`schedule.total_steps == H`); four frozen PASS
  conditions including a DEFINED "beats the baseline" (paired precision margin, shared
  rule, floor 0.05); >20% failed/nonfinite → EXECUTION_INVALID.
- **G0A (G):** durable append-only checkpoint OUTSIDE the repo (fsync, crash-recovery,
  duplicate-reject, corruption-detect); chunked wall-clock deadline; frozen quantifiers
  (deciding sizes {200,400}, N=100 non-deciding, chaos prerequisite, ALL-cells rule);
  partial grid → INCONCLUSIVE(INCONCLUSIVE_BY_COST).
- **G0B/G0C (H):** G0B fast/slow "ALL" semantics + failed handling; G0C emits
  reason_code PARTIAL_NO_TSWT_DEPENDENCE / PREREQ_FAIL.
- **Custody (I):** external `--run-dir`, `run_id` from hashes, transactional suite
  (staging → atomic publish, failure ledger, no partial success bundle), reports carry
  the scientific runner SHA AND the orchestrator SHA, sequential individual runners
  share a run_id, `--cheap-only`/`--include-g0a-expensive` semantics with a rejected
  contradiction, and no overwrite/resume/retry without a frozen policy.
- **Seed blocks:** stages and identifiability enlarged to 8 seeds so the exact sign
  test is attainable.

## Proof this predates any result

There are no `*_v2.json` result files anywhere in the repo (only v1
`*.superseded.json` sidecars). The execution contract requires `--i-am-authorized`
+ the frozen hashes + an external run-dir, never supplied. v4 is frozen strictly
before any v2/v3/v4 result exists.
