# LICENSE — BLOCKER (no license chosen; none invented)

**Status: BLOCKED — decision required from the repository owner.**

No `LICENSE` file has been added, and none will be invented. Choosing a license is a
legal/authorship decision that only the owner can make; guessing one would be wrong
and potentially harmful (an incorrect license can mislead reusers about their rights).

## Why this is a blocker, not a default

- The repository currently has **no declared license**, which under default copyright
  means "all rights reserved" — others may view it (it is public) but have no granted
  rights to copy, modify, or redistribute.
- The repo contains a third-party artifact: `docs/research/sources/eser2025_arxiv_2507.08007v2.pdf`
  (arXiv:2507.08007). arXiv papers carry their **own** license (often the arXiv
  non-exclusive license or a CC variant chosen by the authors); **the repository's
  license cannot and does not relicense that PDF.** Its redistribution terms are the
  authors'/arXiv's, independent of whatever license the owner picks for the code.

## Decision the owner must make

1. Pick a code license for the owner's original work (common research choices: **MIT**
   or **BSD-3-Clause** for permissive reuse; **Apache-2.0** if patent grant matters;
   **GPL-3.0** for copyleft; **CC-BY-4.0** for the prose/docs). These have different
   obligations — this file does not recommend one.
2. Decide how to handle the bundled arXiv PDF: keep it (subject to its own terms) or
   remove it and rely on the recorded SHA-256 + arXiv URL in `engel_paper_audit.md`.

## When resolved

Add a top-level `LICENSE` file with the chosen license text, add an SPDX header or a
`## License` section to `README.md`, and (if relevant) a `NOTICE`/attribution for the
bundled PDF. Then delete or update this blocker.
