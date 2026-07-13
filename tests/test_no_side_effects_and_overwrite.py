"""No module executes experiments on import; results are never silently
overwritten."""
import importlib

import pytest


def test_modules_have_no_import_side_effects():
    # importing any src module must not run experiments or print/integrate.
    for mod in [
        "src.dynamics.fhn",
        "src.networks.ring",
        "src.networks.switching",
        "src.networks.temporal_metrics",
        "src.metrics.sync",
        "src.metrics.propagator",
        "src.metrics.baselines",
        "src.metrics.lyapunov",
        "src.simulation.double_layer",
        "src.simulation.linear_surrogate",
        "src.validation.checks",
        "src.validation.freeze",
    ]:
        importlib.import_module(mod)  # must not raise or run anything heavy


def test_atomic_write_refuses_overwrite(tmp_path):
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "experiments") not in sys.path:
        sys.path.insert(0, str(root / "experiments"))
    from _common import atomic_write_json

    f = tmp_path / "r.json"
    atomic_write_json(f, {"a": 1})
    with pytest.raises(FileExistsError):
        atomic_write_json(f, {"a": 2})
