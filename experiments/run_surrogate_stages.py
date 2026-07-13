"""Gate G3: robustness of the fast-switching contraction advantage under staged
departures from the faithful case (heterogeneity, directed, signed couplings).
Reports the stage at which the advantage over static-sparse disappears."""
from __future__ import annotations

import numpy as np

from _common import REPORT_DIR, append_registry, atomic_write_json, load_contract
from src.metrics.propagator import full_contraction_rate, ordered_product
from src.networks.switching import random_switching, static_sparse
from src.simulation.linear_surrogate import SurrogateParams, difference_step_maps
from src.validation.freeze import config_hash


def _rate(p, sched):
    maps = difference_step_maps(p, sched)
    return full_contraction_rate(ordered_product(maps), len(maps))


def run(c: dict) -> dict:
    st = c["surrogate_stages"]
    N, N_IL, H = st["N"], st["N_IL"], st["horizon_steps"]
    df, ds = st["dwell_fast"], st["dwell_slow"]
    out = {}
    for stage in st["stages"]:
        adv, gf, gs = [], [], []
        for seed in st["seeds"]:
            p = SurrogateParams(N=N, kappa=st["kappa"], rho_target=st["rho_target"],
                                intra_coupling=st["intra_coupling"],
                                heterogeneity=stage["heterogeneity"],
                                directed=stage["directed"], signed=stage["signed"],
                                seed_struct=seed)
            fast = random_switching(N, N_IL, df, H // df + 1,
                                    np.random.default_rng(seed * 10 + 1), "fast")
            stat = static_sparse(N, N_IL, H, np.random.default_rng(seed * 10 + 2),
                                 "static_sparse")
            rf, rs = _rate(p, fast), _rate(p, stat)
            gf.append(rf); gs.append(rs); adv.append(rf - rs)
        out[stage["name"]] = {
            "gamma_fast_mean": float(np.mean(gf)),
            "gamma_static_mean": float(np.mean(gs)),
            "advantage_mean": float(np.mean(adv)),
            "advantage_std": float(np.std(adv)),
        }
    return out


def evaluate(res: dict, c: dict) -> dict:
    order = [s["name"] for s in c["surrogate_stages"]["stages"]]
    surviving = [n for n in order if res[n]["advantage_mean"] > 0]
    faithful_ok = res["faithful"]["advantage_mean"] > 0
    mild_ok = res.get("mild_heterogeneity", {}).get("advantage_mean", -1) > 0
    verdict = "PASS" if (faithful_ok and mild_ok) else "LIMITED"
    first_fail = next((n for n in order if res[n]["advantage_mean"] <= 0), None)
    return {"verdict": verdict, "stages_with_advantage": surviving,
            "first_stage_without_advantage": first_fail,
            "note": "advantage = gamma_fast - gamma_static (>0 means switching helps)"}


def main() -> None:
    c = load_contract()
    h = config_hash(c)
    res = run(c)
    ev = evaluate(res, c)
    result = {"experiment": "surrogate_stages_g3", "config_hash": h,
              "results": res, "evaluation": ev, "gate": "G3",
              "verdict": ev["verdict"], "summary": str(ev)}
    out = REPORT_DIR / "surrogate_stages_g3.json"
    atomic_write_json(out, result)
    append_registry({"experiment": "surrogate_stages_g3", "config_hash": h,
                     "result_file": str(out.relative_to(out.parents[2])),
                     "gate": "G3", "verdict": ev["verdict"], "summary": str(ev)})
    for name, v in res.items():
        print(f"  {name:22s} fast={v['gamma_fast_mean']:+.4f} "
              f"static={v['gamma_static_mean']:+.4f} adv={v['advantage_mean']:+.4f}")
    print(f"G3 verdict: {ev}")


if __name__ == "__main__":
    main()
