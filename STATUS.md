# STATUS

**Phase:** P0–P1 complete (synthetic only). **Real data used: NONE.**
**Frozen contract:** `experiments/configs/synthetic_prereg_v1.json`, SHA-256 `abbd95154d3fba0c417d7bdbd70752e225a01e4e2d14d33291cab039ec883e82`.
**Freeze manifest:** `artifacts/freeze_manifest_v1.json` — 19 files (src + config), verified `ok=True`.
**Environment:** Python 3.14.3; numpy 2.4.4, scipy 1.17.1, matplotlib 3.10.9 (pinned in `requirements.lock.txt`).
**Tests:** 20 passed.

---

## Gate outcomes

| Gate | Verdict | Evidence |
|---|---|---|
| **G0 Reproduction** | **PASS** | Isolated layer chaotic: λ_max = +0.018 / +0.011 / +0.021 at N=40/100/200 (Benettin, RK4 co-integrated). Fast switching synchronizes (frac_synced = 1.0 for T_swt ≤ 40), degrading monotonically to 0.2 at T_swt = 300; finite max switching time — reproduces the paper's qualitative mechanism (Figs. 3–5). |
| **G1 Causal isolation** | **PASS (weak) / FAIL (strict)** | Fast switching beats the equal-density static-sparse graph (surrogate γ: +0.111 vs −0.030, Δ=+0.142 ≫ 3σ band 0.014) and slow switching (−0.023, Δ=+0.135). FHN confirms (E12: fast 0.0 vs static 0.084 vs slow 0.112). **But the average graph contracts MORE** (γ_avg = +0.253 vs fast +0.111; Δ=−0.142): switching does **not** beat aggregate connectivity. |
| **G2 Temporal order** | **AGG_CONNECTIVITY** (evidence favors aggregate connectivity) | Order effect at intermediate rate = +0.0035, inside the 0.014 noise band; shuffled-order ≈ ordered at every rate (fast: +0.107 vs +0.111). Temporal order adds nothing beyond the time-average. |
| **G3 Robustness** | **PASS (weak advantage)** | γ_fast − γ_static > 0 through all stress stages: faithful +0.138, mild-het +0.164, strong-het +0.235, directed +0.146, signed +0.178. The switching-vs-static advantage is robust; the average-graph dominance persists throughout. |
| **G4 Identifiability** | **FAIL** | Venue-difference (factor-free) estimator: precision = recall = 0.35 (base rate 0.25; bar 0.6). Beats the factor-confounded level-correlation estimator (0.20) by 0.14, but far below threshold. Contraction correlation 0.22 (bar 0.5). Under asynchronous observation it collapses to chance (0.26) and contraction-correlation goes negative — the Epps effect destroys identifiability. |
| MSF (G0 support) | **PARTIAL** | Switched coupling gives transverse contraction (Ψ<0) but the stability boundary does not depend on T_swt in the minimal N=2 build, because that isolated layer is a limit cycle (λ_max ≈ −0.001, verified), not chaotic. The switching-time dependence is instead reproduced by the large-N direct simulation (G0). |

### Auxiliary isolation results (H3, informational)
- **Coverage** matters: fast switching confined to a fixed subset (no coverage) fails (γ = −0.032, same as static); Δ vs full-coverage fast = +0.143.
- **Reachability** matters: high node-sweep with broken temporal reachability fails (γ = −0.036); Δ vs fast = +0.147.
- Confirms node-sweep coverage ≠ temporal reachability (the `G_switch`/node-sweep critique).

---

## Honest synthesis

1. **The mechanism is real in the model (A):** switching a sparse set of channels synchronizes chaotic layers when it is fast enough (G0, G1-weak, G3).
2. **It is not more than aggregate connectivity (B, identifiability of concept):** the time-averaged graph contracts at least as strongly, and temporal order adds nothing beyond it (G1-strict FAIL, G2 → AGG_CONNECTIVITY). This is exactly what fast-switching/averaging theory (Belykh 2004; Stilwell 2006) predicts. The defensible content is narrower: **fast switching lets a sparse, capacity-limited system emulate the denser average graph**, decisively beating the equal-density static graph.
3. **It is only weakly identifiable from observations (C):** and not at all under realistic asynchrony (G4 FAIL). Once the system synchronizes, the instantaneous active-link set is washed out; a common factor confounds naive estimators to chance.

A positive G0 did **not** imply positive B or C — as the project design anticipated.

## GO / NO-GO recommendation for the empirical phase

**NO-GO for a predictive/operational empirical study.** **Conditional-GO only for a falsification/bounding study** (test whether temporal switching carries information beyond density + average graph + common factor + DCC, with a strong prior that it does not, and identifiability as the binding constraint). Any empirical phase requires a new explicit authorization and must touch no real data until then. See `docs/methodology/empirical_stage_proposal.md`.

## v1-audit addendum (2026-07-13, phase P1.1)

The v1 gate table above is **preserved as the historical v1 record** but is superseded by the independent audit `docs/audits/p1_v1_independent_audit.md`. Corrected dispositions:

| Gate | v1 verdict (above) | Post-audit disposition |
|---|---|---|
| G0 | PASS | **DOWNGRADED_TO_CALIBRATED_DEMONSTRATION** (σ_12=1.5 was hand-tuned; split into G0A exact / G0B calibrated / G0C MSF in v2) |
| G1 / G2 | PASS / AGG_CONNECTIVITY | **SUPERSEDED_PENDING_PAIRED_RERUN** (unpaired arms, horizons 242/252/300, no-op dwell null; recorded PASS contradicted the artifact) |
| G3 signed | PASS | **INVALID** (signed stage produced no negative weights) |
| H3 | (informational) | **INVALID** (controls confound coverage and reachability); removed as a gate in v2 |
| G4 | FAIL | **FAIL_SUPPORTED_BY_PRECISION_RECALL_ONLY**; `contraction_corr` **INVALID** (independent trajectory) |
| MSF | PARTIAL | **INVALID** (channels driven in the same phase) |
| freeze v1 | ok | **NONEXECUTABLE_AS_SCIENTIFIC_FREEZE** (omits runners/tests; blind to added files; two conflated hashes) |

**GO/NO-GO recommendation — softened.** The v1 statement of a "strong prior that switching does not beat aggregate connectivity" is **withdrawn**: it rested on a confounded contrast and on the time-average (not the best admissible static) as comparator, and Zhang–Strogatz (2021) show a budget-constrained, curvature-driven advantage can exist at intermediate rates. The current position is **NO-GO for any predictive/empirical study**, and the *scientific* open questions (G1-strict, G2, and the intermediate-rate advantage) are **UNRESOLVED pending the v2 paired reruns**, not settled negatively. Identifiability (G4) remains the binding constraint on the empirical side.

## Artifacts

- Reports: `experiments/reports/*.json` (atomic, all stamped with the frozen hash); index in `experiments/registry.csv`.
- Figures (from artifacts only): `artifacts/figures/{g0_reproduction,g1g2_surrogate_gamma,g3_stages,g4_identifiability}.png`.
- Freeze manifest: `artifacts/freeze_manifest_v1.json`.
