"""Build and verify the executable freeze v2 manifest.

Usage: python3 experiments/run_freeze_v2.py
Writes artifacts/freeze_manifest_v2.json (refuses to overwrite) and prints the
content hash + a full verification (which must not regenerate the manifest).
"""
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
        "requirements.lock.txt",
        "python-version.txt",
        "conftest.py",
        "experiments/configs/synthetic_prereg_v2.json",
        "experiments/configs/synthetic_prereg_v1.json",
        "docs/research/source_ledger.csv",
        "docs/methodology/synthetic_prereg_v2.md",
        "docs/methodology/intermediate_rate_temporal_advantage_prereg_v1.md",
        "docs/audits/p1_v1_independent_audit.md",
        "CITATION.cff",
        ".github/workflows/ci.yml",
    ],
}
CONFIG_REL = "experiments/configs/synthetic_prereg_v2.json"
PDF_REL = "docs/research/sources/eser2025_arxiv_2507.08007v2.pdf"


def main() -> None:
    config = json.loads((REPO_ROOT / CONFIG_REL).read_text())
    manifest = build_manifest_v2(REPO_ROOT, SPEC, config, CONFIG_REL, PDF_REL)
    out = REPO_ROOT / "artifacts" / "freeze_manifest_v2.json"
    out.parent.mkdir(exist_ok=True)
    write_manifest_atomic(out, manifest)
    ver = verify_manifest_v2(REPO_ROOT, manifest)
    print(f"freeze v2 written: {manifest['n_files']} files -> {out}")
    print(f"config_canonical_hash : {manifest['config_canonical_hash']}")
    print(f"config_file_sha256    : {manifest['config_file_sha256']}")
    print(f"freeze content_hash   : {manifest['content_hash']}")
    print(f"git_commit            : {manifest['git_commit']}")
    print(f"pdf_sha256            : {manifest['pdf_sha256']}")
    print(f"verification: ok={ver['ok']} checked={ver['n_checked']} "
          f"added={ver['added']} missing={ver['missing']} "
          f"content_hash_ok={ver['content_hash_ok']} env_ok={ver['environment_ok']}")


if __name__ == "__main__":
    main()
