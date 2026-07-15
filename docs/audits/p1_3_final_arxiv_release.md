# P1.3-B Final arXiv Release — SwitchSync Markets manuscript

**Scope:** author-metadata substitution, license record, final typography, arXiv
source packaging, commit and annotated tag. **No simulation executed, modified or
reinterpreted.** All sealed results, the five gate JSONs, `RESULT_REPORT.md`,
`RESULT_MANIFEST.json`, `RESULTS_REGISTRY.json`, prereg v8, execution contract v6,
freeze v8 and every prior tag are byte-for-byte unchanged.

## Author and license (confirmed by the owner)

| field | value |
|---|---|
| Author | Maximiliano Lucius |
| Affiliation | Independent Researcher, Buenos Aires, Argentina |
| Email | `maximiliano@aureus-finance.com` |
| ORCID | none (not included) |
| arXiv submission license | Creative Commons Attribution 4.0 International (CC BY 4.0) |

The CC BY 4.0 choice applies to the **manuscript only**. It does not create or
modify the repository's general code license, which remains a separate, still-open
decision (`docs/LICENSE_BLOCKER.md`).

## Changes applied

- `paper/main.tex`: `\author{}` replaced with the Maximiliano Lucius block (name,
  affiliation, email; no ORCID); footnote records the CC BY 4.0 manuscript license.
  `\hypersetup` `pdfauthor` set to `Maximiliano Lucius`. §8 retitled
  "Why the Results Favor Aggregate Connectivity" (single line; no split word).
  All placeholder / `PAPER_RC_BLOCKED_ON_AUTHOR_METADATA_AND_LICENSE` / "AUTHOR
  NAME PENDING" / "PLACEHOLDER" text and every missing-author/license claim
  removed.
- `paper/tables/table_audit.tex`: float specifier `[h]` → `[ht]` (removes the
  "[h] changed to [ht]" warning).
- `paper/arxiv_readme.md`: status changed to FINALIZED; records the author and the
  CC BY 4.0 manuscript license (repo code license explicitly left separate); adds
  the exact arXiv upload instruction.
- `CITATION.cff`: `authors` = Lucius, Maximiliano (email + affiliation, no ORCID);
  all blocker language removed; manuscript license noted as CC BY 4.0.

## Compilation and QA (from scratch)

- `latexmk -pdf main.tex` exit 0; **14 pages**; **0** Overfull \hbox; **0** undefined
  citations/references; **32/32** bibliography entries cited (none missing, none
  uncited); **5** figures resolved; all fonts embedded (`pdffonts`).
- PDF metadata (`pdfinfo`): Title = full title; Author = `Maximiliano Lucius`;
  Subject and Keywords set.
- Visual review of all 14 pages: author block and CC BY 4.0 footnote render on p.1;
  §8 title on a single line on p.7; figures and tables intact.

## arXiv source package (deterministic)

- File: `switchsync-arxiv-v1.tar.gz`
  (built at `/media/maxim/MX00x/working_dir/tmp/p1_3_audit/arxiv_final/`).
- Contents (`main.tex` at the archive ROOT): `main.tex`, `main.bbl`,
  `references.bib`, `tables/*.tex` (4), `figures/*.pdf` (5). Excludes the compiled
  PDF, scientific results, scripts, and all `.aux/.log/.fls/.fdb_latexmk`/caches.
- Normalized headers: `--sort=name`, `--owner=0 --group=0 --numeric-owner`, fixed
  mtime, gzip `-n` (no timestamp). Extracts without `--no-same-owner` as a normal
  user; re-compiles from a fresh directory (exit 0, 14 pages, Author =
  Maximiliano Lucius).

## Hashes (SHA-256)

| object | SHA-256 |
|---|---|
| `paper/main.tex` | `4d02c60be10658457bb454c87fdbadd9a2b8f1bd4c0709b9c518a09c627c0468` |
| `paper/main.pdf` | `0e6085a0d3b9f62c5bf7f161115a5ae3b517c55c82a37e7b23672c61c94651f3` |
| `switchsync-arxiv-v1.tar.gz` | `62037386fce5dcb1aa8ec778994df2c73c6522f4c7363d549460efc9c9eab14f` |

## Scientific-artifact integrity (re-verified this phase)

Five gate JSONs, `attempt_manifest.json`, `SEALED`, `RESULT_MANIFEST.json` →
`sha256sum -c` PASS; prereg v8 file SHA, exec v6 file SHA and freeze v8 content
hash all match their frozen values; `RESULTS_REGISTRY.json` untouched. Attempt
`1baa47da06fede2a` under freeze v8 remains the only scientific execution.

## Status

NO-RUN / NO-PUSH / NO-SUBMISSION. Commit "Finalize SwitchSync Markets arXiv
manuscript"; annotated tag `switchsync-paper-arxiv-v1`; no prior tag moved.
