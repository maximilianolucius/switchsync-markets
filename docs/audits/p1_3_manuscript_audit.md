# P1.3-A Manuscript Audit — editorial/transparency corrections (release candidate)

**Scope:** exclusively editorial and transparency corrections to the arXiv
manuscript and editorial documentation. **No simulation was executed, modified or
reinterpreted.** The five sealed gate JSONs, `attempt_manifest.json`, `SEALED`,
`RESULT_MANIFEST.json`, `RESULT_REPORT.md`, `RESULTS_REGISTRY.json`, prereg v8,
execution contract v6, freeze v8 and every prior tag are byte-for-byte unchanged.
(`RESULTS_REGISTRY.json` retains its historical "independent_audit" field name: it
is under the absolute do-not-modify restriction; the terminology correction is
applied in the manuscript and editorial documentation only.)

## Recomputation gate (pre-edit; MANDATORY)

Every decision statistic was re-derived from the sealed `paired_differences`
arrays (mean; sample sd ddof=1; band = max(3·sd, floor); exact two-sided sign
test) and compared against the stored JSON fields and the manuscript strings:
**34/34 MATCH** across G0B (fractions row), G1-weak, G1-strict (diagnostic),
G2 (diagnostic), all five G3 stages, G4 (metrics + beats-baseline margin) and the
G0C onset. No mismatch; the phase proceeded.

## Defect → correction → verification

| # | Defect | Correction | Verification |
|---|--------|------------|--------------|
| a | The frozen floors sentence grouped "FHN $E_{12}$ 0.02" with the effect-band floors, inviting confusion with G0B's deterministic synchronization threshold (also 0.02). | §Contract: floors restated as 0.02 for surrogate-γ paired differences and 0.05 for the G4 margin; an explicit sentence states the G0B tail-E12<0.02 criterion is a deterministic per-seed threshold, "numerically equal but contractually distinct". §Design (G0B) reworded accordingly. | grep: no remaining text describes E12=0.02 as an effect-band floor; compile clean. |
| b | Abstract said "no temporal-order effect was resolved", eliding the frozen hierarchy. | Replaced with: "Because G1-weak did not pass, G2 was formally NOT_INTERPRETABLE; its diagnostic order statistic was non-significant." | String present in abstract; hierarchy preserved. |
| c | §8 title "Why Aggregate Connectivity Dominates the Interpretation" overstated (dominance is an interpretation, not a demonstrated theorem). | Retitled "Why the Results Favor an Aggregate-Connectivity Interpretation". | Title updated; TOC/refs recompiled. |
| d | "Even in the most favorable conditions finance can never offer" was an absolute claim. | Replaced with "Under synthetic conditions more favorable than those normally available in empirical finance". | String replaced in §Identifiability. |
| e | "monotone descent" overdescribed the G0B sequence (1.0,1.0,1.0,1.0,1.0,0.6,0.2,0.2 — non-increasing, with plateaus). | Replaced with "non-increasing transition" plus the explicit observed sequence (1.0→1.0→0.6→0.2 for T=20,40,80,160). | Matches the sealed rows. |
| f | First prose mention of Eser et al. did not identify the publication status. | Intro now opens "In a recent arXiv preprint, Eser, Medeiros, Riza and Engel…"; the bib entry already carries arXiv:2507.08007 [nlin.AO]. | First mention labelled; no duplication introduced. |
| g | "independent audit" implied a documented external human auditor; none is evidenced. | Replaced with "separate post-execution artifact audit" (result) and "separate pre-execution artifact audits" (freezes v2–v7) in main.tex, table_audit.tex, arxiv_readme.md and the STATUS.md closure line. Sealed artifacts and the historical DECISIONS log entries untouched. | grep over paper/: no bare "independent audit" remains; sealed files byte-identical. |
| h | No AI-involvement disclosure. | Added unnumbered "Transparency Statement" (verbatim per instruction) before the appendices. | Present in PDF. |
| i | Author was "SwitchSync Markets Project" — not a valid final arXiv author. | Replaced with an explicit marked placeholder; footnote declares `PAPER_RC_BLOCKED_ON_AUTHOR_METADATA_AND_LICENSE`. No name/affiliation/email/ORCID fabricated. | Placeholder visible on p.1; blocker declared here, in arxiv_readme.md and CITATION.cff. |
| j | No PDF metadata. | `\hypersetup{pdftitle, pdfauthor (placeholder), pdfsubject, pdfkeywords}` added. | `pdfinfo` shows the four fields. |
| k | One Overfull \hbox (8.3pt, §Translation item 2). | Rephrased "interdependence/heteroskedasticity confound" → "confound between interdependence and heteroskedasticity". | Zero Overfull \hbox in the final log. |
| l | CITATION.cff described the pre-execution P1 state and dated the seed preprint 2026 (ledger says 2025). | Updated to the closed P1.3 state (verdict summary, results-v2, RC status), seed year 2025 per the verified ledger, explicit author-metadata + license blockers. No personal identity invented. | cff parses as YAML; blocker text present. |

## QA gate (post-edit)

- latexmk exit 0; 14 pages; **zero** undefined citations/references; **zero**
  Overfull \hbox; 32/32 bibliography entries cited; five figures resolved; fonts
  embedded (`pdffonts`: no unembedded fonts); visual review of all 14 pages.
- All figures/tables regenerated only from the sealed JSONs (no simulation).

## Blockers (human input required; deliberately not fabricated)

**`PAPER_RC_BLOCKED_ON_AUTHOR_METADATA_AND_LICENSE`**

1. Human author name, affiliation, contact email, optional ORCID.
2. arXiv submission license and repository license (`docs/LICENSE_BLOCKER.md`).

No final paper tag is created until both are resolved. NO-RUN / NO-PUSH.
