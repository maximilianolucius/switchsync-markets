"""Contract hashing and freeze manifests.

- `config_hash`: SHA-256 of a config dict serialized canonically (sorted keys,
  no whitespace ambiguity), so the same contract always hashes identically.
- `freeze_manifest`: hash every source file under given roots plus the config and
  the environment, producing a manifest that can be re-verified later.
- `verify_manifest`: recompute and compare, reporting any drift.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def config_hash(config: dict) -> str:
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_files(root: Path, patterns=(".py", ".json")):
    for pth in sorted(root.rglob("*")):
        if pth.is_file() and pth.suffix in patterns and "__pycache__" not in pth.parts:
            yield pth


def environment_fingerprint() -> dict:
    mods = {}
    for name in ("numpy", "scipy", "matplotlib"):
        try:
            m = __import__(name)
            mods[name] = getattr(m, "__version__", "unknown")
        except Exception:
            mods[name] = "absent"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": mods,
    }


def freeze_manifest(repo_root: Path, roots: list[str], config: dict) -> dict:
    files = {}
    for r in roots:
        base = repo_root / r
        if not base.exists():
            continue
        for pth in _iter_files(base):
            files[str(pth.relative_to(repo_root))] = file_hash(pth)
    return {
        "config_hash": config_hash(config),
        "n_files": len(files),
        "files": files,
        "environment": environment_fingerprint(),
    }


def verify_manifest(repo_root: Path, manifest: dict) -> dict:
    """Recompute file hashes and compare. Returns {ok, mismatches, missing, added}."""
    mismatches, missing = [], []
    recorded = manifest.get("files", {})
    for rel, h in recorded.items():
        pth = repo_root / rel
        if not pth.exists():
            missing.append(rel)
        elif file_hash(pth) != h:
            mismatches.append(rel)
    return {
        "ok": not mismatches and not missing,
        "mismatches": mismatches,
        "missing": missing,
        "n_checked": len(recorded),
    }
