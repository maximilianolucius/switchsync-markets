"""Dimension / finiteness / stability guards. Fail loud, fail early."""
from __future__ import annotations

import numpy as np


def assert_finite(x: np.ndarray, name: str = "array") -> None:
    if not np.all(np.isfinite(x)):
        n_bad = int(np.sum(~np.isfinite(x)))
        raise FloatingPointError(f"{name} has {n_bad} non-finite entries")


def assert_shape(x: np.ndarray, shape: tuple, name: str = "array") -> None:
    if x.shape != shape:
        raise ValueError(f"{name} expected shape {shape}, got {x.shape}")


def assert_symmetric(M: np.ndarray, tol: float = 1e-10, name: str = "matrix") -> None:
    if not np.allclose(M, M.T, atol=tol):
        raise ValueError(f"{name} is not symmetric within {tol}")


def assert_zero_row_sum(L: np.ndarray, tol: float = 1e-10, name: str = "Laplacian") -> None:
    rs = np.abs(L.sum(axis=1))
    if np.max(rs) > tol:
        raise ValueError(f"{name} row sums not zero (max {np.max(rs):.2e})")
