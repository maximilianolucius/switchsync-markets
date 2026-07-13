"""Build and verify the EXECUTION freeze v3 (P1.2-A).

Supersedes freeze_execution_v2.json (which froze a mutated prereg). Covers the
corrected modules, ALL v2 runners + execution contract/evaluators/schema, tests,
the scientific prereg v3 + execution contract v1, the RESTORED prereg v2 (+ its
SUPERSEDED marker) and the v2->v3 changelog, lockfiles, the v1 audit + supersession
sidecars, plus the source PDF SHA, git commit and environment. Writes
artifacts/freeze_execution_v3.json (refuses overwrite)."""
from __future__ import annotations

import json

from _common import REPO_ROOT
from src.validation.freeze_v2 import (
    build_manifest_v2,
    verify_manifest_v2,
    write_manifest_atomic,
)

SPEC = {
    "roots": [
        {"dir": "src", "ext": [".py"]},
        {"dir": "experiments", "ext": [".py"]},
        {"dir": "tests", "ext": [".py"]},
    ],
    "files": [
        "requirements.lock.txt", "python-version.txt", "conftest.py",
        "experiments/configs/synthetic_prereg_v3.json",
        "experiments/configs/synthetic_execution_contract_v1.json",
        "experiments/configs/synthetic_prereg_v2.json",
        "experiments/configs/synthetic_prereg_v2.SUPERSEDED.md",
        "experiments/configs/synthetic_prereg_v1.json",
        "docs/methodology/synthetic_prereg_v3.md",
        "docs/methodology/prereg_v2_to_v3_changelog.md",
        "docs/methodology/synthetic_prereg_v2.md",
        "docs/methodology/intermediate_rate_temporal_advantage_prereg_v1.md",
        "docs/audits/p1_v1_independent_audit.md",
        "docs/research/source_ledger.csv",
        "docs/LICENSE_BLOCKER.md",
        "CITATION.cff", "SECURITY.md", ".github/workflows/ci.yml",
        "experiments/reports/reproduction_g0.superseded.json",
        "experiments/reports/causal_fhn_g1.superseded.json",
        "experiments/reports/surrogate_causal_g1_g2.superseded.json",
        "experiments/reports/surrogate_stages_g3.superseded.json",
        "experiments/reports/identifiability_g4.superseded.json",
        "experiments/reports/msf_minimal.superseded.json",
    ],
}
CONFIG_REL = "experiments/configs/synthetic_prereg_v3.json"
PDF_REL = "docs/research/sources/eser2025_arxiv_2507.08007v2.pdf"
OUT = "artifacts/freeze_execution_v3.json"


def main() -> None:
    config = json.loads((REPO_ROOT / CONFIG_REL).read_text())
    manifest = build_manifest_v2(REPO_ROOT, SPEC, config, CONFIG_REL, PDF_REL)
    out = REPO_ROOT / OUT
    out.parent.mkdir(exist_ok=True)
    write_manifest_atomic(out, manifest)
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    print(f"execution freeze v3 written: {manifest['n_files']} files -> {out}")
    print(f"prereg v3 canonical : {manifest['config_canonical_hash']}")
    print(f"prereg v3 file SHA  : {manifest['config_file_sha256']}")
    print(f"freeze content_hash : {manifest['content_hash']}")
    print(f"git_commit          : {manifest['git_commit']}")
    print(f"verification: ok={ver['ok']} checked={ver['n_checked']} added={ver['added']} "
          f"missing={ver['missing']} content_hash_ok={ver['content_hash_ok']} env_ok={ver['environment_ok']}")


if __name__ == "__main__":
    main()
