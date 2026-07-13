# SwitchSync Markets

**Scientific question.** *Can the temporal redistribution of a fixed, sparse set of transmission channels produce or anticipate cross-market synchronization beyond what is explained by instantaneous density, average connectivity, common factors and volatility?*

This is a new, independent research project. It is **not** a continuation of any prior trading project. Its aim is to test — rigorously and without a foregone conclusion — whether the link-switching synchronization mechanism of Eser, Medeiros, Riza & Engel (*"Dynamic link switching induces stable synchronized states in sparse networks"*, arXiv:2507.08007v2) admits a mathematically faithful and **empirically identifiable** translation to financial temporal networks.

> **No real market data is used anywhere in this repository.** All results are synthetic. Synthetic results MUST NOT be interpreted as evidence about real markets, predictability, or trading value. The empirical phase is unauthorized until the gates below justify it and a new authorization is given.

## Inspiring paper

Eser, Medeiros, Riza, Engel, arXiv:2507.08007v2 (nlin.AO, 2026). Local copy and SHA-256 in `docs/research/sources/`. Full mathematical audit in `docs/research/engel_paper_audit.md`.

## Three separated questions

- **A. Mechanism** — does switching synchronize a system whose dynamics and true links we know? (P1.1, G0)
- **B. Robustness** — does it survive heterogeneity, noise, directed/signed links, common shocks, partial observation? (P1.2–P1.3, G1–G3)
- **C. Identifiability** — could the mechanism be distinguished from observed series and estimated links alone? (P1.4, G4)

A positive answer to A does not imply B or C.

## Gates

| Gate | Question | If NO |
|---|---|---|
| **G0** Reproduction | Does the implementation reproduce the fast-switching mechanism within frozen tolerances? | STOP — FAILURE TO REPRODUCE |
| **G1** Causal isolation | Does fast switching contract more when density, strength, occupancy AND the average graph are controlled? | MECHANISM NOT ISOLATED |
| **G2** Temporal order | Does the order-sensitive propagator beat snapshot/average metrics? | Record that evidence favors aggregate connectivity |
| **G3** Robustness | Does the effect persist under predefined heterogeneity/noise/shocks? | Record the limited domain of validity |
| **G4** Identifiability | Can the mechanism be recovered from observations without the true links? | Do NOT advance to real data |

Current gate outcomes are in `STATUS.md`.

## Repository structure

```
docs/research/       paper audit, literature review, novelty matrix, source ledger, PDF source
docs/methodology/    financial-translation audit, temporal-stability metrics, synthetic prereg, empirical proposal
src/dynamics/        FitzHugh-Nagumo double-layer field + Jacobian
src/networks/        ring Laplacian, switching schedules + controls, temporal-graph metrics
src/metrics/         sync error, order-sensitive propagator (gamma), Lyapunov, baselines (incl. demoted G_switch)
src/simulation/      RK4 double-layer integrator, linear financial surrogate
src/validation/      dimension/finiteness guards, config hashing, freeze manifests
experiments/         frozen config, deterministic runners, atomic JSON reports, registry.csv
tests/               deterministic tests incl. deliberate leakage/order/corruption guards
artifacts/           freeze manifest, figures (generated only from saved reports)
```

## Reproducible commands

```bash
python3 -m pytest -q                         # test suite (deterministic)
cd experiments
python3 run_freeze.py                         # contract hash + freeze manifest + verify
python3 run_reproduction.py                   # G0: chaos + fast-vs-slow switching (FHN)
python3 run_causal_fhn.py                     # G1: FHN controls at fixed density/coupling
python3 run_surrogate_causal.py               # G1/G2: exact gamma decomposition (surrogate)
python3 run_surrogate_stages.py               # G3: heterogeneity/directed/signed robustness
python3 run_identifiability.py                # G4: recover switching from observations
python3 run_msf.py                            # minimal-system transverse Lyapunov (MSF)
python3 make_figures.py                       # figures from saved artifacts only
```

**Environment.** Exact freeze interpreter: **Python 3.14.3** (`python-version.txt`); dependencies pinned exactly in `requirements.lock.txt`. CI runs the **3.14** minor line — a patch-level difference is a *compatible* version, not the exact freeze interpreter; only 3.14.3 with the pinned packages reproduces the freeze hashes bit-for-bit. Determinism: explicit seeds everywhere; no module runs experiments on import; results are never overwritten.

**CI / license status.** A GitHub Actions workflow (`.github/workflows/ci.yml`) installs `requirements.lock.txt` and runs the test suite. Its remote result is **not yet verified** (no push has occurred), so no "CI passing" claim is made here. The repository has **no license yet** — see `docs/LICENSE_BLOCKER.md`; choosing one is a pending owner decision and none has been invented.

## v1 audit and v2 contract

P1 v1 was independently audited (`docs/audits/p1_v1_independent_audit.md`): 13 defects, with v1 results re-classified (G0 → calibrated demonstration; G1/G2 → superseded pending paired rerun; G3-signed and H3 → invalid; G4 → FAIL on precision/recall only, its `contraction_corr` invalid; MSF → invalid; freeze v1 → non-executable). Original v1 reports are preserved byte-for-byte with `*.superseded.json` sidecars. The corrected, executable contract is `docs/methodology/synthetic_prereg_v2.md` (+ `.json`), **not yet executed**. A separate, unexecuted branch (`docs/methodology/intermediate_rate_temporal_advantage_prereg_v1.md`), motivated by Zhang–Strogatz (2021), tests whether an intermediate-rate temporal advantage over the best admissible static network exists.

## Interpretation discipline (enforced throughout)

*synchronization ≠ correlation ≠ common-factor domination ≠ contagion ≠ convergence ≠ price discovery ≠ statistical dependence.* A link is not "causal" because it precedes another or has a nonzero VAR coefficient. An empirical slope is not a Lyapunov exponent without a defined dynamical system and variational equation. Synthetic synchronization is not evidence of market predictability.

## Current state

See `STATUS.md` for gate outcomes and the GO/NO-GO recommendation. Summary: the mechanism reproduces (G0), is robust in the weak sense (G3), but **does not beat aggregate connectivity** (G1 strict / G2) and is **only weakly identifiable** (G4) — consistent with fast-switching averaging theory and the financial confound literature.
