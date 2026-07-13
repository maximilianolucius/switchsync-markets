# Pre-registration v2 → v3 changelog

**Purpose:** document every change from the frozen prereg v2 to prereg v3, and
prove it predates any v2 experimental result.

## Provenance of the four hashes (P1.2-A forensics)

| Document | canonical | file SHA-256 | git blob | last commit |
|---|---|---|---|---|
| prereg v2 @ tag `switchsync-synthetic-prereg-v2-freeze` | `7e5f1536…` | `2607…` | `750b2fd` | `b940652` |
| prereg v2 @ P1.2 HEAD (mutated) | `be52bf96…` | `1e63787a…` | `cd29737` | `00a4c44` |
| prereg v2 **restored** (P1.2-A) | `7e5f1536…` | `2607…` | (restored) | this phase |
| prereg **v3** (new) | `a3de3d19…` | `7aa8b226…` | (new) | this phase |
| execution contract v1 (new) | `c519857a…` | `f9fd8c26…` | (new) | this phase |

**Root cause:** in P1.2 the frozen prereg v2 file was edited in place to add
execution parameters, changing `7e5f1536`→`be52bf96`. The forensic diff shows the
edit added only execution config (no gate criterion changed). P1.2-A restores the
frozen v2 bytes (`7e5f1536`) and moves all forward progress into v3 (scientific) +
execution contract v1 (operational).

## What changed, item by item

### Restored / preserved
- `synthetic_prereg_v2.json` and `.md` restored to their frozen bytes; the tag is
  untouched. A SUPERSEDED marker is added as a sidecar
  (`synthetic_prereg_v2.SUPERSEDED.md`), not by editing the frozen files.

### Moved out of the prereg into the execution contract v1 (operational)
- The `surrogate_paired` grid (N, N_IL, K, H, kappa, cycles, variable-dwell multiset, best-static search count, signed neg-fraction).
- G0A `record_every`; G0C `n_steps`/`transient_steps`/`renorm_every`.
- All concrete gate grids (G0A sizes/T_swt/total_time, G0B, G0C sigma/T_swt, G4).
- The G3 stage list (heterogeneity/directed/signed values).

### Added to the prereg v3 (scientific — the reason v3 is required)
- **Statistical contract:** experimental unit, paired comparison, estimators, the bootstrap-CI inferential rule (n_boot, boot_seed), the exact PASS/FAIL/INCONCLUSIVE decision rule, min effect size (floor 0.02), gate hierarchy, multiplicity, failed-run handling.
- **Best-static policy:** admissible space, identical budget, optimization algorithm, and the DISJOINT selection vs evaluation seed split (fixing the F defect where v1 optimized and evaluated on the same realization).
- **Seed policy:** `paired_causal` (v2) replaced by disjoint `paired_selection` [41–48] and `paired_evaluation` [81–88] (8 each; 4+4 would make the inferential rule unsatisfiable).
- **G0A cost rule:** frozen wall-time/size/seed budget, timeout rule, partial-grid rule (never PASS/FAIL), append-only checkpoint, no post-hoc budget revision.
- **Outcome vocabulary:** INCONCLUSIVE_BY_COST as a reason_code (not a verdict); NOT_RUN as a suite state.

### Unchanged (scientific criteria carried verbatim in spirit)
- FHN model params, gate goals and accept thresholds (frac≥0.5 sync rules, G4 0.6/0.5 thresholds, G3 advantage>0), the H3 removal, and the interpretation discipline.

## Proof this predates any v2 result

No v2 gate runner has ever been executed at contract scale: there are **no
`*_v2.json` result files** in `experiments/reports/` (only v1 `*.superseded.json`
sidecars). All P1.2 and P1.2-A commits are audit/implementation/freeze only; the
execution contract requires `--i-am-authorized` plus the frozen hashes, which has
never been supplied. Therefore v3 was frozen strictly before any v2 result exists.
