# DECISIONS (append-only)

Scientific decisions, contract choices, and their reasons. Newest entries appended at the bottom. Do not edit past entries.

---

## 2026-07-13 — Project initialized (P0–P1)

- **D1. New independent project.** SwitchSync Markets is created fresh; it is not a continuation of any prior trading work. No prior data or code is imported.
- **D2. Paper fixed and hashed.** arXiv:2507.08007v2 downloaded to `docs/research/sources/`, SHA-256 `0774a03c9c5f84fa1c6bb6c70a1a13345b23e3e3ecf5cb37a4b882b085e442e6`. Audit reads v2 in full.
- **D3. `G_switch` demoted.** The connectivity gap `λ2(avg) − mean λ2(snapshot)` is retained only as an "aggregation connectivity gap" descriptor. Reason: proven invariant under time-dilation (rate-blind) and under reordering (order-blind); therefore cannot be the dynamic switching mechanism. Primary metrics are the order-sensitive propagator `γ` (linear) and the transverse Lyapunov exponent `Λ_⊥` (nonlinear), both defined from the full variational dynamics including the local Jacobian.
- **D4. Two translations separated.** Faithful multilayer (T1: same asset, two venues, basis = transverse coordinate, sync manifold ≈ cointegration) is the primary target. Broad generalization (T2: different assets, directed/signed links) is treated as new theory, used only as a synthetic stress test, never presented as "the paper applied to markets".
- **D5. Directed/signed operators.** For directed/signed surrogates the symmetric-Laplacian `λ_2` is forbidden; the ordered product of the actual (possibly non-normal) per-step maps and its largest singular value are used instead.

## 2026-07-13 — Reproduction parameter departure (documented, not result-hacking)

- **D6. `σ_12 = 1.5` for the FHN reproduction (paper uses 0.1 at N=400).** Reason discovered empirically: inter-layer coupling acts only on the activator, and full static coupling of two identical chaotic layers at our tractable size (N=40) synchronizes only for `σ ≳ 0.5`; with 25%-density switching the fast-limit effective coupling is ≈0.25×, so the sync threshold sits near `σ_12 ≈ 1.0–1.5`. Gate G0 is defined as a *qualitative* reproduction (fast syncs, slow does not, finite max switching time), not a match of the absolute threshold. Documented in the audit and the prereg. The mechanism (fast-vs-slow separation, threshold, monotonic `T_swt` dependence) reproduces cleanly.
- **D7. Benettin tangent co-integration.** First implementation used a frozen-Jacobian explicit-Euler tangent and produced a spurious negative `λ_max`. Fixed to co-integrate state and tangent with RK4, evaluating the Jacobian at each substage. Verified `λ_max > 0` at N∈{40,100,200} (≈0.006–0.017), consistent with the paper's ~0.04. This was a bug fix, not a tuning choice.

## 2026-07-13 — Identifiability estimator (fair-attempt fix, criteria unchanged)

- **D8. Estimator changed from rolling basis-variance to rolling AR(1) coefficient; window reduced 24→8 to match the dwell.** Reason: a window much longer than the dwell straddles multiple on/off cycles and washes out the signal; the AR(1) self-coefficient of the venue-difference basis cleanly separates active (mean-reverting, coef≈A_jj−2κ<0) from inactive (expanding, coef≈1.04). This makes the estimator a *fair* attempt rather than a strawman. **Acceptance criteria (P/R>0.6, corr>0.5) were NOT changed.** The estimator still fails the bar (P/R≈0.35), and that FAIL is reported honestly.

## 2026-07-13 — Minimal-system MSF limitation (recorded, not forced)

- **D9. Minimal-system MSF does not reproduce the slow-switching instability.** The N=2-per-layer isolated layer is a limit cycle (`λ_max ≈ -0.001`, verified), so its transverse mode does not expand during off-phases and any switched coupling contracts (`Ψ<0` for all tested `σ,T_swt`). The switching-TIME dependence of the stability boundary is therefore NOT reproduced in the minimal build; it IS reproduced by the large-N direct simulation (G0). MSF verdict recorded as PARTIAL with this explanation rather than overclaimed as PASS.

## 2026-07-13 — Honest gate reading

- **D10. G1 strict bar and G2 favor aggregate connectivity.** The average (time-averaged) graph contracts more than fast switching in the surrogate (`γ_avg > γ_fast`), and temporal order adds nothing beyond the seed-noise band. Per the brief this is an allowed, non-pejorative outcome: evidence favors aggregate connectivity over dynamic switching. The defensible positive content is that fast switching lets a *sparse* system emulate the *dense average*, beating the equal-density static-sparse graph. Recorded rather than reframed as success.
