"""Shared helpers for experiment runners: paths, config loading, atomic writes,
registry appends. Importing this module runs nothing."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np


def to_native(obj):
    """Recursively convert numpy scalar/array types to JSON-native Python types."""
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return to_native(obj.tolist())
    return obj

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "experiments" / "configs"
REPORT_DIR = REPO_ROOT / "experiments" / "reports"
REGISTRY = REPO_ROOT / "experiments" / "registry.csv"

import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_contract(name: str = "synthetic_prereg_v1.json") -> dict:
    with open(CONFIG_DIR / name) as fh:
        return json.load(fh)


def atomic_write_json(path: Path, obj: dict) -> None:
    """Write JSON atomically; REFUSE to overwrite an existing result (brief:
    'No sobrescribir resultados existentes')."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"result already exists, refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w") as fh:
            json.dump(to_native(obj), fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def append_registry(row: dict) -> None:
    fields = ["experiment", "config_hash", "result_file", "gate", "verdict", "summary"]
    exists = REGISTRY.exists()
    with open(REGISTRY, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})
