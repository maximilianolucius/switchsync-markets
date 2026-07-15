# P1.2-F — Cheap-suite one-shot RESULT (SYNTHETIC; freeze v8)

**This is a RESULT package, not a pre-execution package.** All content is synthetic;
no real/market data was used; nothing was committed or pushed; the sealed bundle lives
OUTSIDE the repository.

## 1. Exact command

```
python3 experiments/run_suite_v2.py --cheap-only --i-am-authorized \
  --run-dir /media/maxim/MX00x/working_dir/tmp/switchsync_runs/p1_2f \
  --expect-prereg-canonical a667434d0d7c5905d62cf81b79699f2799e2597128631cab1e4792bed6053dd9 \
  --expect-prereg-file-sha 896163891b8b43f42511a1a57294d6075f3b65f33877780daf82cc03a54d568e \
  --expect-execution-contract-canonical 6dbe79ddf1d0b6e5e63f74a5ae3ed947abfc837419f4b7938fdcf8c09f525ee8 \
  --expect-execution-contract-file-sha 80609ef5a90817813f0a9978ec017ab00734c3681abb0429fbe4ec4582b8c2bb \
  --expect-freeze-content-hash 2991e064ced6154c149fa57d4fc77e855bede51750565c264972b369778d112d \
  --expect-freeze-commit 5ca40c7da87f583c7cea1cefd00cc978c3731d98 \
  --expect-freeze-tag switchsync-synthetic-execution-v8-freeze \
  --authorization-token <SWITCHSYNC-P1.2F-CHEAP-ONE-SHOT-…  (recorded ONLY as SHA-256)>
```

Run from the v8 freeze commit with a clean tree; external run-dir. Executed exactly
once.

## 2. Timing and exit

| | |
|---|---|
| started_utc (manifest) | `2026-07-14T19:46:42.275337+00:00` |
| ended_utc (manifest) | `2026-07-14T19:55:26.628915+00:00` |
| wall clock | ≈ 8 min 44 s |
| process exit code | **0** |
| terminal state | `COMPLETED` (bundle SEALED; no `.interrupted`/`.invalid`/`.failed`) |

## 3. Frozen v8 identity

| field | value |
|---|---|
| prereg v8 canonical | `a667434d0d7c5905d62cf81b79699f2799e2597128631cab1e4792bed6053dd9` |
| prereg v8 file SHA-256 | `896163891b8b43f42511a1a57294d6075f3b65f33877780daf82cc03a54d568e` |
| exec contract v6 canonical | `6dbe79ddf1d0b6e5e63f74a5ae3ed947abfc837419f4b7938fdcf8c09f525ee8` |
| exec contract v6 file SHA-256 | `80609ef5a90817813f0a9978ec017ab00734c3681abb0429fbe4ec4582b8c2bb` |
| freeze v8 content_hash | `2991e064ced6154c149fa57d4fc77e855bede51750565c264972b369778d112d` |
| source commit | `0bb2ab8a9c32f5c2f5193be97c7d29e919816944` |
| freeze commit = HEAD | `5ca40c7da87f583c7cea1cefd00cc978c3731d98` |
| tag (annotated) | `switchsync-synthetic-execution-v8-freeze` → `5ca40c7…` |

## 4. Attempt identity (token never stored in clear)

| field | value |
|---|---|
| campaign_id | `44be3a5d07e67b5e` |
| execution_scope | `cheap-suite` |
| authorization_token SHA-256 | `3b4b903518fa5cb337cbf5416aa8cc6db8db47c1548b39545f562158b07aca29` |
| attempt_id | `1baa47da06fede2a` |

The manifest's `structured_command` masks the token as
`<sha256:3b4b9035…>`; no clear token appears in any artifact.

## 5. Manifest / seal verification

- `verify_sealed_attempt` → **ok=True**, errors=[].
- SEALED marker == manifest_content_hash `4e029d814437695d99c4b5cc62cbe3cf94ebd0e46c6e9ae51d54cc5f28f3c33d`.
- Attempt contents = EXACTLY {`attempt_manifest.json`, `SEALED`, the 5 inventoried
  reports}. All frozen v8 hashes in the manifest match section 3.

## 6. Per-report SHA-256

| report | SHA-256 |
|---|---|
| `g0b_calibrated_v2.json` | `d592b75d59b6e50c51ec6263c0a8469654651e0ef247fd2fadd3cf5adad4d4e5` |
| `g0c_msf_v2.json` | `150a53dc42236742d347012704a00a4d2e1db52d99bb800341bbc3ec6de484d0` |
| `g1_g2_paired_v2.json` | `b6242cd72510ce6d8b0daa5edba31b1c124f3fa519eae92ac0a408f06decbce0` |
| `g3_robustness_v2.json` | `2f16a4578c5b48cbb8621455b5a37042ec615a7127c9d709acb43ab1a3414964` |
| `g4_identifiability_v2.json` | `bd148d1ed23ba057df41dedfbdb7414b7d450a7f5c28b59617e354d5bbb597e6` |

## 7. Verdicts and complete metrics

### G0B — CALIBRATED_DEMONSTRATION (σ_inter=1.5, N=40) → **PASS**
`fast_all_sync=True`, `slow_all_not_sync=True`; 5/5 seeds successful in every cell,
0 failures.

| T_swt | 2 | 5 | 10 | 20 | 40 | 80 | 160 | 300 |
|---|---|---|---|---|---|---|---|---|
| frac_synced | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.6 | 0.2 | 0.2 |

Fast band (T≤10) all ≥0.5; slow band (T≥160) all <0.5. (T=80 lies between the frozen
bands and is unconstrained.)

### G0C — minimal MSF → **INCONCLUSIVE (PARTIAL_NO_TSWT_DEPENDENCE)**
Transverse Lyapunov Ψ<0 across the ENTIRE grid (incl. fastest T_swt=11: Ψ from
−0.0084 at σ=0.05 to −0.177 at σ=0.8), so contraction exists; but the onset σ = **0.05
for every T_swt** (11/25/100/135) → `boundary_depends_on_Tswt=False`. 0 failures.

### G1/G2 (paired surrogate) — headline **INCONCLUSIVE (TIE)**
Arm selected on selection seeds = **fast** (scores fast +0.0366 > inter +0.0071 > slow
−0.0155). best-of-frozen-candidate static subset = [0,5,9,13,18,22] over 248 candidates.
0 evaluation failures, n=8 evaluation seeds.

| sub-gate | mean Δ | effect band | sign test | verdict | interpretable |
|---|---|---|---|---|---|
| G1_weak (arm − static_sparse) | +0.04197 | 0.06663 | 8+/0−, p=0.0078 | INCONCLUSIVE (TIE) | headline |
| G1_strict (arm − max(avg, best_static)) | −0.00457 | 0.02 | 0+/8−, p=0.0078 | INCONCLUSIVE (TIE) | **NOT_INTERPRETABLE** |
| G2_order (γ_ordered − median perm) | +0.00301 | 0.02 | 7+/1−, p=0.0703 | INCONCLUSIVE (NOT_SIGNIFICANT) | **NOT_INTERPRETABLE** |

G1_weak: the advantage is **consistently signed (8/8 positive, p=0.0078) but its
magnitude (+0.042) is inside the effect band (0.067)** → TIE, not PASS. Because
G1_weak did not PASS, G1_strict and G2 are NOT_INTERPRETABLE by the frozen hierarchy;
their diagnostic values are shown but must not be read as gate outcomes. (Diagnostic:
G1_strict mean is slightly negative — switching does not beat the aggregate/best-static
comparator.)

### G3 — robustness → **INCONCLUSIVE**
Gate rule: PASS iff BOTH `faithful` AND `mild_heterogeneity` PASS; `first_stage_without_pass=faithful`.
No stage EXECUTION_INVALID (the signed stage had valid per-seed negative weights and a
matching Frobenius budget). 0 failures in all stages.

| stage | mean Δ | band | sign test | verdict |
|---|---|---|---|---|
| faithful | +0.04922 | 0.07894 | 8+/0− | INCONCLUSIVE (TIE) |
| mild_heterogeneity | +0.04549 | 0.17150 | 8+/0− | INCONCLUSIVE (TIE) |
| strong_heterogeneity | +0.06307 | 0.29844 | — | INCONCLUSIVE (NOT_SIGNIFICANT) |
| directed | +0.06032 | 0.10060 | 8+/0− | INCONCLUSIVE (TIE) |
| signed | +0.04672 | 0.07988 | 8+/0− | INCONCLUSIVE (TIE) |

Every stage shows a consistently positive but sub-band advantage → the robustness gate
is INCONCLUSIVE (the required stages did not PASS).

### G4 — identifiability → **FAIL**
`accept = PASS iff ALL FOUR conditions hold`. Result: 2/4 hold.

| condition | value | holds? |
|---|---|---|
| mean precision > 0.6 | 0.3529 (sync) / 0.2544 (async 1:3) | **NO** |
| mean recall > 0.6 | 0.3529 (sync) | **NO** |
| contraction_corr_same_realization > 0.5 | 0.9483 (sync 1:1) / 0.0099 (async 1:3) | yes (sync) |
| beats factor-confounded baseline | basis 0.3529 vs levelcorr 0.1904; paired mean +0.16248, band 0.0646, 8+/0−, p=0.0078 → PASS | yes |

Precision/recall are far below the 0.6 bar; under asynchronous observation (1:3) the
contraction correlation collapses to 0.0099 (Epps-like degradation, as the prereg's
`async_language` anticipates). 0 failures, n=8.

## 8. Failures / nonfinite / dropped seeds

**None.** Every gate reports 0 failure records, 0 nonfinite, 0 dropped seeds; every
cell used its full seed block (G0B 5/5, G1/G2/G3/G4 n=8, G0C single seed).

## 9. G0A

**G0A = NOT_RUN** (scope `cheap-suite`), confirmed by the console
(`G0A_exact_reproduction: NOT_RUN (scope cheap-suite)`) and by its absence from the
manifest `gate_verdicts`.

## 10. Strict interpretation (per prereg v8)

- **G0B PASS** is a *calibrated qualitative demonstration* at σ_12=1.5, N=40 — **not**
  a reproduction of the paper regime and it makes **no N-dependence claim**. It shows
  only that, at this calibration, fast switching synchronizes and slow does not.
- The scientific claims of interest are **NOT established**:
  - **G1 (switching advantage): not established.** The fast-arm advantage over the
    equal-density static-sparse graph is consistently signed but within the effect band
    (TIE). G1_strict/G2 are NOT_INTERPRETABLE; their diagnostics point *against*
    switching beating aggregate connectivity.
  - **G2 (temporal order): not interpretable** and, diagnostically, not significant.
  - **G3 (robustness): INCONCLUSIVE** — no required stage reached PASS.
  - **G4 (identifiability): FAIL** — precision/recall below bar; asynchrony destroys
    the contraction correlation.
- This is an honest inconclusive/negative outcome. No rescue analysis, no new grid, no
  parameter search was performed, and no parameter was changed after observing results.

## 11. Repository state / no real data

- `git status` clean; HEAD = freeze commit `5ca40c7…`; annotated tag →
  `5ca40c7…`; `origin/main` unchanged at `40568308…` (**NO push**).
- Prior tags/freezes (v2–v7) preserved byte-for-byte.
- **No real/market data.** Inputs are synthetic FHN/surrogate simulations only; the
  run read no external data files. Results are sealed OUTSIDE the repo and **not
  committed**.

## 12. Package

This directory is the self-contained result package: the sealed attempt bundle
(`1baa47da06fede2a/`), the console log, this report, and `RESULT_MANIFEST.json` with a
SHA-256 for every file.
