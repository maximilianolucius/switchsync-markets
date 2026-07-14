"""Durable checkpoint ledger + immutable attempt publication (P1.2-C).

CheckpointLedger v2 (contract F): append-only JSONL with a per-record hash chain:
  {"seq": n, "prev_record_hash": h_{n-1}, "cell": {...}, "result": {...},
   "provenance_key": pk, "record_hash": sha256(canonical(body))}
On load it verifies: strictly sequential seq (no gaps), an unbroken prev/record
hash chain (detects reordering and changed results), no duplicate cell UIDs, and
matching provenance. A truncated/corrupt LAST line raises TruncatedTail (the valid
prefix is preserved, never silently deleted); loading past it requires the explicit
`allow_truncated_tail=True` (resume authorization path only). Corruption anywhere
else raises CheckpointCorrupt.

Attempt publication (contracts C/D/E): each authorized execution attempt owns
  <run-dir>/<attempt_id>.staging/      work in progress
  <run-dir>/<attempt_id>.failed/       failure ledger (no success bundle)
  <run-dir>/<attempt_id>.interrupted/  preserved staging after crash/interruption
  <run-dir>/<attempt_id>/              final, immutable, SEALED
Publication builds attempt_manifest.json (with its own content hash), fsyncs,
re-verifies every report SHA, atomically renames staging -> final and writes the
SEALED marker. A SEALED directory refuses further writes. An flock on
<run-dir>/<attempt_id>.lock prevents concurrent executions of the same attempt.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class CheckpointCorrupt(Exception):
    pass


class TruncatedTail(CheckpointCorrupt):
    """Last ledger line is truncated/corrupt; the valid prefix is preserved."""

    def __init__(self, msg, n_valid):
        super().__init__(msg)
        self.n_valid = n_valid


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _fsync_dir(p: Path) -> None:
    fd = os.open(str(p), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Checkpoint ledger v2 (hash chain)
# ---------------------------------------------------------------------------
GENESIS = "GENESIS"


class CheckpointLedger:
    def __init__(self, path, provenance: dict, key_fields,
                 allow_truncated_tail: bool = False):
        self.path = Path(path)
        self.provenance = provenance
        self.key_fields = list(key_fields)
        self.allow_truncated_tail = allow_truncated_tail
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: dict[str, dict] = {}
        self._last_hash = GENESIS
        self._next_seq = 0
        if self.path.exists():
            self._load()

    def _provenance_key(self) -> str:
        return "|".join(f"{k}={self.provenance.get(k)}" for k in sorted(self.provenance))

    def _cell_key(self, cell: dict) -> str:
        return "|".join(f"{k}={cell[k]}" for k in self.key_fields)

    def _record_body(self, seq, prev, cell, result):
        return {"seq": seq, "prev_record_hash": prev, "cell": cell,
                "result": result, "provenance_key": self._provenance_key()}

    def _load(self) -> None:
        raw = self.path.read_text()
        lines = raw.split("\n")
        # a well-formed ledger ends with a newline => last element is ""
        complete_lines = lines[:-1] if lines and lines[-1] == "" else lines[:-1]
        tail = "" if (lines and lines[-1] == "") else lines[-1]

        prev = GENESIS
        for i, line in enumerate(complete_lines):
            if not line.strip():
                raise CheckpointCorrupt(f"blank interior line {i}")
            try:
                rec = json.loads(line)
            except Exception as e:
                raise CheckpointCorrupt(f"line {i} is not valid JSON: {e}")
            for f in ("seq", "prev_record_hash", "cell", "result",
                      "provenance_key", "record_hash"):
                if f not in rec:
                    raise CheckpointCorrupt(f"line {i} missing field {f}")
            if rec["seq"] != i:
                raise CheckpointCorrupt(
                    f"sequence violation at line {i}: seq={rec['seq']} (gap or reorder)")
            if rec["prev_record_hash"] != prev:
                raise CheckpointCorrupt(f"hash chain broken at line {i} (reordered or edited)")
            body = self._record_body(rec["seq"], rec["prev_record_hash"],
                                     rec["cell"], rec["result"])
            if rec["provenance_key"] != self._provenance_key():
                raise CheckpointCorrupt(f"line {i} has foreign provenance")
            expect = _sha(_canonical(body))
            if rec["record_hash"] != expect:
                raise CheckpointCorrupt(f"record hash mismatch at line {i} (result changed?)")
            key = self._cell_key(rec["cell"])
            if key in self._done:
                raise CheckpointCorrupt(f"duplicate cell UID at line {i}: {key}")
            self._done[key] = rec
            prev = rec["record_hash"]

        self._last_hash = prev
        self._next_seq = len(complete_lines)

        if tail:
            # truncated (no trailing newline) or corrupt final line: preserve
            # the prefix; never delete evidence; require authorization to go on.
            if not self.allow_truncated_tail:
                raise TruncatedTail(
                    f"ledger has a truncated/corrupt final line after "
                    f"{self._next_seq} valid records; resume requires authorization",
                    n_valid=self._next_seq)
            # authorized: keep prefix loaded; the truncated tail stays on disk
            # untouched and subsequent appends go AFTER it is preserved by moving
            # the file to a .truncated evidence copy first.
            evidence = self.path.with_suffix(self.path.suffix + ".truncated")
            if not evidence.exists():
                evidence.write_text(raw)
                _fsync_dir(self.path.parent)
            valid = "\n".join(complete_lines)
            self.path.write_text(valid + ("\n" if valid else ""))
            _fsync_dir(self.path.parent)

    def has(self, cell: dict) -> bool:
        return self._cell_key(cell) in self._done

    def append(self, cell: dict, result: dict) -> None:
        key = self._cell_key(cell)
        if key in self._done:
            raise CheckpointCorrupt(f"duplicate cell refused: {key}")
        body = self._record_body(self._next_seq, self._last_hash, cell, result)
        rec = dict(body)
        rec["record_hash"] = _sha(_canonical(body))
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        _fsync_dir(self.path.parent)
        self._done[key] = rec
        self._last_hash = rec["record_hash"]
        self._next_seq += 1

    def completed(self) -> list:
        return list(self._done.values())

    def n_completed(self) -> int:
        return len(self._done)


# ---------------------------------------------------------------------------
# Attempt directories, lock, manifest, seal
# ---------------------------------------------------------------------------
def staging_dir(run_dir, attempt_id: str) -> Path:
    return Path(run_dir) / f"{attempt_id}.staging"


def failed_dir(run_dir, attempt_id: str) -> Path:
    return Path(run_dir) / f"{attempt_id}.failed"


def interrupted_dir(run_dir, attempt_id: str) -> Path:
    return Path(run_dir) / f"{attempt_id}.interrupted"


def final_dir(run_dir, attempt_id: str) -> Path:
    return Path(run_dir) / attempt_id


class AttemptLock:
    """Exclusive flock preventing concurrent executions of the same attempt_id."""

    def __init__(self, run_dir, attempt_id: str):
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(run_dir) / f"{attempt_id}.lock"
        self._fh = None

    def acquire(self) -> bool:
        self._fh = open(self.path, "a+")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self._fh.close()
            self._fh = None
            return False

    def release(self) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


RESERVED = {"attempt_manifest.json", "SEALED"}


def _safe_relname(name: str) -> bool:
    if name in ("", ".", ".."):
        return False
    if name.startswith("/") or ".." in Path(name).parts:
        return False
    return True


def inventory_staging(staging: Path, roles: dict) -> dict:
    """Build the artifact inventory of a staging dir: for every regular file that
    is NOT a reserved name, record size, sha256 and a declared role. Rejects
    symlinks / non-regular files and any file lacking a declared role (unexpected
    file). Rejects unsafe names. Returns {name: {size, sha256, role}}."""
    staging = Path(staging)
    inv = {}
    for p in sorted(staging.rglob("*")):
        rel = p.relative_to(staging).as_posix()
        if rel in RESERVED:
            raise CheckpointCorrupt(f"reserved name present before sealing: {rel}")
        if p.is_dir():
            continue
        if p.is_symlink() or not p.is_file():
            raise CheckpointCorrupt(f"non-regular/symlink artifact refused: {rel}")
        if not _safe_relname(rel):
            raise CheckpointCorrupt(f"unsafe artifact name: {rel}")
        if rel not in roles:
            raise CheckpointCorrupt(f"unexpected (undeclared) artifact: {rel}")
        data = p.read_bytes()
        inv[rel] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "role": roles[rel]}
    missing_roles = set(roles) - set(inv)
    if missing_roles:
        raise CheckpointCorrupt(f"declared artifacts missing from staging: {sorted(missing_roles)}")
    return inv


def build_attempt_manifest(*, campaign_id, attempt_id, execution_scope, hashes,
                           head, tag, structured_command, runner_shas,
                           orchestrator_sha, authorization_token_sha256,
                           started_utc, ended_utc, exit_status, artifacts: dict,
                           gate_verdicts, environment):
    body = {
        "campaign_id": campaign_id, "attempt_id": attempt_id,
        "execution_scope": execution_scope, "hashes": hashes,
        "head": head, "tag": tag, "structured_command": structured_command,
        "runner_shas": runner_shas, "orchestrator_sha256": orchestrator_sha,
        "authorization_token_sha256": authorization_token_sha256,
        "started_utc": started_utc, "ended_utc": ended_utc,
        "exit_status": exit_status, "artifacts": artifacts,
        "gate_verdicts": gate_verdicts, "environment": environment,
        "state": "COMPLETED",
    }
    manifest = dict(body)
    manifest["manifest_content_hash"] = _sha(_canonical(body))
    return manifest


def _write_fsync(path: Path, text: str) -> None:
    with open(path, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def seal_and_publish(staging: Path, final: Path, manifest: dict) -> None:
    """Write manifest + SEALED INTO staging, fsync, verify the full inventory,
    then a SINGLE atomic rename staging->final (no final-without-SEAL window).
    Re-verify the exact inventory afterward."""
    staging, final = Path(staging), Path(final)
    if final.exists():
        raise FileExistsError(f"refusing to overwrite published attempt: {final}")
    inv = manifest["artifacts"]
    # verify each inventoried artifact exists with the right size + hash
    for name, meta in inv.items():
        p = staging / name
        if not p.exists() or p.is_symlink() or not p.is_file():
            raise CheckpointCorrupt(f"artifact missing/irregular before publish: {name}")
        data = p.read_bytes()
        if len(data) != meta["size"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise CheckpointCorrupt(f"artifact size/hash mismatch before publish: {name}")
    # no undeclared files present
    for p in staging.rglob("*"):
        if p.is_file():
            rel = p.relative_to(staging).as_posix()
            if rel not in inv and rel not in RESERVED:
                raise CheckpointCorrupt(f"unexpected file before sealing: {rel}")
    # write manifest + SEALED INSIDE staging, fsync everything
    _write_fsync(staging / "attempt_manifest.json",
                 json.dumps(manifest, indent=2, sort_keys=True))
    _write_fsync(staging / "SEALED", manifest["manifest_content_hash"] + "\n")
    for p in staging.rglob("*"):
        if p.is_file():
            fd = os.open(str(p), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    _fsync_dir(staging)
    os.replace(staging, final)          # single atomic publish; SEALED already inside
    _fsync_dir(final.parent)
    res = verify_sealed_attempt(final)   # post-rename re-verification of the exact inventory
    if not res["ok"]:
        raise CheckpointCorrupt(f"post-publish verification failed: {res['errors']}")


def verify_sealed_attempt(final: Path) -> dict:
    """Adversarially verify a sealed attempt. Rejects: tampered manifest/SEALED,
    corrupt/missing/extra/wrong-size/wrong-hash artifact, symlink or non-regular
    file, absolute or '..' path. A valid attempt contains EXACTLY
    attempt_manifest.json, SEALED and the inventoried artifacts."""
    final = Path(final)
    errors = []
    man_p = final / "attempt_manifest.json"
    seal_p = final / "SEALED"
    if not man_p.is_file() or not seal_p.is_file():
        return {"ok": False, "errors": ["missing manifest or SEALED marker"]}
    try:
        manifest = json.loads(man_p.read_text())
    except Exception as e:
        return {"ok": False, "errors": [f"manifest not JSON: {e}"]}
    body = {k: v for k, v in manifest.items() if k != "manifest_content_hash"}
    mh = manifest.get("manifest_content_hash")
    if _sha(_canonical(body)) != mh:
        errors.append("manifest content hash mismatch")
    if seal_p.read_text().strip() != mh:
        errors.append("SEALED marker does not match manifest hash")
    inv = manifest.get("artifacts", {})
    # every inventoried artifact present, regular, correct size + hash
    for name, meta in inv.items():
        if not _safe_relname(name):
            errors.append(f"unsafe artifact name in manifest: {name}"); continue
        p = final / name
        if not p.exists():
            errors.append(f"missing artifact {name}"); continue
        if p.is_symlink() or not p.is_file():
            errors.append(f"non-regular/symlink artifact {name}"); continue
        data = p.read_bytes()
        if len(data) != meta.get("size"):
            errors.append(f"artifact size mismatch: {name}")
        if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
            errors.append(f"artifact SHA mismatch: {name}")
    # exact inventory: no extra files, no stray symlinks/dirs
    expected = set(inv) | RESERVED
    for p in final.rglob("*"):
        rel = p.relative_to(final).as_posix()
        if p.is_symlink():
            errors.append(f"symlink present: {rel}"); continue
        if p.is_dir():
            continue
        if rel not in expected:
            errors.append(f"unexpected file present: {rel}")
    return {"ok": not errors, "errors": errors}


def mark_interrupted(run_dir, attempt_id: str) -> Path:
    """Preserve a crashed/interrupted staging as .interrupted (never auto-retry)."""
    st = staging_dir(run_dir, attempt_id)
    dst = interrupted_dir(run_dir, attempt_id)
    if st.exists():
        os.replace(st, dst)
        _fsync_dir(Path(run_dir))
    return dst


def write_failure_ledger(run_dir, attempt_id: str, failures: list) -> Path:
    d = failed_dir(run_dir, attempt_id)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "failure_ledger.json"
    tmp = out.with_suffix(".json.tmp")
    _write_fsync(tmp, json.dumps({"attempt_id": attempt_id, "failures": failures,
                                  "utc": utc_now()}, indent=2, sort_keys=True))
    os.replace(tmp, out)
    _fsync_dir(d)
    return out
