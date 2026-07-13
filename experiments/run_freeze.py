"""Compute the contract hash, write and verify the freeze manifest.

Usage: python3 experiments/run_freeze.py
Writes artifacts/freeze_manifest_v1.json and prints the config hash + verification.
"""
from __future__ import annotations

import json

from _common import REPO_ROOT, load_contract
from src.validation.freeze import config_hash, freeze_manifest, verify_manifest


def main() -> None:
    contract = load_contract()
    h = config_hash(contract)
    manifest = freeze_manifest(REPO_ROOT, roots=["src", "experiments/configs"],
                               config=contract)
    out = REPO_ROOT / "artifacts" / "freeze_manifest_v1.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    ver = verify_manifest(REPO_ROOT, manifest)
    print(f"contract config_hash = {h}")
    print(f"freeze manifest: {manifest['n_files']} files -> {out}")
    print(f"verification: ok={ver['ok']} checked={ver['n_checked']} "
          f"mismatches={ver['mismatches']} missing={ver['missing']}")
    print(f"environment: {manifest['environment']}")


if __name__ == "__main__":
    main()
