"""Generate figures EXCLUSIVELY from saved artifacts in experiments/reports/.
No simulation is run here (brief: 'Figuras generadas exclusivamente desde
artefactos guardados'). Missing reports are skipped with a note."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _common import REPORT_DIR, REPO_ROOT

FIG_DIR = REPO_ROOT / "artifacts" / "figures"


def _load(name):
    p = REPORT_DIR / name
    if not p.exists():
        print(f"  (skip) {name} not found")
        return None
    return json.loads(p.read_text())


def fig_reproduction():
    d = _load("reproduction_g0.json")
    if not d:
        return
    rows = d["reproduction"]["rows"]
    T = [r["T_swt"] for r in rows]
    frac = [r["frac_synced"] for r in rows]
    e12 = [r["mean_tail_E12"] for r in rows]
    fig, ax1 = plt.subplots(figsize=(6, 4))
    ax1.semilogx(T, frac, "o-", color="C0", label="fraction synced")
    ax1.set_xlabel("switching time T_swt"); ax1.set_ylabel("fraction of seeds synced", color="C0")
    ax1.set_ylim(-0.05, 1.05)
    ax2 = ax1.twinx()
    ax2.semilogx(T, e12, "s--", color="C3", label="tail E12")
    ax2.set_ylabel("tail-mean E12", color="C3")
    plt.title("G0: fast switching synchronizes, slow does not (FHN, N=40)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "g0_reproduction.png", dpi=120)
    plt.close(fig); print("  wrote g0_reproduction.png")


def fig_surrogate_causal():
    d = _load("surrogate_causal_g1_g2.json")
    if not d:
        return
    agg = d["results"]["aggregate"]
    items = sorted(agg.items(), key=lambda kv: kv[1]["mean"])
    names = [k for k, _ in items]
    means = [v["mean"] for _, v in items]
    errs = [v["std"] for _, v in items]
    colors = ["C2" if "average" in n else ("C0" if n in ("fast", "shuffled_order_fast")
              else "C3" if n in ("static_sparse", "slow", "no_coupling", "repeated_subset_fast",
                                  "high_sweep_low_reach_fast") else "C1") for n in names]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(names, means, xerr=errs, color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("transverse contraction rate gamma (>0 = contracts/syncs)")
    ax.set_title("G1/G2: gamma by schedule (surrogate)\navg-graph green > fast blue; static/slow/nulls red")
    fig.tight_layout(); fig.savefig(FIG_DIR / "g1g2_surrogate_gamma.png", dpi=120)
    plt.close(fig); print("  wrote g1g2_surrogate_gamma.png")


def fig_stages():
    d = _load("surrogate_stages_g3.json")
    if not d:
        return
    res = d["results"]
    names = list(res.keys())
    adv = [res[n]["advantage_mean"] for n in names]
    err = [res[n]["advantage_std"] for n in names]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(names, adv, yerr=err, color=["C0" if a > 0 else "C3" for a in adv])
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("advantage gamma_fast - gamma_static")
    ax.set_title("G3: switching advantage over static across stress stages")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout(); fig.savefig(FIG_DIR / "g3_stages.png", dpi=120)
    plt.close(fig); print("  wrote g3_stages.png")


def fig_identifiability():
    d = _load("identifiability_g4.json")
    if not d:
        return
    res = d["results"]
    variants = list(res.keys())
    x = range(len(variants))
    bp = [res[v]["basis_precision"] for v in variants]
    lp = [res[v]["levelcorr_precision"] for v in variants]
    fig, ax = plt.subplots(figsize=(6, 4))
    w = 0.35
    ax.bar([i - w / 2 for i in x], bp, w, label="basis (factor-free)", color="C0")
    ax.bar([i + w / 2 for i in x], lp, w, label="level-corr (factor-confounded)", color="C3")
    ax.axhline(0.25, color="k", ls=":", label="base rate 0.25")
    ax.axhline(0.6, color="C2", ls="--", label="acceptance 0.6")
    ax.set_xticks(list(x)); ax.set_xticklabels(variants)
    ax.set_ylabel("precision"); ax.legend(fontsize=8)
    ax.set_title("G4: switching only weakly identifiable (FAIL)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "g4_identifiability.png", dpi=120)
    plt.close(fig); print("  wrote g4_identifiability.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig_reproduction()
    fig_surrogate_causal()
    fig_stages()
    fig_identifiability()
    print(f"figures in {FIG_DIR}")


if __name__ == "__main__":
    main()
