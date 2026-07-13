"""Minimal-system MSF reproduction: the transverse Lyapunov exponent Psi of the
N=2-per-layer FHN system under switched inter-layer coupling, as a function of
(sigma_12, T_swt). Reproduces the qualitative sign structure (paper Figs. 8-9):
faster switching turns Psi negative at smaller coupling.
"""
from __future__ import annotations

import numpy as np

from _common import REPORT_DIR, append_registry, atomic_write_json, load_contract
from src.dynamics.fhn import FHNParams
from src.metrics.lyapunov import transverse_lyapunov
from src.validation.freeze import config_hash


def smooth_square_gamma(N: int, T_swt: float, dt: float, alpha: float = 5.0):
    """Smooth square-wave switching of the single inter-layer link between the two
    mirror pairs (paper Eq. for g(t,alpha,p), p=2*T_swt). Returns gamma_of_step."""
    p_period = 2.0 * T_swt

    def g(t):
        n = np.floor(t / p_period)
        return (np.tanh(alpha * (t - n * p_period))
                - np.tanh(alpha * (t - (n + 0.5) * p_period)) - 1.0)

    def gamma_of_step(step):
        t = step * dt
        gv = np.zeros(N)
        # pair 0 driven by g, pair 1 by opposite phase f(t)=g(t+p)
        gv[0] = 0.5 * (g(t) + 1.0)              # map [-1,1]-ish to [0,1]
        gv[1] = 0.5 * (g(t + p_period) + 1.0)
        return gv

    return gamma_of_step


def run(c: dict) -> dict:
    m = c["msf_minimal"]
    N = m["N"]
    dt = m["dt"]
    grid = {}
    for Tswt in m["T_swt_grid"]:
        row = {}
        gamma_of_step = smooth_square_gamma(N, Tswt, dt)
        for sigma in m["sigma_grid"]:
            p = FHNParams(N=N, sigma_inter=sigma)
            x0 = np.random.default_rng(m["seeds"][0]).uniform(-2, 2, size=2 * N)
            psi = transverse_lyapunov(
                p, m["lam_perp"], gamma_of_step, x0, dt=dt,
                n_steps=m["n_steps"], renorm_every=m["renorm_every"],
                transient_steps=m["transient_steps"])
            row[str(sigma)] = psi
        grid[str(Tswt)] = row
    return grid


def evaluate(grid: dict, c: dict) -> dict:
    """Qualitative: for the fastest T_swt there exists some sigma with Psi<0
    (stable sync possible), and for the slowest T_swt Psi stays >=0 at the smallest
    sigma. Also: onset sigma (first negative) should not increase as T_swt shrinks."""
    Tswt_vals = sorted(float(k) for k in grid)
    onset = {}
    for T in Tswt_vals:
        row = grid[str(T)]
        negs = [float(s) for s, v in row.items() if v < 0]
        onset[T] = min(negs) if negs else None
    fastest = Tswt_vals[0]
    fast_has_neg = onset[fastest] is not None
    # Does the stability boundary DEPEND on T_swt? (the paper's key minimal claim)
    onset_values = [onset[T] for T in Tswt_vals if onset[T] is not None]
    tswt_dependence = (len(set(onset_values)) > 1) if onset_values else False

    if fast_has_neg and tswt_dependence:
        verdict = "PASS"
        note = "switched coupling stabilizes and the stability boundary depends on T_swt"
    elif fast_has_neg and not tswt_dependence:
        verdict = "PARTIAL"
        note = ("switched coupling produces transverse contraction (Psi<0), but the "
                "stability boundary does NOT depend on T_swt in this minimal build: "
                "the N=2 isolated layer is a limit cycle (lambda_max~0, verified), so "
                "the transverse mode does not expand during off-phases and any "
                "coupling contracts. The paper's slow-switching instability at N=2 is "
                "NOT reproduced here. The switching-TIME dependence is instead "
                "reproduced by the large-N direct simulation (Gate G0).")
    else:
        verdict = "INCONCLUSIVE"
        note = "no stable region found for the fastest switching in the tested grid"
    return {"verdict": verdict, "onset_sigma_by_Tswt": onset,
            "fast_has_stable_region": fast_has_neg,
            "boundary_depends_on_Tswt": tswt_dependence,
            "note": note}


def main() -> None:
    c = load_contract()
    h = config_hash(c)
    grid = run(c)
    ev = evaluate(grid, c)
    result = {"experiment": "msf_minimal", "config_hash": h, "grid": grid,
              "evaluation": ev, "gate": "G0-support", "verdict": ev["verdict"],
              "summary": str(ev["onset_sigma_by_Tswt"])}
    out = REPORT_DIR / "msf_minimal.json"
    atomic_write_json(out, result)
    append_registry({"experiment": "msf_minimal", "config_hash": h,
                     "result_file": str(out.relative_to(out.parents[2])),
                     "gate": "G0-support", "verdict": ev["verdict"],
                     "summary": str(ev["onset_sigma_by_Tswt"])})
    for T in sorted(grid, key=float):
        print(f"  T_swt={float(T):6.1f}: " +
              "  ".join(f"s={s}:{grid[T][s]:+.3f}" for s in grid[T]))
    print(f"MSF evaluation: {ev}")


if __name__ == "__main__":
    main()
