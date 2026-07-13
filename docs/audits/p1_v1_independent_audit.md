# Independent Corrective Audit of P1 v1

**Audited artifacts:** commit `e2fff2aaccb36f74112439df62fffdba2e7fbbd6` (tag `switchsync-synthetic-results-v1`); contract `891da4f…` (tag `switchsync-fhn-prereg-v1`).
**Audit stance:** adversarial. The goal is to find and classify defects, not to rescue positive results. A correction may confirm, weaken, or invalidate any v1 result.
**Method:** every defect below was verified against the v1 code and/or by direct recomputation; the verifying command/line is cited. Original v1 reports are preserved byte-for-byte; supersession is recorded in `*.superseded.json` sidecars, never by editing v1 JSON.

---

## Summary disposition table

| Item | v1 result / component | Disposition |
|---|---|---|
| G0 | FHN reproduction (σ_12=1.5, N=40) | **DOWNGRADED_TO_CALIBRATED_DEMONSTRATION** |
| G1 / G2 | surrogate causal decomposition | **SUPERSEDED_PENDING_PAIRED_RERUN** |
| G3 (signed) | signed-coupling robustness stage | **INVALID** |
| H3 | coverage vs reachability isolation | **INVALID** |
| G4 | identifiability | **FAIL_SUPPORTED_BY_PRECISION_RECALL_ONLY**; `contraction_corr` **INVALID** |
| MSF | minimal-system transverse Lyapunov | **INVALID** |
| freeze v1 | `freeze_manifest_v1.json` + tooling | **NONEXECUTABLE_AS_SCIENTIFIC_FREEZE** |

G3 stages other than `signed` (heterogeneity, directed) and the G0 chaos check are **not** invalidated by this audit; they are re-scoped under v2, not discarded.

---

## Defects, with code evidence

### D1 — Freeze v1 is incomplete (19 files; excludes runners, `_common.py`, tests, evaluators)
`src/validation/freeze.py:freeze_manifest` hashes only the roots passed by `run_freeze.py`, which are `["src", "experiments/configs"]`. Recomputation:
```
n_files: 19
includes any runner (run_*.py)? False
includes _common.py?          False
includes tests/?              False
```
The evaluation logic that decides PASS/FAIL lives in the runners and `_common.py`, and the tests that certify behaviour live in `tests/` — **none are covered by the freeze**. A "scientific freeze" that omits the code producing the verdicts cannot certify the verdicts.

### D2 — `run_freeze.py` overwrites the manifest; `verify_manifest` cannot detect added files and derives no manifest content hash
`experiments/run_freeze.py` writes with a plain `json.dump` (no refuse-overwrite, no atomic guard). `src/validation/freeze.py:verify_manifest` iterates only over `manifest["files"]` (recorded set), so an executable added *after* the freeze is invisible. Recomputation (added `src/evil.py` after freeze):
```
added-file detected?  {'ok': True, 'mismatches': [], 'missing': [], 'n_checked': 1}
manifest has a top-level content hash field?  False
```
There is no single content hash of the whole manifest, so the freeze cannot be referenced by one immutable identifier, and tampering by *addition* passes verification.

### D3 — Two different "contract hashes" exist and are conflated
The contract is identified by a **canonical** hash (sorted-key, minified JSON) but the file on disk has a **different raw-bytes** SHA-256. Recomputation:
```
canonical config_hash : abbd95154d3fba0c417d7bdbd70752e225a01e4e2d14d33291cab039ec883e82
raw-bytes SHA-256     : 6d19cf5aa3408c8c18e93fa835fecf8464654943e0fbe4e957007f03e28d5941
```
v1 reports and docs cite only the canonical hash. A reader who hashes the file bytes gets a different value; provenance is ambiguous. v2 must record **both** (canonical config hash AND file SHA) in every report.

### D4 — G1-strict artifact contradicts the recorded verdict
`experiments/reports/surrogate_causal_g1_g2.json` records `evaluation.G1.beats_average_graph = False` and `fast_minus_average = -0.1419` (fast *loses* to the average graph), yet the report `verdict` and `registry.csv` both record **PASS**. The runner's `evaluate()` defines G1 PASS as beating static-sparse + slow only, silently dropping the brief's hard rule that switching must beat the average graph. The registry therefore reports a PASS that the artifact's own numbers refute.

### D5 — Rate arms are not paired and do not share the horizon
`run_surrogate_causal.py` builds each arm with `random_switching(..., H//dwell + 1, rng(k))`: distinct RNG draws per arm and `n_epochs = H//dwell + 1` with no final-epoch trim. Recomputation of total steps:
```
fast         dwell=2  epochs=121 total=242   (target 240)
intermediate dwell=12 epochs=21  total=252   (target 240)
slow         dwell=60 epochs=5   total=300   (target 240)
```
Fast/intermediate/slow run on horizons 242/252/300, on **different underlying snapshot sequences**. The γ contrast therefore confounds rate with horizon length and with the specific random draw — it is not a controlled rate experiment.

### D6 — `shuffled_dwell` is a no-op
`random_switching` assigns the same `dwell_steps` to every epoch, so the dwell multiset is a singleton. `shuffle_dwell` permutes identical values. Recomputation:
```
distinct dwell values in base: {2}
epochs identical after shuffle_dwell: True
```
The shuffled-dwell null is byte-identical to the base schedule and tests nothing.

### D7 — MSF two channels are the same phase
`run_msf.smooth_square_gamma` sets `gamma_0 = g(t)` and `gamma_1 = g(t + p_period)` with `p_period = 2*T_swt`. Since `g` has period `p_period`, `g(t+p_period) = g(t)`, so the two channels are identical, not complementary. Recomputation:
```
max|gamma_0 - gamma_1| over a run: 0.0
```
The minimal system is therefore driven with **both** mirror links in the same phase (or effectively one doubled link), not the alternating single link the paper's construction requires. The MSF result cannot represent switching.

### D8 — Signed stress produces no negative weights
`linear_surrogate.build_basis_operator` (signed branch) computes `diffusion * (0.5 + 0.5*signs)` with `signs ∈ {−1,+1}`, giving multipliers in `{0, 1}` — never negative. Recomputation:
```
min off-diagonal entry: 0.0
any strictly negative off-diagonal? False
```
The "signed" stage only zeroes some couplings; it never introduces a negative (antagonistic) coupling. The G3 signed claim is unsupported.

### D9 — H3 controls change more than one variable
`repeated_subset` (fast, links confined to a fixed set of size `N_IL`) changes **coverage** but simultaneously changes the reachable node set; `high_sweep_low_reachability` confines links to a node block, changing **reachability** but also the identity of covered nodes and the effective average operator. Neither is a clean single-variable contrast, and `temporal_reachability_ratio` (defined in `src/networks/temporal_metrics.py`) is **never actually reported** in the G1/G2 artifact. Calling these "isolation" of coverage vs reachability is unjustified.

### D10 — `contraction_corr` correlates against a different latent trajectory
`run_identifiability._contraction_corr` (lines 82–84) calls `simulate_basis(params, sched, np.random.default_rng(999), noise=0.0)` — a **fresh, independent** basis realization — and correlates it against the observed `p1−p2`. The observed data came from `simulate_observed` with entirely different RNG draws. The "true-vs-observed contraction correlation" therefore compares two unrelated realizations and is meaningless.

### D11 — LOCF asynchrony ≠ demonstration of the Epps effect
`linear_surrogate._hold_except_every` implements last-observation-carried-forward staleness. This produces an Epps-*like* degradation but does not isolate the Epps mechanism (non-synchronous sampling of a continuous covariance). v1 language should be "asynchrony/LOCF degradation," not "the Epps effect is the cause."

### D12 — G0 coupling was chosen exploratorily
`fhn.note_sigma_inter` and `DECISIONS.md:D6` record that `σ_12 = 1.5` was found empirically (the paper uses `0.1` at N=400). This makes G0 a **calibrated qualitative demonstration**, not a reproduction of the paper's regime. It must be labelled as such and must not, by itself, support any claim about the N-dependence of the switching threshold (that claim requires a switching grid across several N, which was not run).

### D13 — The 20 v1 tests detect none of D1–D12
The suite asserts invariances of helper functions and guard behaviours but contains no test that: pairs rate arms and asserts equal horizon (D5); asserts a non-constant dwell distribution (D6); asserts MSF channel anti-phase (D7); requires a strictly negative signed weight (D8); ties contraction correlation to the same realization (D10); detects an added executable in the freeze (D1/D2). Passing tests gave false assurance.

---

## Rationale for each disposition

- **G0 → DOWNGRADED_TO_CALIBRATED_DEMONSTRATION** (D12): the mechanism is shown at a hand-tuned coupling and one small N; valid as a demonstration, not as paper reproduction.
- **G1/G2 → SUPERSEDED_PENDING_PAIRED_RERUN** (D4, D5): the contrast is confounded (unpaired, unequal horizon) and the recorded PASS contradicts the artifact. The *direction* (fast beats static-sparse; average graph beats fast) is plausible but must be re-established with paired schedules before any verdict stands.
- **G3 signed → INVALID** (D8): the stress was never actually signed.
- **H3 → INVALID** (D9): controls confound coverage and reachability; the mediating metric is unreported.
- **G4 → FAIL_SUPPORTED_BY_PRECISION_RECALL_ONLY; contraction_corr INVALID** (D10, D11): the FAIL verdict rests on precision/recall (valid, past-only estimator), which is fine; the contraction-correlation evidence is invalid (wrong trajectory) and the asynchrony claim is over-stated.
- **MSF → INVALID** (D7): driven with identical-phase channels; cannot represent switching.
- **freeze v1 → NONEXECUTABLE_AS_SCIENTIFIC_FREEZE** (D1, D2, D3): omits the code that produces verdicts, cannot detect added files, has no single content hash, and conflates two hashes.

## What is NOT claimed here
- No v1 commit or tag is rewritten, moved, or deleted.
- The chaos check (λ_max>0) and the heterogeneity/directed G3 stages are not invalidated by this audit; they are re-scoped under v2.
- This audit does not assert the *corrected* experiments will reproduce or overturn any v1 direction — that is deferred to the (unexecuted) v2 run.
