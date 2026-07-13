# Financial Translation Audit (P0.2)

**Purpose.** Decide, honestly, whether and how the Eser–Medeiros–Riza–Engel switching-synchronization mechanism (see `../research/engel_paper_audit.md`) can be mapped onto financial systems. Two candidate translations are examined. For each: object correspondence, required assumptions, unobservable assumptions, endogeneity, common shocks, heterogeneity, signed links, asynchrony, estimation error, existence of a synchronization manifold, and the economic meaning (if any) of "synchronization".

**Bottom line up front.** Translation **T1 (faithful multilayer: same asset, two venues)** is the only one where the paper's mathematical objects have a defensible financial counterpart, and even there several of the paper's load-bearing assumptions (identical layers, undirected/unsigned diffusive coupling, a genuine invariant synchronization manifold, known true links) are **violated or unobservable** in markets. Translation **T2 (broad: different assets, directed/signed links)** is *not* an application of this paper — it requires new theory, because the paper provides neither a stability result nor even a well-posed synchronization manifold for non-identical, directed, or signed systems. We proceed with T1 as the primary target and treat T2 as an explicitly-flagged generalization to be built and justified from scratch, never presented as "the paper applied to markets".

---

## 1. Translation T1 — Faithful multilayer (same asset, two representations)

### 1.1 Object correspondence

| Paper object | T1 financial counterpart |
|---|---|
| Layer 1 / Layer 2 | Two **venues / representations of the same asset universe**: e.g. spot vs perpetual-future, or two exchanges, or cash vs futures. |
| Node `j` in a layer | One **asset** in that venue (e.g. BTC on venue A). |
| Mirror pair `(1,j)–(2,j)` | The **same underlying asset** in the two venues (BTC-spot ↔ BTC-perp). |
| Intra-layer ring + rotational `H` | Cross-asset dynamics *within* a venue (co-movement structure among assets on that venue). **No natural ring or rotational coupling exists in markets** — see §1.3. |
| Inter-layer link on mirror pair `j` | An active **price-discovery / arbitrage channel** transmitting information between the two representations of asset `j`. |
| `γ_j(t)∈{0,1}` switching | Whether that arbitrage/price-discovery channel is "active" (binding) at time `t`. |
| `σ_12` | Strength of cross-venue transmission (arbitrage intensity). |
| Sync manifold `L_1=L_2` | The **law of one price**: the two representations carry the same (de-trended) state. |
| Inter-layer sync error `E^{12}` | Residual **basis / dislocation** between venues after removing common movement. |

### 1.2 Required assumptions (that could plausibly hold)

- The two venues track the **same** underlying value process (true for spot vs perp of the same coin; approximately true across exchanges).
- Transmission is **bidirectional and mean-reverting toward parity** — i.e. genuinely diffusive/error-correcting (arbitrage pushes the basis toward zero). This is the financial analogue of `L^I = [[−1,1],[1,−1]]`.
- Channels are **intermittent**: arbitrage capital, liquidity and attention rotate across assets, so at any instant only a subset of mirror pairs is being actively arbitraged. This is the analogue of sparse, switching inter-layer links.

### 1.3 Unobservable / violated assumptions (the honest problems)

1. **Identical layers — VIOLATED.** The paper's entire stability argument requires `layer 1` and `layer 2` to be dynamically identical so that a synchronization manifold `L_1=L_2` is *invariant*. Spot and perpetual are **not** identical: perps carry a funding-rate mechanism, different microstructure, different participants, leverage, and liquidation dynamics. There is no exact invariant manifold; at best an approximate, drifting one (a **basis** that is stationary but not identically zero). **Consequence:** we can study *contraction of the basis*, not exact synchronization.
2. **The intra-layer ring + rotational coupling has no market counterpart.** In the paper the ring/`H` structure is what makes each layer chaotic and desynchronized *by construction*. In markets the within-venue cross-asset structure is (a) not a ring, (b) not known, (c) dominated by common factors, and (d) not obviously chaotic in any verified sense. **We must not import the ring; the intra-layer generator must be replaced by an estimated or posited market dynamic, and that changes the transverse spectrum.** This is a structural, not cosmetic, departure.
3. **True links are unobservable.** The paper *knows* `γ_j(t)`. In markets the "active arbitrage channel" indicator is latent and must be **estimated from data** — the whole of P1.4 (identifiability) exists because of this.
4. **A genuine dynamical system + variational equation is unavailable.** The paper's transverse Lyapunov exponent requires a known vector field `G` and its Jacobian `DG(S)`. Markets give us **observed time series**, not a trusted generator. Any "Lyapunov exponent" computed from data is a *statistic*, not the paper's object, and must not be called a Lyapunov exponent without a defined system (project discipline rule).

### 1.4 Endogeneity, common shocks, heterogeneity, signed links, asynchrony, estimation error

- **Endogeneity:** Spot and perp prices are jointly determined; "who leads" is endogenous and time-varying. A lead–lag coefficient ≠ a causal transmission link. The paper has no endogeneity because it *defines* the coupling; we cannot.
- **Common shocks:** The dominant driver of cross-venue and cross-asset co-movement is **common information / market-wide factors** (macro, BTC beta). This produces synchronization-*looking* behaviour **without any switching mechanism**. This is the single biggest confound and mandates a `common-factor-only` baseline (see baselines) and factor removal before any link estimation.
- **Heterogeneity:** Assets differ in volatility, liquidity, tick size. The paper's two-population heterogeneity is mild and symmetric; market heterogeneity is large and asymmetric — squarely in the regime the authors say "would pose additional difficulties".
- **Signed links:** Some cross-asset relationships are negative (hedges, substitutes). A symmetric non-negative Laplacian cannot represent these; `λ_2` of a symmetric Laplacian is then **not the right operator** (see `temporal_stability_metrics.md` §on directed/signed).
- **Asynchrony:** Venues trade on different clocks; non-synchronous sampling induces the **Epps effect** (spurious de-correlation at high frequency) and can *manufacture* apparent "link turnover" that has nothing to do with a real switching mechanism.
- **Estimation error:** Rolling-window / thresholded network estimation produces **edge turnover as an artifact of noise**, which mimics switching. Distinguishing real switching from estimator churn is exactly Gate G4.

### 1.5 Conditions for a synchronization manifold to exist (T1)

For the paper's framework to even be *well-posed* in T1 we would need: (i) two systems sharing an invariant (or slowly-drifting) manifold on which the de-trended states coincide; (ii) transverse directions with a well-defined contraction rate; (iii) a coupling operator that is error-correcting toward that manifold. In practice (i) holds only approximately (cointegration / stationary basis), (ii) requires a posited generator, (iii) requires arbitrage to be genuinely mean-reverting. **The most defensible reading is a cointegration / error-correction picture**: the "synchronization manifold" ≈ the cointegrating relation (law of one price), and "transverse contraction" ≈ the speed of error-correction of the basis. We adopt this reading explicitly.

### 1.6 Economic meaning of "synchronization" under T1

Convergence of the **basis** (spot−perp dislocation, or cross-exchange spread) toward its stationary attractor — i.e. **integration / efficient arbitrage**. It is *not* a claim about predictability or profit. A period of strong transverse contraction means dislocations decay fast (well-arbitraged, integrated market); weak contraction means dislocations persist (fragmented / stressed market). Whether *switching of channels* (as opposed to their density or strength) drives this is the empirical question — and the null is that density/factors explain it.

---

## 2. Translation T2 — Broad financial generalization

### 2.1 Object correspondence (attempted)

| Paper object | T2 counterpart |
|---|---|
| Node | A **distinct asset** (different underlyings). |
| Inter-node link | A **directed, possibly signed** influence (lead–lag, spillover, VAR edge). |
| Switching | Time-variation of the influence network. |
| "Synchronization" | Co-movement / contraction between **heterogeneous** states. |

### 2.2 Why T2 is not an application of this paper

- **No mirror pairs, no identical layers.** Different assets do not share a trajectory; there is **no synchronization manifold `x_i=x_j`** to contract onto. "Synchronization of heterogeneous nodes" is a *different* concept (generalized/cluster synchronization, or mere correlation), for which this paper offers no result.
- **Directed/signed coupling breaks the paper's spectral machinery.** The MSF reduction (Eqs. 6–8) relies on diagonalizing a **symmetric** Laplacian with real non-negative structure and a clean tangent/transverse split. Directed and signed operators are generally non-normal, may have complex spectra, and do not admit the same tangent/transverse decomposition. Using `λ_2` of a symmetrized Laplacian here is **unjustified** and is explicitly forbidden by the project brief.
- **What "contraction" even means changes.** For heterogeneous, directed systems the relevant object is contraction of a **VAR/state-space operator** (spectral radius / joint spectral radius of a product of time-varying matrices), possibly after common-factor removal — not a transverse Lyapunov exponent onto an identical-copy manifold.

### 2.3 Verdict on T2

T2 is a **legitimate research direction but a new theory**, not a corollary of Eser et al. If pursued, it must define its own operator (directed/signed, non-symmetric), its own notion of "synchronization or contraction between heterogeneous states", and its own stability object. In this project T2 is used **only** in the synthetic financial surrogate (P1.3) as a *stress test* of the mechanism under directed/signed links, and every such result is labelled "generalization beyond the source paper", never "the paper's mechanism in markets".

---

## 3. Decision and consequences for the project

1. **Primary target = T1** (same asset, two venues, basis contraction / error-correction reading of the synchronization manifold).
2. The **intra-layer ring + rotational `H`** is a paper-specific device; in the financial surrogate it is replaced by a linear/state-space market generator with a common factor (P1.3). This is a *departure* and is documented as such — it means our surrogate tests *the switching idea*, not the paper's exact system.
3. **Common factors are the primary confound.** Factor removal precedes any link estimation; a `common-factor-only` process is a mandatory baseline that any switching metric must beat.
4. **No object may be renamed across the semantic boundary.** synchronization ≠ correlation ≠ common-factor domination ≠ contagion ≠ price discovery ≠ statistical dependence (project discipline). Each is used only in its precise sense.
5. **Directed/signed operators** get their own definition (`temporal_stability_metrics.md`); `λ_2` of a symmetric Laplacian is used only where the operator is genuinely symmetric and non-negative.
6. Any T1 result is, at most, evidence about **market integration / arbitrage-channel dynamics** in synthetic data — never evidence of predictability or trading value (forbidden by authorization scope until real-data gates pass).

*End of P0.2 audit.*
