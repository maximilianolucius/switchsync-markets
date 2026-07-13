# Synthetic Pre-Registration v1 (P0.5 + P1 contract)

**Frozen contract file:** `experiments/configs/synthetic_prereg_v1.json`
**Contract SHA-256:** `abbd95154d3fba0c417d7bdbd70752e225a01e4e2d14d33291cab039ec883e82`
**Freeze manifest (code + config + env):** `artifacts/freeze_manifest_v1.json` (verified — see `run_freeze.py`).
**Scope:** synthetic only. NO real market data is used anywhere in this contract. This document is registered *before* interpreting results as evidence; acceptance/failure criteria were fixed in the config and are not moved after seeing results.

This pre-registration governs the P1 synthetic experiments and the gates G0–G4. It states the hypotheses as falsifiable claims with estimands, units, controls, baselines, metrics, and explicit accept/fail/inconclusive criteria.

---

## 1. Systems under test

1. **FHN double-layer** (faithful reproduction, P1.1): two identical rings of `N` FitzHugh–Nagumo oscillators, rotational intra-layer coupling `σ(L⊗H)`, sparse switched inter-layer activator coupling on mirror pairs at density `0.25`. Parameters frozen in `fhn`/`reproduction` sections. `σ_12 = 1.5` (documented departure from the paper's `0.1`; the reproduction target is *qualitative*, Gate G0).
2. **Linear basis surrogate** (P1.2–P1.4): two venues carrying the same assets; the transverse coordinate is the per-asset basis `d_j = p_{1,j}−p_{2,j}`; the common factor cancels in the basis; uncoupled basis dynamics are mildly expanding (`ρ≈1.04`), stabilized only by switched arbitrage channels. Parameters in `surrogate_*`/`identifiability` sections.

## 2. Metrics (defined in `docs/methodology/temporal_stability_metrics.md`)

- **`E^{12}`** — inter-layer synchronization error (FHN); tail-mean below `sync_threshold_E12=0.02` ⇒ synchronized.
- **`γ`** — order-sensitive transverse-contraction rate `−(1/Hδt)·log σ̄(P_⊥Φ P_⊥)` (or `σ̄(Φ)` for the already-transverse basis system). Primary mechanism metric.
- **`Λ_⊥`** — transverse Lyapunov exponent via the full variational equation (FHN MSF, minimal system).
- **`λ_max`** — Benettin largest Lyapunov exponent of the isolated layer (chaos check).
- Mandatory baselines: no-coupling, static-sparse, average-graph, density, node-sweep, temporal reachability, `G_switch` (descriptor only), shuffled-order null, shuffled-dwell null.

## 3. Definitions of outcome

- **Reproduce (G0):** chaos confirmed (`λ_max>0` at all tested sizes) AND fast switching (`T_swt≤10`) synchronizes in a majority of seeds AND slow switching (`T_swt≥160`) does not, with a finite, size-dependent maximum switching time.
- **Fail (G0):** fast switching does not synchronize, or slow synchronizes as readily as fast.
- **Inconclusive:** mixed seeds without a clear fast/slow separation; recorded as INCONCLUSIVE, not forced to a verdict.

---

## 4. Hypotheses (falsifiable)

### H1 — Rate effect (primary)
*At fixed instantaneous edge density, coupling strength and time-averaged topology, faster redistribution of sparse links increases transverse contraction relative to static, slow-switching and order-randomized controls.*
- **Estimand:** difference in transverse-contraction rate `γ_fast − γ_static` and `γ_fast − γ_slow` (surrogate); tail-mean `E^{12}_fast` vs `E^{12}_static/slow` (FHN).
- **Unit of observation:** one (schedule, seed) realization at fixed `N, N_IL, coupling`.
- **Controls:** identical `N_IL` (density), identical coupling strength, identical time-average where applicable, same seeds/ICs.
- **Baseline:** static-sparse graph of equal instantaneous density; slow switching.
- **Metric:** `γ` (surrogate), `E^{12}` (FHN).
- **Accept:** `γ_fast − γ_static > 3·pooled_std` AND `γ_fast − γ_slow > 3·pooled_std`.
- **Fail:** `γ_fast ≤ γ_static`.
- **Inconclusive:** difference positive but within the 3·std band.

### H2 — Temporal order vs aggregate connectivity
*Order-sensitive temporal propagators explain synchronization better than snapshot density, node sweep, or algebraic connectivity of the average graph.*
- **Estimand:** `γ_ordered − γ_shuffled_order` at intermediate rate; and sign of `γ_fast − γ_average_graph`.
- **Controls:** shuffled-order and shuffled-dwell nulls that preserve the snapshot multiset and occupancy.
- **Baseline:** average-graph `γ` and `λ_2(avg)`.
- **Accept:** order effect exceeds the seed-noise band AND `γ_fast > γ_average_graph`.
- **Fail / record as AGG_CONNECTIVITY:** order effect within the band OR `γ_fast ≤ γ_average_graph` (evidence favors aggregate connectivity, not dynamic switching). *This is an explicitly allowed, non-pejorative outcome per the brief.*

### H3 — Reachability mediation
*Temporal reachability mediates the effect of switching; endpoint coverage without temporal paths is insufficient.*
- **Estimand:** `γ_fast_full_coverage − γ_repeated_subset` (coverage) and `γ_fast − γ_high_sweep_low_reach` (reachability).
- **Accept:** both differences `> 3·pooled_std` (removing coverage/reachability kills the effect while rate is held fast).
- **Fail:** high node-sweep with broken reachability contracts as well as full-reachability fast switching.

### H4 — Robustness envelope
*The mechanism weakens or disappears as node heterogeneity, signed interactions, observation noise and common shocks increase.*
- **Estimand:** `γ_fast − γ_static` (advantage) across staged surrogates.
- **Accept (as a bounding statement):** advantage `>0` through the faithful and mild-heterogeneity stages; record the first stage at which it vanishes.
- **Note:** this hypothesis predicts *degradation*; confirming degradation is a positive result for H4.

### H5 — Identifiability
*A network-estimation procedure can recover enough of the true switching structure to distinguish genuine switching from estimator-induced edge turnover.*
- **Estimand:** precision & recall of estimated active links vs ground truth (past-only estimator); Pearson correlation of estimated vs true transverse contraction.
- **Controls:** common-factor-only confound (level-correlation estimator), asynchronous-observation variant, obs noise.
- **Baseline:** base-rate precision `= N_IL/N = 0.25`.
- **Accept:** precision AND recall `> 0.6` in the synchronous case AND contraction-correlation `> 0.5`, with the factor-confounded estimator staying below the basis estimator.
- **Fail:** precision or recall `≤ 0.5`, or the effect requires future data / collapses under asynchrony.

---

## 5. Baselines that any switching claim must beat (hard rule)

Per the brief: a switching metric is **not** accepted as evidence of the mechanism unless it beats (i) the average-graph metric, (ii) density, and (iii) nulls preserving occupancy and dwell time. The reports record the sign of every such comparison; the honest verdict follows the comparisons, not a desired conclusion.

## 6. Reproducibility procedure (executed in this order)

1. Freeze config (this file's hash) — done.
2. `run_freeze.py` → freeze manifest of `src/` + config + environment; verify.
3. Commit + tag `switchsync-fhn-prereg-v1`.
4. Run experiments (`run_reproduction`, `run_causal_fhn`, `run_surrogate_causal`, `run_surrogate_stages`, `run_identifiability`, `run_msf`) → atomic JSON in `experiments/reports/`, rows in `registry.csv`.
5. Generate figures **only** from saved artifacts.
6. Evaluate gates; commit + tag `switchsync-synthetic-results-v1`.

Any deviation is logged, with reason, in `DECISIONS.md` (append-only).
