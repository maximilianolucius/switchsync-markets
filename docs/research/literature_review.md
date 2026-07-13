# Literature Review (P0.4)

Scope: primary literature bearing on (a) synchronization in switching/temporal networks and (b) its possible translation to financial networks. All 52 references are logged with DOI/URL in `source_ledger.csv`; each DOI was verified to resolve to the stated title/authors via the Crossref REST API (the two seed papers via their AIP/SIAM landing pages). Provenance note: the initial search+verification pass was executed by an automated sub-agent; six of its first-pass DOIs were wrong and were corrected before inclusion (see the note at the end). Nothing here is a placeholder.

Discipline reminder (applies throughout): *synchronization*, *correlation*, *common-factor domination*, *contagion*, *convergence*, *price discovery*, and *statistical dependence* are distinct and are not used interchangeably.

---

## Cluster 1 — Master stability function (MSF) foundations

Pecora & Carroll's conditional-Lyapunov criterion (1990) and the MSF factorization (1998) are the backbone: the transverse stability of a synchronous state reduces to a scalar function evaluated at Laplacian eigenvalues. Barahona & Pecora (2002) tie synchronizability to the eigenratio `λ_N/λ_2`; Huang et al. (2009) classify the generic MSF shapes; Arenas et al. (2008) review the topology→synchronizability map. **Relevance:** this is exactly the machinery the seed paper invokes, and it is what our transverse-contraction metrics generalize to *time-varying* coupling. **Limit:** the classical MSF assumes a fixed, trajectory-independent Laplacian; the seed paper (and we) must instead compute a transverse Lyapunov exponent of a *time-dependent* variational system, which is not the standard `σ`-parametrized MSF curve.

## Cluster 2 — Fast-switching / blinking-network theory (the load-bearing cluster)

Belykh–Belykh–Hasler (2004) introduced the "blinking" model and showed that **fast on/off links synchronize a network as if it were coupled by its time-averaged topology**. Stilwell–Bollt–Roberson (2006) proved the sufficient condition: *if the time-averaged network synchronizes, sufficiently fast switching does too*, even when no instantaneous snapshot does. Hasler–Belykh–Belykh (2013) bound the finite-time deviation from the averaged system. Porfiri et al. (2006) and Frasca et al. (2008) extend this to proximity/mobility-driven time-varying links. **Relevance:** this cluster is the theoretical explanation of the seed paper's central result and of our own G1/G2 finding. It predicts precisely what we observe in the surrogate: fast switching **approaches** the average graph from below and never exceeds it. **This directly frames our strict G1 bar** — "switching must beat the average graph to count as a distinct mechanism" — as one that averaging theory says should *fail* in the fast limit. That is not a defect of the experiment; it is the theory being confirmed.

## Cluster 3 — Consensus over jointly-connected / switching graphs

Jadbabaie–Lin–Morse (2003), Olfati-Saber–Murray (2004), Moreau (2005), Ren–Beard (2005), and the Olfati-Saber–Fax–Murray survey (2007) establish that linear consensus is achieved when the *union* of switching interaction graphs is **jointly connected** frequently enough — not connected at every instant. **Relevance:** this is the discrete/linear counterpart of switching-induced synchronization and grounds our `joint_connectivity` and `temporal_reachability` controls. **Limit:** these are linear-consensus results with no chaotic node dynamics and no estimation error; our G3/G4 add both.

## Cluster 4 — Synchronization in temporal / time-varying networks (seeds + review)

Schröder et al. (2015, "transient uncoupling") show *less* coupling can *help* synchronization. Boccaletti et al. (2006) give the exact commuting-graph case that switching approximates. Kohar et al. (2014) and Zhou et al. (2019) provide the empirical basis that rapid/random temporal links enhance synchronizability. Jardón-Kojakhmetov–Kuehn–Longo (2024) give rigorous persistence conditions for time-dependent *linear diffusive* coupling — the math backbone for our linear surrogate. The seed paper's own predecessor, Eser–Medeiros–Riza–Zakharova (2021), established the two-layer FHN switching setup; Ghosh et al. (2022) is the definitive review. **Relevance:** this is the immediate home of the seed paper. **Our additions:** independent reproduction, an explicit causal decomposition (occupancy/order/coverage/reachability controls the seed lacks), and the financial identifiability question none of these address.

## Cluster 5 — Temporal-network foundations

Holme & Saramäki (2012), Holme (2015), Pan & Saramäki (2011), Holme (2005) define temporal networks, **time-respecting paths**, and reachability, and show time-ordering sharply limits who can influence whom. **Relevance:** the formal language for our order-sensitive reachability metric and for the proof (in `temporal_stability_metrics.md`) that node-sweep coverage ≠ temporal reachability. **Limit:** this literature studies spreading/reachability, not transverse contraction; connecting the two is our contribution.

## Cluster 6 — Financial connectedness / networks

Diebold–Yılmaz (2009, 2012, 2014) turn VAR forecast-error variance decompositions into directed weighted networks; Billio et al. (2012) show financial networks densify before crises; Barigozzi–Hallin (2017) build idiosyncratic networks after common-factor removal. **Relevance:** these are the candidate *financial* networks our switching structure would sit inside, and Billio et al. supplies the crucial empirical fact that these networks are time-varying. **Discipline flag:** a nonzero variance-decomposition or Granger edge is a *statistical dependence*, not a causal transmission channel; we never conflate the two.

## Cluster 7 — Factor-adjusted / large-VAR network estimation

Barigozzi–Brownlees (2019, NETS), Fan–Liao–Mincheva (2013, POET), Basu–Michailidis (2015), Kock–Callot (2015) provide estimators and error bounds for high-dimensional VAR/partial-correlation networks after separating a low-rank factor part from a sparse residual. **Relevance:** these are the tools an empirical stage would use to *estimate* the switching network, and their error bounds are exactly the "estimator-induced edge turnover" our Gate G4 must distinguish from genuine switching. **Limit:** they assume stability and a sparse-plus-low-rank structure; our basis system is intentionally near-unstable between switches.

## Cluster 8 — Spot–futures price discovery

Hasbrouck (1995, information shares; 2003), Gonzalo–Granger (1995, permanent–transitory), Baillie et al. (2002, reconciliation). **Relevance:** these define the *economic* meaning of inter-venue coupling in Translation T1 (same asset, two venues) and support reading the "synchronization manifold" as a cointegrating/law-of-one-price relation. **Discipline flag:** price discovery ≠ synchronization; a venue can "lead" price discovery without the basis contracting.

## Cluster 9 — Crypto spot–perpetual lead–lag

Alexander et al. (2020), Baur–Dimpfl (2019), Alexander–Heck (2020), Entrop et al. (2020) document that spot/perp leadership exists, differs by venue/regulation, and **varies over time**. **Relevance:** the time-variation of leadership is the concrete phenomenon our switching translation would target, and perpetual funding provides an economic mechanism. **Limit:** all empirical; our P1 is synthetic-only, and these papers measure price-discovery shares, not transverse contraction.

## Cluster 10 — Asynchronous / non-synchronous trading

Epps (1979), Hayashi–Yoshida (2005), Scholes–Williams (1977), Barndorff-Nielsen et al. (2011). **Relevance:** the **Epps effect** (cross-correlations vanish as sampling shrinks under asynchrony) is a first-order confound for any high-frequency synchronization estimate and directly motivates our asynchronous-observation control; our G4 reproduces the Epps-like collapse of identifiability. **Limit:** these give consistent covariance estimators; we show even correct estimators cannot separate switching once the system has synchronized.

## Cluster 11 — Dynamic correlation & diversification breakdown

Engle (2002, DCC), Longin–Solnik (2001), Ang–Chen (2002), Forbes–Rigobon (2002). **Relevance:** correlations are time-varying and rise (asymmetrically) in crises — the "onset" one might hope to anticipate. **Crucial caution (Forbes–Rigobon):** after correcting for heteroskedasticity, apparent crisis *contagion* is largely *stable interdependence* — i.e. rising measured correlation is often a volatility artifact, not new coupling. This is the sharpest warning against interpreting any measured co-movement increase as switching-induced synchronization.

---

## Synthesis: where the seed paper sits and what is genuinely open

The mechanism (fast switching of sparse links → synchronization, approaching the time-averaged graph) is **well-established theory** (Clusters 2–3), with the seed paper contributing a specific two-layer FHN instantiation and a minimal-system MSF. The financial side (Clusters 6–11) has rich, separate literatures on connectedness, price discovery, and time-varying correlation — **but none connects the switching-synchronization mechanism to a financial temporal network, and none asks whether the *temporal redistribution* of channels (as opposed to their density or a common factor) is identifiable from observed series.** That gap is the project's target, quantified in `novelty_matrix.md`.

Two conclusions from the review shape our expectations honestly:
1. **Averaging theory predicts switching will not beat the average graph.** Any positive claim must therefore be about switching letting a *sparse, capacity-constrained* system emulate a denser average — not about switching adding contraction beyond aggregate connectivity.
2. **The financial-side literature is dominated by confound warnings** (Epps; Forbes–Rigobon; factor domination). These make the identifiability question (G4/C) the true crux — and a likely failure point — of any financial translation.

---

### Provenance / correction log
The automated verification pass corrected six wrong first-pass DOIs before inclusion (Epps 1979, Hayashi–Yoshida 2005, Gonzalo–Granger 1995, Baur–Dimpfl 2019, Alexander–Heck 2020, Baillie et al. 2002) and confirmed all others via Crossref. Volume-year vs online-year discrepancies (Diebold–Yılmaz EJ 2009, Barigozzi–Hallin JRSS-C 2017, Alexander et al. JFM 2020) were resolved to the citeable volume year. The seed arXiv:2507.08007 is the only non-peer-reviewed entry.
