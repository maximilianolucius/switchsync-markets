"""Executable scientific freeze v2 (fixes audit defects D1, D2, D3).

Improvements over v1:
  * Coverage: freezes src/, ALL runners + _common.py, tests/, prereg JSON+MD,
    evaluation/figure code, requirements.lock.txt, python-version.txt,
    source_ledger.csv, contract docs, and the source PDF's SHA.
  * Single content hash: a path-independent canonical hash over the whole manifest
    body (file SHAs + tracked spec + config hashes + env + commit). Stored and
    independently recomputable.
  * Added-file detection: the tracked spec is stored, so the verifier re-scans and
    flags files present now but absent from the manifest (executables added after
    the freeze).
  * Environment verification, refuse-overwrite, atomic write.
  * The verifier NEVER regenerates the manifest; it only reads and compares.
  * Path independence: all keys are repo-relative with forward slashes, so a copied
    repo at a different absolute path yields the identical content hash.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

MANIFEST_VERSION = 2


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def config_canonical_hash(config: dict) -> str:
    return _sha256_bytes(canonical_json(config).encode())


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()   # forward slashes => path independent


def _collect(root: Path, spec: dict) -> list[Path]:
    """Resolve the tracked spec into a sorted list of files.

    spec = {
      "roots":  [{"dir": "src", "ext": [".py"]}, ...],   # recursive by extension
      "files":  ["requirements.lock.txt", ...],          # explicit files
    }
    """
    found: set[Path] = set()
    for r in spec.get("roots", []):
        base = root / r["dir"]
        exts = set(r["ext"])
        if base.exists():
            for p in base.rglob("*"):
                if (p.is_file() and p.suffix in exts
                        and "__pycache__" not in p.parts):
                    found.add(p)
    for f in spec.get("files", []):
        p = root / f
        if p.exists():
            found.add(p)
    return sorted(found)


def environment_fingerprint() -> dict:
    mods = {}
    for name in ("numpy", "scipy", "matplotlib"):
        try:
            mods[name] = getattr(__import__(name), "__version__", "unknown")
        except Exception:
            mods[name] = "absent"
    return {"python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": mods}


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def compute_content_hash(body: dict) -> str:
    """Path-independent content hash over the manifest body (everything except the
    stored content_hash field itself)."""
    return _sha256_bytes(canonical_json(body).encode())


def build_manifest_v2(root: Path, spec: dict, config: dict,
                      config_rel: str, pdf_rel: str | None = None) -> dict:
    root = root.resolve()
    files = _collect(root, spec)
    file_hashes = {_rel(p, root): file_sha256(p) for p in files}
    body = {
        "manifest_version": MANIFEST_VERSION,
        "tracked_spec": spec,
        "files": file_hashes,
        "n_files": len(file_hashes),
        "config_rel": config_rel,
        "config_canonical_hash": config_canonical_hash(config),
        "config_file_sha256": file_sha256(root / config_rel),
        "pdf_rel": pdf_rel,
        "pdf_sha256": file_sha256(root / pdf_rel) if pdf_rel else None,
        "environment": environment_fingerprint(),
        "git_commit": _git_commit(root),
    }
    manifest = dict(body)
    manifest["content_hash"] = compute_content_hash(body)
    return manifest


def write_manifest_atomic(path: Path, manifest: dict) -> None:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing freeze: {path}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def verify_manifest_v2(root: Path, manifest: dict) -> dict:
    """Verify without regenerating. Detects modified, missing, and ADDED files,
    environment mismatch, and content-hash integrity."""
    root = root.resolve()
    recorded = manifest["files"]
    mismatches, missing = [], []
    for rel, h in recorded.items():
        p = root / rel
        if not p.exists():
            missing.append(rel)
        elif file_sha256(p) != h:
            mismatches.append(rel)

    # ADDED files: re-scan the tracked spec and flag anything not recorded.
    current = {_rel(p, root) for p in _collect(root, manifest["tracked_spec"])}
    added = sorted(current - set(recorded.keys()))

    # content-hash integrity: recompute from the body (exclude the stored hash).
    body = {k: v for k, v in manifest.items() if k != "content_hash"}
    recomputed = compute_content_hash(body)
    content_hash_ok = (recomputed == manifest.get("content_hash"))

    env_now = environment_fingerprint()
    env_ok = (env_now == manifest.get("environment"))
    env_diff = {} if env_ok else {"stored": manifest.get("environment"), "now": env_now}

    ok = (not mismatches and not missing and not added
          and content_hash_ok and env_ok)
    return {
        "ok": ok,
        "mismatches": mismatches,
        "missing": missing,
        "added": added,
        "content_hash_ok": content_hash_ok,
        "recomputed_content_hash": recomputed,
        "stored_content_hash": manifest.get("content_hash"),
        "environment_ok": env_ok,
        "environment_diff": env_diff,
        "n_checked": len(recorded),
    }
