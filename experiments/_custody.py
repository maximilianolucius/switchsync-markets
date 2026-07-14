"""Durable checkpoint ledger + immutable attempt publication.

CheckpointLedger (contract F): append-only JSONL with a per-record hash chain:
  {"seq": n, "prev_record_hash": h_{n-1}, "cell": {...}, "result": {...},
   "provenance_key": pk, "record_hash": sha256(canonical(body))}
On load it verifies: strictly sequential seq (no gaps), an unbroken prev/record
hash chain (detects reordering and changed results), no duplicate cell UIDs, and
matching provenance. A truncated/corrupt LAST line raises TruncatedTail: it is
corruption, detected and PRESERVED as evidence, never silently deleted and never a
resume input. allow_truncated_tail=True loads the valid prefix READ-ONLY for
evidence inspection (an immutable .truncated snapshot is written, the live file is
left untouched, and no further append is permitted); a truncated ledger is never
continued. Corruption anywhere else raises CheckpointCorrupt.

Attempt publication (contracts B/C/D): each authorized attempt owns
  <run-dir>/<attempt_id>.staging/      work in progress (flock-held)
  <run-dir>/<attempt_id>.failed/       failure ledger (no success bundle)
  <run-dir>/<attempt_id>.interrupted/  preserved staging (terminal; never resumed)
  <run-dir>/<attempt_id>.invalid/      exceptional post-rename verify failure (terminal)
  <run-dir>/<attempt_id>/              final, immutable, SEALED
Publication inventories staging, builds attempt_manifest.json (with its own content
hash), writes the manifest + SEALED INTO staging, fsyncs files and directory, runs a
SINGLE full validation, and ONLY if every check passes performs a SINGLE atomic
rename staging -> final (no final-without-SEAL window) followed by post-rename
re-verification. A deterministic pre-rename validation error leaves `final`
nonexistent; an exceptional post-rename failure moves final -> .invalid. A SEALED
directory refuses further writes; verify_sealed_attempt NEVER raises on a malformed
manifest. An flock on <run-dir>/<attempt_id>.lock prevents concurrent executions of
the same attempt.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

VALID_ROLES = {"report", "checkpoint", "evidence"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
        self._readonly = False
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
            # A truncated/corrupt FINAL line is corruption: detected and PRESERVED as
            # evidence, never silently deleted and never a resume input. By default
            # this raises. With allow_truncated_tail=True the valid prefix is loaded
            # READ-ONLY for evidence inspection: an immutable .truncated snapshot is
            # written, the live file is left untouched, and no further append is
            # permitted (a truncated ledger is never continued).
            if not self.allow_truncated_tail:
                raise TruncatedTail(
                    f"ledger has a truncated/corrupt final line after "
                    f"{self._next_seq} valid records; preserved as evidence (never "
                    f"resumed)", n_valid=self._next_seq)
            evidence = self.path.with_suffix(self.path.suffix + ".truncated")
            if not evidence.exists():
                evidence.write_text(raw)
                _fsync_dir(self.path.parent)
            self._readonly = True

    def has(self, cell: dict) -> bool:
        return self._cell_key(cell) in self._done

    def append(self, cell: dict, result: dict) -> None:
        if self._readonly:
            raise CheckpointCorrupt("ledger loaded READ-ONLY from a truncated tail; "
                                    "no append and no continuation (never resumed)")
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
    if not isinstance(name, str) or name in ("", ".", ".."):
        return False
    if name.startswith("/") or "/" in name or "\\" in name or ".." in Path(name).parts:
        return False
    return True


def _entry_kind(p: Path) -> str:
    """Classify a filesystem entry WITHOUT following symlinks."""
    m = os.lstat(p).st_mode
    if stat.S_ISLNK(m):
        return "symlink"
    if stat.S_ISDIR(m):
        return "dir"
    if stat.S_ISREG(m):
        return "file"
    if stat.S_ISFIFO(m):
        return "fifo"
    if stat.S_ISSOCK(m):
        return "socket"
    return "device"


def inventory_staging(staging: Path, roles: dict) -> dict:
    """Build the artifact inventory of a FLAT staging dir: every top-level entry
    must be a regular file (no subdirectories, symlinks, FIFO/socket/device),
    non-reserved, safely named, and declared in `roles`. Returns
    {name: {size, sha256, role}}."""
    staging = Path(staging)
    inv = {}
    for p in sorted(staging.iterdir()):          # top-level only => enforces flat
        rel = p.name
        kind = _entry_kind(p)
        if kind != "file":
            raise CheckpointCorrupt(f"non-regular staging entry ({kind}) refused: {rel}")
        if rel in RESERVED:
            raise CheckpointCorrupt(f"reserved name present before sealing: {rel}")
        if not _safe_relname(rel):
            raise CheckpointCorrupt(f"unsafe artifact name: {rel}")
        if rel not in roles:
            raise CheckpointCorrupt(f"unexpected (undeclared) artifact: {rel}")
        if roles[rel] not in VALID_ROLES:
            raise CheckpointCorrupt(f"invalid role {roles[rel]!r} for {rel}")
        data = p.read_bytes()
        inv[rel] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "role": roles[rel]}
    missing_roles = set(roles) - set(inv)
    if missing_roles:
        raise CheckpointCorrupt(f"declared artifacts missing from staging: {sorted(missing_roles)}")
    return inv


_MANIFEST_FIELDS = {
    "campaign_id": str, "attempt_id": str, "execution_scope": str, "hashes": dict,
    "head": str, "tag": str, "structured_command": dict, "runner_shas": dict,
    "orchestrator_sha256": (str, type(None)), "authorization_token_sha256": str,
    "started_utc": str, "ended_utc": str, "exit_status": int, "artifacts": dict,
    "gate_verdicts": dict, "environment": dict, "state": str,
    "manifest_content_hash": str,
}


def validate_manifest_and_staging(staging: Path, manifest) -> list:
    """SINGLE pre-rename validation (contract B/C). Returns a list of error
    strings (empty == valid). Never raises on a malformed manifest."""
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest is not a dict"]
    for f, typ in _MANIFEST_FIELDS.items():
        if f not in manifest:
            errors.append(f"missing manifest field: {f}")
        elif not isinstance(manifest[f], typ):
            errors.append(f"manifest field {f} has wrong type")
    if errors:
        return errors
    # recomputed content hash
    body = {k: v for k, v in manifest.items() if k != "manifest_content_hash"}
    if _sha(_canonical(body)) != manifest["manifest_content_hash"]:
        errors.append("manifest content hash mismatch")
    # coherent identifiers
    for f in ("campaign_id", "attempt_id", "execution_scope", "authorization_token_sha256"):
        if not manifest[f]:
            errors.append(f"empty {f}")
    # artifact metadata exactness
    inv = manifest["artifacts"]
    for name, meta in inv.items():
        if not _safe_relname(name) or name in RESERVED:
            errors.append(f"unsafe/reserved artifact name in manifest: {name}"); continue
        if not isinstance(meta, dict) or {"size", "sha256", "role"} - set(meta):
            errors.append(f"artifact {name} metadata incomplete"); continue
        if not isinstance(meta["size"], int) or meta["size"] < 0:
            errors.append(f"artifact {name} bad size")
        if not (isinstance(meta["sha256"], str) and SHA256_RE.match(meta["sha256"])):
            errors.append(f"artifact {name} bad sha256")
        if meta["role"] not in VALID_ROLES:
            errors.append(f"artifact {name} bad role")
    # staging must be FLAT and contain EXACTLY the declared artifacts + reserved
    staging = Path(staging)
    present = {}
    for p in staging.iterdir():
        present[p.name] = _entry_kind(p)
    for name, kind in present.items():
        if kind != "file":
            errors.append(f"non-regular staging entry {name} ({kind})")
    expected = set(inv) | RESERVED
    extra = set(present) - expected
    if extra:
        errors.append(f"unexpected staging entries: {sorted(extra)}")
    missing = expected - set(present)
    if missing:
        errors.append(f"missing staging entries: {sorted(missing)}")
    # each artifact matches its inventoried size + hash
    for name, meta in inv.items():
        p = staging / name
        if present.get(name) == "file":
            data = p.read_bytes()
            if len(data) != meta.get("size"):
                errors.append(f"artifact size mismatch: {name}")
            if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
                errors.append(f"artifact hash mismatch: {name}")
    # manifest <-> SEALED consistency
    seal = staging / "SEALED"
    if present.get("SEALED") == "file":
        if seal.read_text().strip() != manifest["manifest_content_hash"]:
            errors.append("SEALED marker does not match manifest content hash")
    return errors


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


def invalid_dir(run_dir, attempt_id: str) -> Path:
    return Path(run_dir) / f"{attempt_id}.invalid"


def seal_and_publish(staging: Path, final: Path, manifest: dict) -> None:
    """Mandatory sequence (contract B): (1) staging already inventoried by caller;
    (2) manifest built; (3) write manifest + SEALED into staging; (4) fsync; (5)
    validate the FULL staging incl. manifest+SEALED via the single validator; (6)
    ONLY if all passes, a single atomic rename staging->final; (7) re-verify final.
    A deterministic pre-rename error leaves `final` nonexistent. If the exceptional
    post-rename re-verification fails, final is moved to <attempt_id>.invalid and an
    error is raised (never left as a successful attempt)."""
    staging, final = Path(staging), Path(final)
    if final.exists():
        raise FileExistsError(f"refusing to overwrite published attempt: {final}")
    _write_fsync(staging / "attempt_manifest.json",
                 json.dumps(manifest, indent=2, sort_keys=True))
    _write_fsync(staging / "SEALED",
                 (manifest.get("manifest_content_hash", "") if isinstance(manifest, dict) else "") + "\n")
    for p in staging.iterdir():
        if _entry_kind(p) == "file":
            fd = os.open(str(p), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    _fsync_dir(staging)
    errors = validate_manifest_and_staging(staging, manifest)
    if errors:
        raise CheckpointCorrupt(f"pre-rename validation failed (final NOT created): {errors}")
    os.replace(staging, final)          # single atomic publish; SEALED already inside
    _fsync_dir(final.parent)
    res = verify_sealed_attempt(final)
    if not res["ok"]:
        inv = invalid_dir(final.parent, final.name)
        try:
            os.replace(final, inv)
            _fsync_dir(final.parent)
        except OSError:
            pass
        raise CheckpointCorrupt(
            f"post-publish verification failed; moved to {inv.name}: {res['errors']}")


def verify_sealed_attempt(final: Path) -> dict:
    """Adversarially verify a sealed attempt. NEVER raises (returns ok=False with
    errors on any malformation). Rejects tampered manifest/SEALED, corrupt/missing/
    extra/wrong-size-or-hash artifact, symlink/dir/special entry, unsafe path. A
    valid attempt contains EXACTLY attempt_manifest.json, SEALED and the
    inventoried artifacts (flat)."""
    try:
        final = Path(final)
        man_p = final / "attempt_manifest.json"
        seal_p = final / "SEALED"
        if not (man_p.exists() and _entry_kind(man_p) == "file"):
            return {"ok": False, "errors": ["missing/irregular manifest"]}
        if not (seal_p.exists() and _entry_kind(seal_p) == "file"):
            return {"ok": False, "errors": ["missing/irregular SEALED marker"]}
        try:
            manifest = json.loads(man_p.read_text())
        except Exception as e:
            return {"ok": False, "errors": [f"manifest not JSON: {e}"]}
        return {"ok": (lambda es: not es)(
            _verify_final_body(final, manifest, seal_p)),
            "errors": _verify_final_body(final, manifest, seal_p)}
    except Exception as e:   # defensive: verification must never throw
        return {"ok": False, "errors": [f"verification exception: {type(e).__name__}: {e}"]}


def _verify_final_body(final: Path, manifest, seal_p: Path) -> list:
    if not isinstance(manifest, dict):
        return ["manifest is not a dict"]
    errors = []
    body = {k: v for k, v in manifest.items() if k != "manifest_content_hash"}
    mh = manifest.get("manifest_content_hash")
    if _sha(_canonical(body)) != mh:
        errors.append("manifest content hash mismatch")
    if seal_p.read_text().strip() != mh:
        errors.append("SEALED marker does not match manifest hash")
    inv = manifest.get("artifacts", {})
    if not isinstance(inv, dict):
        return errors + ["artifacts not a dict"]
    present = {}
    for p in final.iterdir():
        present[p.name] = _entry_kind(p)
    for name, kind in present.items():
        if kind != "file":
            errors.append(f"non-regular entry present: {name} ({kind})")
    for name, meta in inv.items():
        if not _safe_relname(name):
            errors.append(f"unsafe artifact name in manifest: {name}"); continue
        if present.get(name) != "file":
            errors.append(f"missing artifact {name}"); continue
        data = (final / name).read_bytes()
        if not isinstance(meta, dict) or len(data) != meta.get("size"):
            errors.append(f"artifact size mismatch: {name}")
        if hashlib.sha256(data).hexdigest() != (meta or {}).get("sha256"):
            errors.append(f"artifact SHA mismatch: {name}")
    expected = set(inv) | RESERVED
    extra = set(present) - expected
    if extra:
        errors.append(f"unexpected entries present: {sorted(extra)}")
    return errors


def mark_interrupted(run_dir, attempt_id: str) -> Path:
    """Preserve a crashed/interrupted staging as .interrupted (terminal; never
    resumed). No-op if staging is absent."""
    st = staging_dir(run_dir, attempt_id)
    dst = interrupted_dir(run_dir, attempt_id)
    if st.exists() and not dst.exists():
        os.replace(st, dst)
        _fsync_dir(Path(run_dir))
    return dst


def write_failure_ledger(run_dir, attempt_id: str, failures: list, meta=None) -> Path:
    """Atomic, NON-overwritable failure ledger (contract J). If a ledger already
    exists it writes the next numbered variant (never a secondary exception)."""
    d = failed_dir(run_dir, attempt_id)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "failure_ledger.json"
    n = 0
    while out.exists():
        n += 1
        out = d / f"failure_ledger.{n}.json"
    payload = {"attempt_id": attempt_id, "utc": utc_now(),
               "terminal_state": "FAILED", "failures": failures}
    if meta:
        payload.update(meta)
    tmp = out.with_suffix(out.suffix + ".tmp")
    _write_fsync(tmp, json.dumps(payload, indent=2, sort_keys=True))
    os.replace(tmp, out)
    _fsync_dir(d)
    return out
