"""G0C minimal-system MSF runner (v2). Uses ONLY smooth_square_gamma_v2 (correct
anti-phase channels) and the transverse Lyapunov exponent along the synchronized
trajectory. Prerequisite: channels must be anti-phase, else EXECUTION_INVALID.

Import-safe; full run gated by the execution contract."""
from __future__ import annotations

import sys

import numpy as np

from _contract_v2 import failure_record, provenance, run_cli
from src.dynamics.fhn import FHNParams
from src.dynamics.msf_switching import smooth_square_gamma_v2
from src.metrics.lyapunov import transverse_lyapunov

GATE = "G0C_msf_minimal"
REPORT = "g0c_msf_v2.json"
SCOPE = "individual:G0C"


def _cfg(ctx):
    return ctx.execution["g0c"], ctx.prereg["seed_blocks"]["g0c_msf"], ctx.prereg["global"]["dt"]


def plan(ctx):
    g, seeds, dt = _cfg(ctx)
    n = len(g["sigma_grid"]) * len(g["T_swt_grid"])
    return {"gate": GATE, "grid_points": n, "seeds": seeds,
            "params": {k: g[k] for k in ("N", "lam_perp", "alpha", "n_steps",
                                         "sigma_grid", "T_swt_grid")},
            "projected_cost": f"{n} transverse-Lyapunov integrations of {g['n_steps']} "
                              f"steps on a {2*g['N']}-dim system; seconds each."}


def _prereq_antiphase(N, T_swt, dt):
    gof = smooth_square_gamma_v2(N, T_swt, dt)
    v = np.array([gof(s) for s in range(0, int(4 * T_swt / dt), max(1, int(T_swt / dt / 8)))])
    return float(np.max(np.abs(v[:, 0] - v[:, 1])))


def compute(ctx):
    g, seeds, dt = _cfg(ctx)
    N = g["N"]
    seed = seeds[0]
    # prerequisite: channels genuinely anti-phase for every T_swt. A TECHNICAL
    # failure of the prerequisite computation (contract H) emits a full failure
    # record; a computed deviation < 0.5 is a genuine prereq-not-met (PREREQ_FAIL).
    for T_swt in g["T_swt_grid"]:
        try:
            deviation = _prereq_antiphase(N, T_swt, dt)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                    "provenance": provenance(ctx, seeds, g,
                                             "MSF anti-phase prerequisite computation failed "
                                             "technically => EXECUTION_INVALID with a full "
                                             "failure record",
                                             reason_code="PREREQ_FAIL",
                                             failures=[failure_record(e, seed,
                                                       {"phase": "prereq", "T_swt": T_swt})]),
                    "result": {"failed_at": {"phase": "prereq", "T_swt": T_swt}}}
        if deviation < 0.5:
            return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                    "provenance": provenance(ctx, seeds, g,
                                             "prerequisite: MSF channels must be anti-phase",
                                             reason_code="PREREQ_FAIL"),
                    "result": {"reason": f"channels not anti-phase at T_swt={T_swt}",
                               "max_channel_deviation": deviation}}

    grid = {}
    for T_swt in g["T_swt_grid"]:
        gof = smooth_square_gamma_v2(N, T_swt, dt, g["alpha"])
        row = {}
        for sigma in g["sigma_grid"]:
            # single-seed gate: a technical failure OR a nonfinite Psi both yield
            # EXECUTION_INVALID WITH a full failure record (contract H). The nonfinite
            # check is inside the try so it flows through the same record path.
            try:
                p = FHNParams(N=N, sigma_inter=sigma)
                x0 = np.random.default_rng(seed).uniform(-2, 2, size=2 * N)
                psi = transverse_lyapunov(p, g["lam_perp"], gof, x0, dt=dt,
                                          n_steps=g["n_steps"], renorm_every=g["renorm_every"],
                                          transient_steps=g["transient_steps"])
                if not np.isfinite(psi):
                    raise FloatingPointError("nonfinite Psi (transverse Lyapunov)")
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                return {"gate": GATE, "verdict": "EXECUTION_INVALID",
                        "provenance": provenance(ctx, seeds, g,
                                                 "single-seed gate: any technical failure OR a "
                                                 "nonfinite Psi => EXECUTION_INVALID (frozen "
                                                 "policy), emitting a full failure record",
                                                 reason_code="FAILED_RUNS",
                                                 failures=[failure_record(e, seed,
                                                           {"sigma": sigma, "T_swt": T_swt})]),
                        "result": {"failed_at": {"sigma": sigma, "T_swt": T_swt},
                                   "psi": ("nonfinite" if isinstance(e, FloatingPointError)
                                           else "error")}}
            row[str(sigma)] = float(psi)
        grid[str(T_swt)] = row

    onset = {}
    for T in g["T_swt_grid"]:
        negs = [float(s) for s, v in grid[str(T)].items() if v < 0]
        onset[str(T)] = min(negs) if negs else None
    fastest = min(g["T_swt_grid"])
    fast_neg = onset[str(fastest)] is not None
    dependence = len({v for v in onset.values() if v is not None}) > 1
    if not fast_neg:
        verdict, reason = "FAIL", None
    elif dependence:
        verdict, reason = "PASS", None
    else:
        verdict, reason = "INCONCLUSIVE", "PARTIAL_NO_TSWT_DEPENDENCE"
    return {"gate": GATE, "verdict": verdict,
            "provenance": provenance(ctx, seeds, g,
                                     "PASS iff fast has Psi<0 region AND onset depends on T_swt; "
                                     "Psi<0 but no dependence -> INCONCLUSIVE(PARTIAL_NO_TSWT_DEPENDENCE); "
                                     "no Psi<0 -> FAIL; prereq fail -> EXECUTION_INVALID(PREREQ_FAIL)",
                                     reason_code=reason),
            "result": {"psi_grid": grid, "onset_sigma_by_Tswt": onset,
                       "boundary_depends_on_Tswt": dependence}}


if __name__ == "__main__":
    sys.exit(run_cli(GATE, __file__, plan, compute, REPORT, SCOPE))
