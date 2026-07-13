# Intermediate-Rate Temporal-Advantage Branch — Pre-Registration v1 (NOT EXECUTED)

**Status:** separate scientific branch. **NOT part of the v1 rescue** and **NOT executed.** Requires explicit authorization to run. Synthetic only.
**Motivation:** Zhang & Strogatz, *Nature Communications* 12, 3273 (2021), DOI 10.1038/s41467-021-23446-9, arXiv:2101.02721 — temporal networks can synchronize under an edge/resource budget where **no static network can**, with the advantage appearing at **intermediate** switching rates and governed by **MSF curvature**.

## Why a separate branch

The main v2 contract (G1_strict) compares switching against the average graph and the best admissible static, with a strong prior — from fast-switching averaging theory — that the **fast** arm does not beat the average. That prior does **not** cover intermediate rates. Zhang–Strogatz show precisely there that a genuine temporal advantage can exist. This branch tests that hypothesis directly and must not be conflated with, or used to reinterpret, the v1/v2 fast-vs-slow results.

## Central hypothesis (falsifiable)

**HI1.** There exists an edge budget `B` and an intermediate switching rate at which a temporal schedule achieves transverse contraction (γ) strictly greater than the **best static network admissible under the same budget** `B`, by a margin exceeding the seed-noise band — and the fast and slow limits do **not** achieve this.

## Definitions to freeze before any run

- **Admissible static budget `B`.** The resource constraint. Two variants to pre-register: (a) fixed instantaneous edge count `N_IL` (sparsity budget); (b) fixed total edge-time (sum of weights × time). The average graph is the budget-`B` static that spends the budget as uniform fractional weights.
- **Best admissible static.** `argmax` over static networks respecting `B` of the transverse contraction rate γ, via (i) enumeration of the base snapshots, (ii) a bounded random search of `K_search` static sets, and (iii) a greedy edge-swap local optimum. Report which static wins and its γ.
- **Average graph.** Per-pair weight = budget-normalized occupancy (the fast-switching limit).
- **Intermediate speeds.** A rate sweep via `paired_switching` cycles (e.g. dwell ∈ {40,20,10,8,5,4,2} at H=240, K=6), all sharing the identical average operator, so only rate varies. The advantage, if any, is a non-monotone function of rate.
- **MSF curvature.** For the linear surrogate, the transverse operator is `A − 2κ·diag(γ_t)`; the curvature of the contraction rate as a function of the instantaneous coupling determines whether time-averaging over the switched operator gains or loses relative to a static operator (Jensen-type effect). Pre-register the estimand: the second derivative of the per-step contraction w.r.t. the coupling level, evaluated along the synchronized state, and its sign as the predictor of a temporal advantage.

## Estimands and criteria (frozen)

- **Estimand:** `max_rate γ(rate) − γ(best_admissible_static)`, paired per seed, over the intermediate-rate sweep.
- **PASS (temporal advantage exists):** the max over intermediate rates exceeds the best admissible static by > 3·pooled_std AND a paired test p<0.05, AND neither the fast nor the slow limit achieves it.
- **FAIL / NO_ADVANTAGE:** no rate beats the best admissible static beyond the band.
- **TIE / INCONCLUSIVE:** advantage within the band.
- **MSF-curvature check:** report whether the sign of the pre-registered curvature estimand predicts the presence/absence of the advantage (a mechanistic corroboration, not a gate).

## Guardrails

- This branch does **not** touch real data, PnL, or any financial claim.
- A PASS here is a statement about the **synthetic surrogate under a budget**, not about markets, and not a reinterpretation of v1.
- The comparator is the **best admissible static**, never a strawman static.

## Execution

**DO NOT RUN** without explicit authorization. When authorized, it would use the same `paired_switching` machinery and a new runner `experiments/run_intermediate_rate_branch.py` (to be written), producing atomic reports with the full hash/commit provenance required by the v2 reporting rules.
