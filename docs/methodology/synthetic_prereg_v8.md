# Synthetic Pre-Registration v8 (authoritative scientific prereg)

**Document kind:** SCIENTIFIC_PREREG.
**Contract file:** `experiments/configs/synthetic_prereg_v8.json`
**Canonical hash:** `a667434d0d7c5905d62cf81b79699f2799e2597128631cab1e4792bed6053dd9`
**File SHA-256:** `896163891b8b43f42511a1a57294d6075f3b65f33877780daf82cc03a54d568e`
**Operational grids:** `experiments/configs/synthetic_execution_contract_v6.json`
(canonical `6dbe79dd…`, file `80609ef5…`), binding this prereg by canonical hash.
**Supersedes:** prereg v7 (canonical `7fde7def…`); execution freeze v7 is SUPERSEDED /
NONEXECUTABLE / NEVER RUN (`docs/audits/p1_2e_independent_audit.md`).
**Changelog:** `docs/methodology/prereg_v7_to_v8_changelog.md`.
**Status:** frozen for execution; authorizes exactly one cheap-suite run under P1.2-F.
Synthetic only; no real data.

## What v8 changes over v7 (the ONLY scientific change)

v8 **restores the top-level `tolerances` block**:

```json
"tolerances": {
  "sync_threshold_E12": 0.02,
  "sync_tail_frac": 0.25
}
```

- These values are taken **verbatim from prereg v3**, where the block last existed.
- The block was **accidentally dropped when prereg v4 was created** and never declared
  as a scientific change. `run_g0a_exact_v2` and `run_g0b_calibrated_v2` read
  `ctx.prereg["tolerances"]`, so its absence made `run_suite_v2.py --plan` raise
  `KeyError` and freeze v7 NON-EXECUTABLE.
- **No result v2–v7 was ever executed**, so no prior number depended on the missing
  block.
- The restoration changes **no seed, grid, estimand, gate, inference contract or
  decision rule**. Every other section of the prereg is byte-identical to v7.

## Everything else unchanged from v7 (frozen science)

Inference contract, ALL gate criteria/estimands (G0A/G0B/G0C/G1_weak/G1_strict/G2/G3/
G4), the frozen grids/seeds/thresholds, the selection protocols, the custody/interruption
policy and the failure policy are byte-identical to v7. Execution contract v6 is
grid-identical to v5/v4/v3; only its binding of the prereg canonical hash changed.

## Not a rescue

v8 restores an already-frozen value that was accidentally lost; it introduces nothing
new and relaxes no scientific criterion. All gates may still FAIL or be INCONCLUSIVE.
