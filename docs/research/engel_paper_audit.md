# Mathematical Audit — Eser, Medeiros, Riza & Engel (arXiv:2507.08007v2)

**Paper:** M. C. Eser, E. S. Medeiros, M. Riza, M. Engel, *"Dynamic link switching induces stable synchronized states in sparse networks"*, arXiv:2507.08007v2, dated 25 February 2026, category nlin.AO.
**Local copy:** `docs/research/sources/eser2025_arxiv_2507.08007v2.pdf`
**SHA-256:** `0774a03c9c5f84fa1c6bb6c70a1a13345b23e3e3ecf5cb37a4b882b085e442e6`
**Audit status:** Read in full (10 pages: main text, all figures, references). This document records *what the paper actually proves*, separating numerical evidence from analytical results from extrapolation. It is deliberately conservative.

---

## 0. One-paragraph summary (in the paper's own scope)

The authors study a **two-layer network of FitzHugh–Nagumo (FHN) oscillators**. Each layer is an identical ring of `N` FHN nodes with nearest-neighbour diffusive coupling; the two layers are sparsely connected by `N_IL = 0.25 N` **inter-layer links that join mirror nodes** (same ring position in both layers). The set of active inter-layer links is **randomly reassigned every `T_swt` time units** ("switching time"). The claim, supported numerically and — for a minimal `N=2`-per-layer system — by a Master Stability Function (MSF) analysis, is that **shorter `T_swt` (faster switching) induces stable inter-layer synchronization**, i.e. the two layers converge to a common trajectory `L_1(t)=L_2(t)`, even though each isolated layer is chaotic (largest Lyapunov exponent `λ_max ≈ 0.04 > 0`). Slow switching fails to synchronize.

This is **inter-layer synchronization between two identical copies of the same system, coupled only through the activator variable of mirror nodes**. It is *not* a statement about heterogeneous nodes, directed links, signed links, or statistical causality.

---

## 1. Local dynamics — FitzHugh–Nagumo

Each node `(i, j)` (layer `i ∈ {1,2}`, ring position `j ∈ {1,…,N}`) carries an activator `u_{ij}` and inhibitor `v_{ij}`. The local vector field (Eq. 2) is

```
du_{ij}/dt = (1/ε) ( u_{ij} − u_{ij}³/3 − v_{ij} )
dv_{ij}/dt = u_{ij} + a_{ij}
```

- **ε = 0.05** — timescale separation (fast activator, slow inhibitor). Fixed for all experiments.
- **a_{ij}** — excitability threshold. `|a|>1` ⇒ excitable (fixed point); `|a|<1` ⇒ oscillatory (limit cycle). **All oscillators are in the oscillatory regime** (`|a|<1`).
- **Intra-layer heterogeneity (two populations):** `a` alternates by ring index. Body text (p.2): odd `j` → `a=0.87`, even `j` → `a=0.97`. Fig. 2 caption: `a_odd=0.87, a_even=0.97` (consistent). Fig. 1 caption swaps odd/even — a **minor internal inconsistency** in the paper; the substantive point is two interleaved populations `{0.87, 0.97}`. **The two layers are identical**: mirror nodes have the same `a`.

**Audit note (chaos):** A *single* FHN oscillator (2-D autonomous) cannot be chaotic. The chaos reported (`λ_max≈0.04`) is a property of the **coupled ring layer** (`2N`-dimensional, with the rotational cross-coupling `H` and heterogeneity), verified in Fig. 2 by the Benettin method for `N=200`. The chaos is emergent from the network + rotational coupling, not from the node.

---

## 2. Intra-layer coupling

Diffusive nearest-neighbour coupling on a ring (radius `r=1`), zero-row-sum Laplacian `L` (Eq. 3), circulant: `−2` on the diagonal, `+1` on the two nearest neighbours (with wrap-around corners). Intra-layer coupling strength `σ_1 = σ_2 = 0.1` (fixed).

The coupling is **rotational**, through the matrix (applied in the 2-D `(u,v)` node space):

```
H = [ cos φ,  sin φ ;  −sin φ,  cos φ ],   φ = π/2 − 0.1
```

`H` mixes activator and inhibitor in the coupling term (cross-influence `u↔v`). The near-`π/2` phase is what **desynchronizes the nodes within a layer** and generates the chaotic layer dynamics. The intra-layer coupling term in Eq. (1) is `σ_i (L ⊗ H) L_i`.

**Audit note:** This rotational coupling is essential and non-standard. It is *not* plain diffusive `u`-coupling; the `⊗H` is what makes the isolated layer chaotic and desynchronized. Any reproduction must implement `L ⊗ H`, not `L` alone.

---

## 3. Inter-layer coupling and the switching mechanism

Inter-layer term in Eq. (1): `σ_12 (L^I ⊗ Γ(t)) (L_1; L_2)`.

- **Inter-layer Laplacian** `L^I = [ −1, 1 ; 1, −1 ]` — couples the two layers diffusively (layer 1 ↔ layer 2). This is a **2×2** Laplacian over the *layer* index, eigenvalues `λ_1=0` (synchronization/tangent direction) and `λ_2=−2` (transverse direction).
- **Γ(t)** is a `2N×2N` diagonal matrix acting on node/state index. Its non-zero entries sit on the **activator diagonal** of each node: `γ_j(t)` multiplies the `u`-component of node `j`. Thus **inter-layer coupling acts only through the activator `u` of mirror nodes** — the inhibitor `v` is not directly coupled across layers.
- **`γ_j(t) ∈ {0,1}`**: `1` if an inter-layer link is active on mirror pair `j` at time `t`, else `0`. At each switching event (every `T_swt`) the set `{j : γ_j=1}` is **randomly reassigned**, keeping the count fixed at `N_IL = 0.25 N`.

**Density is fixed** at `N_IL/N = 0.25` throughout, and `N_IL ≪ N(N−1)/2`, so inter-layer connectivity is genuinely sparse.

**Switching time `T_swt`:** the fixed dwell interval during which a given link set stays active before the random reassignment. This is the central control parameter. Note (p.5): because reassignment is *random*, a given mirror pair may be re-selected consecutively, and a given pair may go many intervals without a link — so the on/off intervals per individual link vary in length even though the global switching cadence is periodic.

**Contrast with prior work [19]:** Ref. [19] introduced rewiring implicitly via a rewiring *frequency*; here the wiring is an explicit time-dependent function, so `T_swt` is a real, controllable dwell time.

---

## 4. Synchronization error

- **Global inter-layer error (Eq. 4):** `E^{12}(t) = (1/N) ‖L_1(t) − L_2(t)‖`. Euclidean distance between the two full layer state-vectors, normalized by `N`. `E^{12}→0` ⇒ inter-layer synchronization.
- **Single-pair error (Fig. 3):** `E_35 = sqrt( (u_{1,35} − u_{2,35})² + (v_{1,35} − v_{2,35})² )`, the distance between mirror node 35 in the two layers.
- **Time-averaged error (Eq. 9):** `E^{12} = (1/T) ∫_t^{t+T} E(t') dt'`, with `t=1000`, `T=10000` (used for the phase diagrams in Fig. 9).

---

## 5. What is shown NUMERICALLY (direct simulation)

| Result | Figure | Parameters | Finding |
|---|---|---|---|
| Isolated layer is chaotic | Fig. 2 | `N=200`, `σ_12=0` | `λ_max≈0.04>0` (Benettin). Confirms synchrony is switching-induced, not from periodic dynamics. |
| Slow vs fast switching | Fig. 3 | `N=400`, `N_IL=100`, `σ_12=0.1` | `T_swt=120` ⇒ `E^{12}` stays bounded away from 0 (no sync). `T_swt=23` ⇒ `E^{12}→0` after a transient (sync). |
| Transient time vs size | Fig. 4 | `N_IL/N=0.25`, several `T_swt∈{5,10,15,23,25,35,50}` | Time-to-sync `T_sync` increases monotonically with `N`; smaller `T_swt` syncs faster. |
| Max switching time vs size | Fig. 5 | `N_IL/N=0.25` | Maximum `T_swt` that still synchronizes decreases with `N` (≈90 at `N≈30` down to ≈50 at `N=300`). |
| Sync-error phase diagram | Fig. 9a | `N=2` (minimal), 100 realizations | `E^{12}(σ_12,T_swt)`: dark (low-error/sync) region grows as `T_swt` decreases; threshold behaviour. |

**Audit note:** The large-`N` results (Figs. 3–5) are **direct numerical integration only** — there is *no* analytical stability proof at large `N`. The relationship "faster switching ⇒ easier synchronization ⇒ synchronizes at lower `σ_12`" is an empirical/numerical claim for these specific parameters.

---

## 6. What is shown by STABILITY ANALYSIS (MSF)

The MSF analysis is performed **only on the minimal system: `N=2` FHN oscillators per layer.** Construction:

1. Treat each layer (2 nodes) as one higher-dimensional system with local field `G(L_i) := F(L_i) + σ_i (L⊗H) L_i` (Eq. 5).
2. Synchronization manifold `S: L_1 = L_2`.
3. Variational equation (Eq. 6): `δL̇_i = [DG(S) + σ_12 (L^I ⊗ Γ(t))] δL_i`, with `DG(S)` the Jacobian of the intra-layer dynamics **evaluated on the synchronized trajectory** — this is the full variational equation, *not* the Laplacian alone.
4. Diagonalize `L^I` (eigenvalues `0, −2`) ⇒ block-decoupled Eq. (7): `δΘ̇_i = [DG(S) − σ_12 λ_i Γ(t)] δΘ_i`. The `λ_1=0` block is tangent (ignored); the transverse block uses `λ_2=−2`, giving Eq. (8): `δΘ̇ = [DG(S) − 2σ_12 Γ(t)] δΘ`.
5. **MSF `Ψ` = largest Lyapunov exponent of Eq. (8)**, as a function of `(σ_12, T_swt)`. `Ψ<0` ⇒ transverse contraction ⇒ stable synchronization.

**Handling the switching discontinuity:** Piecewise-constant `Γ(t)` makes the variational flow discontinuous, threatening well-definedness of `Ψ`. They replace the on/off indicator by a **smooth square wave** `g(t,α,p) = tanh(α(t−np)) − tanh(α(t−(n+0.5)p)) − 1`, with sharpness `α=5` (results converge for `α≥5`), period `p = 2·T_swt`, and `n=⌊t/p⌋`. The two mirror pairs are driven in opposite phases (`f` and `g`), so exactly one link is active at a time — this is the minimal analogue of switching.

**MSF findings:**
- **Static single link (Fig. 6):** `Ψ(σ_12)` positive for "only node 1" and "only node 2" (unstable); negative (around `σ_12≈0.15`) only for "both nodes" connected. ⇒ **A single static inter-layer link cannot synchronize the pair; you need links equal in number to the oscillators per layer** (static case).
- **Switching (Fig. 8):** `Ψ(σ_12,T_swt)` — `T_swt=135` stays positive (no sync); smaller `T_swt` crosses zero at smaller `σ_12`. Below `T_swt≈40`, reducing `T_swt` further does *not* lower the sync threshold below `σ_12≈0.33`.
- **Agreement (Fig. 9):** MSF-negative region (9b) aligns with the low-error region of direct simulation (9a); minor discrepancies attributed to finite-size and integration error.

**Audit note (scope of MSF):** The classical MSF assumes a *fixed* Laplacian diagonalizable independently of the trajectory. Here `Γ(t)` is time-dependent, so the "MSF" is really the **largest Lyapunov exponent of a time-dependent (switched, then smoothed) linear variational system along the synchronized chaotic trajectory** — a Floquet/Lyapunov-type transverse-stability exponent, computed only for `N=2`. It is a legitimate transverse-stability calculation, but it is **not** the standard `σ`-parametrized MSF curve, and it is **not** proven to control the large-`N` system. See §8.

---

## 7. The extrapolation from minimal to large system

The paper is explicit (Conclusions) that the MSF is done on the minimal system and then argued to *justify* the large-`N` results:

> "synchronization is governed by local transverse modes associated with individual inter-layer connections, rather than by global collective coupling. Fast switching effectively generates a time-averaged stabilizing interaction, and each active inter-layer link locally enforces transverse contraction in the same manner as in the minimal system."

**This is a heuristic/physical argument, not a theorem.** The claimed mechanism — "each active link locally enforces the same transverse contraction as in the minimal system, and fast switching time-averages these into a net stabilizing interaction" — is exactly a **fast-switching / averaging** intuition (cf. blinking-network theory). The paper does **not** state or invoke an averaging theorem with error bounds, nor prove that the `N=2` transverse exponent bounds the large-`N` transverse spectrum. This is the single most important gap to keep in mind for our translation (see `temporal_stability_metrics.md`).

---

## 8. Limitations acknowledged by the authors (and audited)

Authors' own caveats:
- Effectiveness "may depend on specific features of the underlying chaotic dynamics" — different chaotic attractors have different tangent-space contraction/expansion, so the quantitative result is attractor-specific.
- MSF only on the minimal system; large-`N` transverse stability is argued, not derived.
- Intra-layer heterogeneity limited to **two** populations; stronger heterogeneity or **random intra-layer topology** "would pose additional difficulties" and is left to future work.
- Spontaneous intra-layer synchronization is deliberately suppressed (that is *why* two populations are used); if it occurred it would reduce effective dimensionality.

Additional caveats surfaced by this audit (not stated as limitations by the authors but true of their setup):
- **Layers are identical.** All results depend on `layer 1` and `layer 2` sharing parameters and structure. There is no analysis of non-identical layers.
- **Coupling is undirected and unsigned.** `L^I` and `L` are symmetric Laplacians with non-negative off-diagonal weights. No directed or negative coupling anywhere.
- **Mirror-only inter-layer links.** Inter-layer links connect *only* corresponding positions; there is no cross-position (`j≠k`) inter-layer coupling. The "network" of inter-layer links is a **matching on mirror pairs**, not an arbitrary bipartite graph.
- **Randomness of reassignment** means "coverage" (how many distinct pairs ever receive a link) and "temporal order" are stochastic; the paper does not isolate order effects from rate/coverage effects — it varies `T_swt` (rate) only. Our causal experiments (P1.2) must add the order/coverage controls the paper lacks.
- **Chaos is verified once** (Fig. 2, `N=200`) and asserted to persist; strictly it is not re-verified at every `(N, φ, a)` combination used elsewhere.

---

## 9. Frozen parameter set (for reproduction, P1.1)

| Symbol | Value | Meaning | Source |
|---|---|---|---|
| `ε` | 0.05 | FHN timescale separation | Eq. (2), all figs |
| `a_odd` | 0.87 | threshold, odd ring index | p.2 / Fig. 2 caption |
| `a_even` | 0.97 | threshold, even ring index | p.2 / Fig. 2 caption |
| `φ` | π/2 − 0.1 | rotational coupling phase | p.3 |
| `σ_1=σ_2` | 0.1 | intra-layer coupling | p.3 |
| `r` | 1 | intra-layer coupling radius (nearest neighbour) | Fig. 2 caption |
| `N_IL/N` | 0.25 | fixed inter-layer density | p.2 |
| `σ_12` | variable (e.g. 0.1) | inter-layer coupling | Figs. 3–9 |
| `T_swt` | variable | switching time | central parameter |
| IC range | `u,v ∈ [−2, 2]` uniform | initial conditions | p.3 |
| `α` | 5 | smooth-square-wave sharpness (MSF only) | p.6 |
| `p` | 2·T_swt | smooth-wave period (MSF only) | p.7 |
| Benettin | periodic tangent renormalization | λ_max method | Fig. 2 / Ref. [39] |

Representative figure settings: Fig. 3 uses `N=400, N_IL=100, σ_12=0.1, T_swt∈{23,120}`; Fig. 2 uses `N=200`; MSF/Fig. 6–9 use `N=2` per layer.

---

## 10. Statements the audit forbids (guardrails for downstream docs)

Per project discipline, the following must **not** be asserted on the basis of this paper:
- That the paper concerns financial networks, arbitrary directed links, or statistical causality. **It does not.**
- That the `N=2` MSF *proves* large-`N` stability. It **motivates** it.
- That "synchronization" here means correlation, contagion, or price discovery. It means `L_1(t)=L_2(t)` (identical-trajectory transverse contraction).
- That `G_switch = λ_2(avg Laplacian) − avg λ_2(instantaneous Laplacian)` captures the mechanism. The paper's mechanism is a **transverse Lyapunov exponent along a chaotic trajectory under a time-dependent coupling operator**, not an algebraic-connectivity gap. (See `temporal_stability_metrics.md`.)

---

*End of P0.1 audit.*
