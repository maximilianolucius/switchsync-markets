# Temporal Stability Metrics (P0.3)

**Purpose.** Replace the naive connectivity gap with order-sensitive, dynamically meaningful measures of switching-induced contraction, and state precisely what each measures. All claims here are mathematical, about the *idealized* systems; whether they hold empirically is deferred to P1.

Notation: `δt` integration step; `H` a horizon in steps; `L_t` the (instantaneous) coupling Laplacian at step `t`; `κ` coupling strength; `1` the all-ones vector; `P_∥ = 11ᵀ/n` the projector onto the synchronization direction; `P_⊥ = I − P_∥` the transverse projector; `‖·‖` the spectral norm (largest singular value) unless stated; `λ_2(·)` the algebraic connectivity (2nd-smallest Laplacian eigenvalue); `ρ(·)` spectral radius; `σ̄(·)` largest singular value.

---

## 1. Why the proposed `G_switch` is inadequate (but retained as a descriptor)

Proposed metric:
```
G_switch = λ_2( L̄ ) − mean_t λ_2( L_t ),   L̄ = mean_t L_t   ("aggregation connectivity gap")
```

We **keep** `G_switch` but only as an *aggregation connectivity gap* descriptor, never as the mechanism metric, because it has three disqualifying defects.

### 1.1 It can be large even when switching is arbitrarily slow (rate-blind)

`G_switch` is a function **only of the time-averaged Laplacian `L̄` and the multiset `{L_t}`**. It contains **no timescale**. Concretely, take any switching schedule and *dilate time*: hold each snapshot `M` times longer (`T_swt → M·T_swt`). The multiset of snapshots is unchanged (each appears `M×` more often but the set of distinct values and their average `L̄` are identical), so `λ_2(L̄)` and `mean_t λ_2(L_t)` are **unchanged**, hence `G_switch` is **unchanged**. But the paper's mechanism *dies* as `T_swt→∞` (slow switching does not synchronize, Figs. 3, 5, 8). Therefore a metric invariant under time-dilation **cannot** be the mechanism. ∎

*Formal statement.* For any schedule `{L_t}` and dilation factor `M∈ℕ`, `G_switch({L_t}) = G_switch(dilate_M{L_t})`, whereas the true transverse contraction rate (§5) is *not* dilation-invariant. Proof: dilation preserves `L̄` and the empirical distribution of snapshots, hence both terms of `G_switch`; the contraction operator `Φ` (§4) changes because each matrix exponential is taken over a longer `δt·M`. (Demonstrated numerically in `tests/test_metric_invariances.py`.)

### 1.2 It is order-insensitive

`G_switch` depends on `{L_t}` only through the average `L̄` and the per-snapshot connectivities. Two schedules with the **same multiset of snapshots in different temporal order** have identical `G_switch`. But temporal order changes reachability and the non-commuting product of propagators (§4). A metric blind to order cannot detect an order effect (H2/Gate G2). ∎

### 1.3 It is not the dynamic mechanism

`λ_2` of a static Laplacian is the contraction rate of the *continuous consensus flow on that fixed graph*. The paper's system is (i) time-varying, (ii) driven along a **chaotic trajectory** with a non-trivial local Jacobian `DG(S)`, and (iii) coupled only through the activator. `λ_2(L̄)` ignores all three. Averaging the Laplacian and then taking `λ_2` is **not** the same as the Lyapunov exponent of the time-averaged variational flow, except in special commuting/fast-switching limits — and even then the correct object is the exponent of the *averaged variational system including `DG`*, not `λ_2(L̄)` (§6).

**Retention rule.** `G_switch` may be reported as one descriptor among the mandatory baselines, labelled "aggregation connectivity gap". It is **never** used as an acceptance criterion for the mechanism.

---

## 2. Why node sweep is insufficient

"Node sweep" = the number/fraction of distinct nodes (or mirror pairs) that ever receive a link over a horizon. It measures **endpoint coverage**, not **temporal connectivity**.

Counterexample (formal): partition nodes into two blocks `A, B` with no temporal path ever crossing between them; switch links so that *within* each block every node is eventually touched. Node sweep = 100% (full coverage), yet information cannot propagate `A↔B`: the temporal reachability graph is disconnected, and the transverse mode spanning `A` vs `B` never contracts. Hence full node sweep is compatible with **zero** joint connectivity and **no** synchronization across the `A|B` cut. ∎

Coverage is *necessary-ish* but not sufficient; the sufficient object is a **temporal path** connecting the relevant cut (§3), which node sweep cannot see.

---

## 3. Temporal-graph primitives

Let the switching schedule over `[t_0, t_0+H)` be a sequence of graphs `G_{t_0}, …, G_{t_0+H−1}` (each a set of active mirror-pair links; here undirected unless stated).

- **Dwell time** `τ_e` of edge `e`: number of consecutive steps `e` stays active before a switch. Distribution `{τ_e}` characterizes the schedule; `T_swt` is the global switch cadence (for the paper, the interval after which the *set* is reassigned).
- **Edge occupancy** `occ(e) = (1/H) Σ_t 1[e active at t]` — fraction of the horizon edge `e` is on. Controls `L̄` (a time-averaged-topology quantity). **A key control (P1.2) preserves `{occ(e)}` while destroying order/rate.**
- **Switching rate** `= 1/T_swt` (switches per unit time). The paper's central knob.
- **Time-respecting (temporal) path** from `i` to `j`: a sequence `i=n_0, n_1, …, n_k=j` with active edges `(n_{m}, n_{m+1})` at non-decreasing times `t_0 ≤ s_0 ≤ s_1 ≤ … ≤ s_{k−1} < t_0+H`. Order matters: reversing the schedule can destroy a path.
- **Temporal reachability** `R(i→j; t_0, H) = 1` iff a time-respecting path exists. The **reachability ratio** `= (1/n²) Σ_{i,j} R(i→j)`.
- **Joint (integral) connectivity** over `[t_0, t_0+H)`: the union graph `∪_t G_t` is connected. This is the classical condition (Jadbabaie–Lin–Morse; Moreau) under which time-varying consensus converges. **Joint connectivity is weaker than requiring every snapshot connected and stronger than mere coverage.** For undirected schedules it coincides with reachability of the union; for directed schedules use *time-respecting* reachability, which is strictly finer (order-sensitive).

**Relationship to the paper.** The mirror-pair inter-layer links form a **matching that changes over time**; "synchronization across the layer" needs the *union over a horizon* of the inter-layer coupling, mediated through the intra-layer ring, to connect all transverse modes. Fast switching increases how many pairs are visited per unit time → faster growth of the union / reachability. This is the reachability-mediation hypothesis (H3).

---

## 4. Order-sensitive propagator (linear diffusive surrogate)

For a **linear** diffusive consensus/error-correction system `ẋ = −κ L_t x` integrated with step `δt`, the state map over horizon `H` is the **ordered (non-commuting) product**

```
Φ(t_0, H) = exp(−κ L_{t_0+H−1} δt) · exp(−κ L_{t_0+H−2} δt) · … · exp(−κ L_{t_0} δt).      (P1)
```

Because the `L_t` generally **do not commute**, `Φ` depends on the **order** of the schedule, not just the multiset — this is precisely what `G_switch` cannot see. `Φ` always fixes the synchronization direction (`Φ 1 = 1` since each `L_t 1 = 0`).

**Transverse contraction operator:**
```
Φ_⊥(t_0, H) = P_⊥ Φ(t_0, H) P_⊥.                                                       (P2)
```
**Finite-horizon transverse contraction factor and rate:**
```
c(t_0, H) = ‖Φ_⊥(t_0, H)‖ = σ̄(P_⊥ Φ P_⊥),                                              (P3)
γ(t_0, H) = −(1 / (H·δt)) · log c(t_0, H).                                              (P4)
```
`γ>0` ⇒ net transverse contraction over the horizon (states pulled together); larger `γ` ⇒ faster synchronization. **`γ` is order-sensitive, rate-sensitive, and reachability-sensitive**, and is the linear analogue of the paper's transverse Lyapunov exponent. This is the primary "switching contraction" metric for the linear surrogate.

Notes:
- Use the **spectral norm / largest singular value**, not `λ_2`, because over a finite horizon the transverse map is generally non-normal (product of non-commuting symmetric matrices is not symmetric); its *worst-case* contraction is `σ̄`, not an eigenvalue.
- Averaging `γ(t_0,H)` over start times `t_0` and seeds gives a schedule-level contraction rate. Comparing across controls that fix `{occ(e)}` and `L̄` but vary order/rate isolates the order/rate effect (Gate G1/G2).
- **Fast-switching limit (sanity anchor).** As `T_swt→0` with fixed occupancies, `Φ(t_0,H) → exp(−κ L̄ H δt)` (averaging/blinking-network theorem, Belykh–Belykh–Hasler; Stilwell–Bollt–Roberson), so `γ → λ_2(L̄)·κ`. Thus `λ_2(L̄)` is only the *fast-switching ceiling*; the gap between `γ` and this ceiling at finite `T_swt` is the genuinely dynamic content, which `G_switch` throws away.

---

## 5. Directed / signed operators (T2 stress tests)

When the surrogate has **directed** or **signed** coupling, `L_t` is not a symmetric non-negative Laplacian and the tangent/transverse split via `λ_2` is invalid.

- **Directed:** define the (generally non-symmetric) generator `A_t` and use the same ordered product `Φ = ∏ exp(A_t δt)`. Transverse contraction still measured by `σ̄(P_⊥ Φ P_⊥)` (worst-case), but the relevant consensus direction is the **left** eigenvector of the averaged generator; document which projector is used. Use time-respecting reachability (strictly order-sensitive) for the graph-level measure.
- **Signed:** a signed Laplacian may be indefinite; there may be **no** contraction onto `1` at all. Do not force `λ_2 ≥ 0` interpretation. Use the ordered product's `σ̄(P_⊥ Φ P_⊥)` and report when contraction fails to exist (a legitimate negative result). Structural balance (Altafini) determines whether bipartite consensus (agreement up to sign) is even possible.

**Rule (from brief):** never apply `λ_2` of a symmetrized Laplacian to a directed/signed system. Define the operator, justify the projector, use singular values of the ordered product.

---

## 6. Nonlinear (FHN) transverse stability — the full variational equation

For the paper's FHN system the contraction must be computed from the **full variational (linearized) dynamics along the synchronized chaotic trajectory `S(t)`**, *not* from the Laplacian in isolation.

Transverse variational equation (paper Eqs. 6–8, generalized to `N`):
```
δΘ̇ = [ DG(S(t)) − κ λ⊥ Γ(t) ] δΘ,                                                      (P5)
```
where:
- `DG(S(t))` = Jacobian of the **intra-layer** dynamics `G(L) = F(L) + σ (L⊗H) L` evaluated on the synchronized trajectory. `DF` for FHN at state `(u,v)` per node is `[[ (1−u²)/ε, −1/ε ], [ 1, 0 ]]`; the ring/rotational part adds `σ (L⊗H)`. **This term carries the chaotic expansion the coupling must overcome — it cannot be dropped.**
- `κ λ⊥ Γ(t)` = transverse projection of the inter-layer coupling; for the paper's minimal system `λ⊥ = 2` (eigenvalue of `L^I`), `κ = σ_12`, and `Γ(t)` selects the activator and switches in time.
- For large `N`, `λ⊥` is replaced by the spectrum of the transverse coupling operator; there is **no single scalar** and the paper's `N=2` reduction is a heuristic (see audit §7).

**Transverse Lyapunov / finite-time exponent:** integrate (P5) with periodic Benettin renormalization of `δΘ` restricted to the transverse subspace; the exponential growth rate is the **transverse Lyapunov exponent** `Λ_⊥`. `Λ_⊥ < 0` ⇒ stable synchronization. This is the object the paper calls the MSF `Ψ` (for `N=2`).

**Finite-time transverse stability** (for switching, where the coupling is non-autonomous): compute the finite-time exponent
```
Λ_⊥(t_0, H) = (1/(H δt)) log ‖ M_⊥(t_0, H) δΘ_0 ‖ / ‖δΘ_0‖,
```
where `M_⊥` is the transverse fundamental solution of (P5) over `[t_0, t_0+H)` (an ordered product of step propagators, exactly analogous to (P1) but with the state-dependent `DG(S(t))` included). Averaging over start times/seeds gives the schedule-level transverse stability. **Discipline: this is only called a "Lyapunov exponent" when (a) a dynamical system and (b) its variational equation are both explicitly defined — never for an empirical slope.**

---

## 7. Metric ledger (what each measures, what it cannot)

| Metric | Sensitive to rate? | Sensitive to order? | Sensitive to reachability? | Includes local Jacobian? | Role |
|---|---|---|---|---|---|
| graph density / mean edge strength | no | no | no | no | baseline (topology only) |
| node sweep (coverage) | weakly | no | no | no | baseline; **insufficient** (§2) |
| `λ_2(L_t)` instantaneous | no | no | no | no | baseline (snapshot) |
| `λ_2(L̄)` avg-graph | no | no | no | no | baseline; = fast-switch ceiling |
| `G_switch` (aggregation gap) | **no** | **no** | no | no | descriptor only; **not** mechanism (§1) |
| temporal reachability ratio | yes | yes | **yes** | no | mediator (H3) |
| joint connectivity | yes | (dir: yes) | yes | no | classical sufficient condition |
| **`γ(t_0,H)` = −log σ̄(P_⊥Φ P_⊥)/Hδt** | **yes** | **yes** | **yes** | linear only | **primary linear mechanism metric** |
| **`Λ_⊥(t_0,H)` transverse f.t. exponent** | **yes** | **yes** | **yes** | **yes** | **primary FHN mechanism metric** |
| shuffled-order / shuffled-dwell nulls | — | — | — | — | preserve occupancy, destroy order/rate → isolate mechanism |

**Acceptance principle (project brief).** No switching metric counts as evidence of the mechanism unless it **beats** (i) the average-graph metric, (ii) density, and (iii) nulls that preserve occupancy and dwell time. `γ` and `Λ_⊥` are the metrics allowed to make that claim; `G_switch` is not.

*End of P0.3.*
