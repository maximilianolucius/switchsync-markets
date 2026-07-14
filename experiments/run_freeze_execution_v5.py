"""Build and verify the EXECUTION freeze v4 (P1.2-B). Supersedes freeze v4.

Covers all src, all v2 runners + execution contract + custody + evaluators, tests,
prereg v5 (json+md) + execution contract v3, the audits and changelogs, DECISIONS,
STATUS, README, lockfile and python version, plus the preserved v1/v2/v3 configs,
sidecars and the source PDF SHA. Writes artifacts/freeze_execution_v4.json."""
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
        "README.md", "STATUS.md", "DECISIONS.md",
        "experiments/configs/synthetic_prereg_v5.json",
        "experiments/configs/synthetic_execution_contract_v3.json",
        "experiments/configs/synthetic_prereg_v4.json",
        "experiments/configs/synthetic_execution_contract_v2.json",
        "experiments/configs/synthetic_prereg_v3.json",
        "experiments/configs/synthetic_execution_contract_v1.json",
        "experiments/configs/synthetic_prereg_v2.json",
        "experiments/configs/synthetic_prereg_v2.SUPERSEDED.md",
        "experiments/configs/synthetic_prereg_v1.json",
        "docs/methodology/synthetic_prereg_v5.md",
        "docs/methodology/prereg_v4_to_v5_changelog.md",
        "docs/methodology/synthetic_prereg_v4.md",
        "docs/methodology/prereg_v3_to_v4_changelog.md",
        "docs/methodology/synthetic_prereg_v3.md",
        "docs/methodology/prereg_v2_to_v3_changelog.md",
        "docs/methodology/synthetic_prereg_v2.md",
        "docs/methodology/intermediate_rate_temporal_advantage_prereg_v1.md",
        "docs/audits/p1_2b_independent_audit.md",
        "docs/audits/p1_2a_independent_audit.md",
        "docs/audits/p1_v1_independent_audit.md",
        "docs/research/source_ledger.csv",
        "docs/LICENSE_BLOCKER.md",
        "CITATION.cff", "SECURITY.md", ".github/workflows/ci.yml",
        "artifacts/freeze_execution_v4.SUPERSEDED.md",
        "artifacts/freeze_execution_v3.SUPERSEDED.md",
        "experiments/reports/reproduction_g0.superseded.json",
        "experiments/reports/causal_fhn_g1.superseded.json",
        "experiments/reports/surrogate_causal_g1_g2.superseded.json",
        "experiments/reports/surrogate_stages_g3.superseded.json",
        "experiments/reports/identifiability_g4.superseded.json",
        "experiments/reports/msf_minimal.superseded.json",
    ],
}
CONFIG_REL = "experiments/configs/synthetic_prereg_v5.json"
PDF_REL = "docs/research/sources/eser2025_arxiv_2507.08007v2.pdf"
OUT = "artifacts/freeze_execution_v5.json"


def main() -> None:
    config = json.loads((REPO_ROOT / CONFIG_REL).read_text())
    manifest = build_manifest_v2(REPO_ROOT, SPEC, config, CONFIG_REL, PDF_REL)
    out = REPO_ROOT / OUT
    out.parent.mkdir(exist_ok=True)
    write_manifest_atomic(out, manifest)
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    print(f"execution freeze v5 written: {manifest['n_files']} files -> {out}")
    print(f"prereg v5 canonical : {manifest['config_canonical_hash']}")
    print(f"prereg v4 file SHA  : {manifest['config_file_sha256']}")
    print(f"freeze content_hash : {manifest['content_hash']}")
    print(f"git_commit          : {manifest['git_commit']}")
    print(f"verification: ok={ver['ok']} checked={ver['n_checked']} added={ver['added']} "
          f"missing={ver['missing']} content_hash_ok={ver['content_hash_ok']} env_ok={ver['environment_ok']}")


if __name__ == "__main__":
    main()
