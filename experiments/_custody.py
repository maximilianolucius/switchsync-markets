"""Durable checkpoint + transactional publish helpers (P1.2-B, contracts G and I).

CheckpointLedger: an append-only JSONL ledger written OUTSIDE the repo. One atomic
line per completed cell (flush+fsync of file and directory), keyed by the run
provenance so foreign entries are rejected, duplicates refused, and a crash leaves
a valid prefix that is reloaded on restart. A corrupt line is detected and raised.

Transactional suite publish: write reports to a staging dir; publish to the final
run dir by atomic rename ONLY on full success; on any failure write a failure
ledger and publish no success bundle.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class CheckpointCorrupt(Exception):
    pass


def _fsync_dir(p: Path) -> None:
    fd = os.open(str(p), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class CheckpointLedger:
    """Append-only durable checkpoint of completed cells."""

    def __init__(self, path, provenance: dict, key_fields):
        self.path = Path(path)
        self.provenance = provenance
        self.key_fields = list(key_fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done = {}          # cell_key -> record
        if self.path.exists():
            self._load()

    def _cell_key(self, cell: dict) -> str:
        return "|".join(f"{k}={cell[k]}" for k in self.key_fields)

    def _load(self) -> None:
        for i, line in enumerate(self.path.read_text().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                raise CheckpointCorrupt(f"line {i} is not valid JSON: {e}")
            if "cell" not in rec or "provenance_key" not in rec:
                raise CheckpointCorrupt(f"line {i} missing required fields")
            if rec["provenance_key"] != self._provenance_key():
                raise CheckpointCorrupt(f"line {i} belongs to a different run provenance")
            self._done[self._cell_key(rec["cell"])] = rec

    def _provenance_key(self) -> str:
        return "|".join(f"{k}={self.provenance.get(k)}" for k in sorted(self.provenance))

    def has(self, cell: dict) -> bool:
        return self._cell_key(cell) in self._done

    def append(self, cell: dict, result: dict) -> None:
        key = self._cell_key(cell)
        if key in self._done:
            raise CheckpointCorrupt(f"duplicate cell refused: {key}")
        rec = {"cell": cell, "result": result, "provenance_key": self._provenance_key()}
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        _fsync_dir(self.path.parent)
        self._done[key] = rec

    def completed(self) -> list:
        return list(self._done.values())

    def n_completed(self) -> int:
        return len(self._done)


def staging_dir(run_dir: Path, run_id: str) -> Path:
    return Path(run_dir) / f"{run_id}.staging"


def final_dir(run_dir: Path, run_id: str) -> Path:
    return Path(run_dir) / run_id


def publish_atomic(staging: Path, final: Path) -> None:
    """Publish the staged bundle by atomic rename. Refuse if the final exists."""
    staging, final = Path(staging), Path(final)
    if final.exists():
        raise FileExistsError(f"refusing to overwrite published run: {final}")
    os.replace(staging, final)          # atomic within the same filesystem
    _fsync_dir(final.parent)


def write_failure_ledger(run_dir: Path, run_id: str, failures: list) -> Path:
    d = Path(run_dir) / f"{run_id}.failed"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "failure_ledger.json"
    tmp = out.with_suffix(".json.tmp")
    with open(tmp, "w") as fh:
        json.dump({"run_id": run_id, "failures": failures}, fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, out)
    _fsync_dir(d)
    return out
