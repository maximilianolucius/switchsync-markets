import numpy as np
import pytest

from src.dynamics.fhn import (
    FHNParams,
    build_const_operator,
    build_inter_operator,
    gamma_from_pairs,
    single_layer_jacobian,
    single_layer_operator,
)
from src.networks.ring import ring_laplacian
from src.validation.checks import assert_zero_row_sum


def test_ring_zero_row_sum_and_symmetric():
    L = ring_laplacian(10, radius=1)
    assert_zero_row_sum(L)
    assert np.allclose(L, L.T)
    assert L[0, 1] == 1 and L[0, -1] == 1 and L[0, 0] == -2


def test_ring_rejects_small_N():
    # N=2 is valid (minimal MSF system); N<2 is not.
    with pytest.raises(ValueError):
        ring_laplacian(1)
    L2 = ring_laplacian(2)
    assert L2.shape == (2, 2)
    assert np.allclose(L2, [[-1, 1], [1, -1]])


def test_const_operator_shape_and_block_structure():
    p = FHNParams(N=6)
    A = build_const_operator(p)
    assert A.shape == (24, 24)
    # two identical layer blocks
    assert np.allclose(A[:12, :12], A[12:, 12:])
    # blocks are decoupled in the constant (no inter-layer) part
    assert np.allclose(A[:12, 12:], 0.0)


def test_inter_operator_diffusive_and_activator_only():
    p = FHNParams(N=6, sigma_inter=0.7)
    gamma = gamma_from_pairs(6, [2])
    A = build_inter_operator(p, gamma)
    # activator of node 2: layer1 idx 4, layer2 idx 12+4=16
    assert A[4, 4] == pytest.approx(-0.7)
    assert A[4, 16] == pytest.approx(0.7)
    assert A[16, 16] == pytest.approx(-0.7)
    assert A[16, 4] == pytest.approx(0.7)
    # row sums over the coupled activators are zero (diffusive)
    assert A[4].sum() == pytest.approx(0.0)
    # inhibitors are never inter-layer coupled
    assert np.allclose(A[5], 0.0)


def test_inter_operator_rejects_bad_gamma():
    p = FHNParams(N=6)
    with pytest.raises(ValueError):
        build_inter_operator(p, np.ones(5))


def test_jacobian_matches_operator_at_zero_u():
    # at u=0 the nonlinear derivative (1/eps)(1-u^2) equals the linear (1/eps),
    # so the Jacobian equals the constant single-layer operator.
    p = FHNParams(N=6)
    M = single_layer_operator(p)
    x = np.zeros(12)
    J = single_layer_jacobian(x, p, M)
    assert np.allclose(J, M)
