# Empirical Stage Proposal (PROPOSAL ONLY — NOT AUTHORIZED TO EXECUTE)

**Status:** This document *proposes* an empirical design for a future phase. Per the P0–P1 authorization, no real data may be downloaded, opened, or processed; no backtests, PnL, Sharpe, drawdown, or trading costs; no operational Synchronization Hazard Index. This proposal is contingent on an explicit new authorization AND on the GO/NO-GO reading below.

## 1. What the synthetic phase concluded (inputs to this decision)

- The switching-synchronization *mechanism* reproduces (G0) but, per fast-switching/averaging theory and our own surrogate, **does not beat the time-averaged graph** (G1 strict bar fails; N2 refuted) and **temporal order adds nothing beyond aggregate connectivity at the tested rates** (G2 → AGG_CONNECTIVITY; N3 refuted).
- **Identifiability is the binding constraint** (G4 FAIL): switching is only weakly recoverable from observations (P/R≈0.35 vs 0.25 base rate), collapses under asynchrony, and is confounded to chance by a common factor unless venues are differenced.

These are strong priors that a real-data study of "switching beyond aggregate connectivity" would most likely return a **null or bounding** result. An empirical stage is therefore worthwhile only if framed as a **falsification / bounding** exercise, not a search for predictive value.

## 2. Proposed design (faithful Translation T1 only)

- **Objects:** one asset, two venues (e.g. spot vs perpetual on the same exchange, or two exchanges). Basis `d_j = p_{1,j} − p_{2,j}` is the transverse coordinate; the common factor cancels by venue-differencing.
- **Estimand:** does the *temporal redistribution* of active price-discovery/arbitrage channels carry transverse-contraction information beyond (i) instantaneous density, (ii) the average graph, (iii) a common-factor-only model, and (iv) DCC-style time-varying correlation?
- **Data (future, on authorization):** documented public sources only; strict event-time handling; Hayashi–Yoshida / realised-kernel covariance for asynchrony; explicit tick-provenance ledger.
- **Estimators:** venue-difference basis AR/error-correction per asset (factor-free by construction); NETS / factor-adjusted VAR (Cluster 7) as the network estimator; compare estimated switching to estimator-induced turnover via placebo/permutation.
- **Mandatory controls & nulls:** common-factor-only surrogate; shuffled-order and shuffled-dwell nulls preserving occupancy/dwell; average-graph baseline; Forbes–Rigobon heteroskedasticity correction to guard against volatility-artifact "contagion".

## 3. Pre-registered success/failure (to be frozen before any data touch)

- **Positive (mechanism identifiable & beyond aggregate):** an order-sensitive contraction estimator explains out-of-sample basis contraction beyond density + average-graph + factor + DCC, with precision/recall of switching above a permutation null, and robust to the Epps asynchrony control.
- **Bounding/Null (expected):** it does not — record the bound and stop. This is a publishable negative result and the honest most-likely outcome.
- **Forbidden interpretations:** no claim of predictability, trading value, PnL, or an operational hazard index; no calling a VAR edge causal; no calling an empirical slope a Lyapunov exponent.

## 4. Interpretation discipline (carried from P0)

synchronization ≠ correlation ≠ common-factor domination ≠ contagion ≠ convergence ≠ price discovery ≠ statistical dependence. Every reported quantity is named in its precise sense, and every co-movement increase is tested against the volatility-artifact and factor-domination confounds before any structural reading.

## 5. Gate to enter this stage

Enter **only** if G0–G4 jointly justify it. Given G4 FAIL and G1/G2 favoring aggregate connectivity, the current reading is **NO-GO for a predictive empirical study** and at most **conditional-GO for a falsification/bounding study** (see `STATUS.md` for the formal recommendation). Either way, a new explicit authorization is required.
