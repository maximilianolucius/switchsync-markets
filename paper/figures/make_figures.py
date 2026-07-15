"""Generate the publication figures for the P1.3 arXiv paper.

Reads ONLY the frozen, committed JSON reports under
results/p1_2f_cheap_suite/1baa47da06fede2a/ (attempt 1baa47da06fede2a, freeze v8).
NO simulation is executed. Output: vector PDFs in paper/figures/.

Confirmatory quantities are drawn in blue/solid; diagnostic (NOT_INTERPRETABLE)
quantities in grey/hatched and labelled as diagnostic.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
ATT = REPO / "results" / "p1_2f_cheap_suite" / "1baa47da06fede2a"
OUT = Path(__file__).resolve().parent

plt.rcParams.update({
    "pdf.fonttype": 42,           # TrueType (arXiv-friendly, searchable)
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 150,
})

C_CONF = "#1f77b4"     # confirmatory
C_DIAG = "#7f7f7f"     # diagnostic / not interpretable
C_BAND = "#d62728"
C_OK = "#2ca02c"


def load(name):
    return json.loads((ATT / name).read_text())


# ---------------------------------------------------------------- fig 1: G0B
def fig_g0b():
    r = load("g0b_calibrated_v2.json")["result"]
    rows = sorted(r["rows"], key=lambda x: x["T_swt"])
    T = [x["T_swt"] for x in rows]
    f = [x["frac_synced"] for x in rows]
    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    ax.axvspan(min(T) * 0.8, 10, color=C_OK, alpha=0.10,
               label="fast band $T_{\\mathrm{swt}}\\leq 10$ (must sync)")
    ax.axvspan(160, max(T) * 1.25, color=C_BAND, alpha=0.08,
               label="slow band $T_{\\mathrm{swt}}\\geq 160$ (must not sync)")
    ax.axhline(0.5, ls="--", lw=0.8, c="k", alpha=0.6)
    ax.plot(T, f, "o-", c=C_CONF, ms=5, lw=1.4)
    ax.set_xscale("log")
    ax.set_xlabel("switching period $T_{\\mathrm{swt}}$")
    ax.set_ylabel("fraction of seeds synchronized")
    ax.set_ylim(-0.05, 1.08)
    ax.set_title("G0B calibrated demonstration ($\\sigma_{12}=1.5$, $N=40$): PASS\n"
                 "confirmatory; 5/5 seeds per cell, zero failures", fontsize=8.5)
    ax.legend(loc="center left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_g0b_sync_fraction.pdf")
    plt.close(fig)


# ------------------------------------------------- fig 2: G1/G2 differences
def _strip(ax, diffs, band, color, title, verdict, hatch=False):
    diffs = np.asarray(diffs)
    x = np.linspace(-0.16, 0.16, len(diffs))
    ax.axhspan(-band, band, color=C_BAND, alpha=0.10, lw=0)
    ax.axhline(0, lw=0.8, c="k", alpha=0.7)
    ax.axhline(band, ls=":", lw=0.9, c=C_BAND)
    ax.axhline(-band, ls=":", lw=0.9, c=C_BAND)
    ax.scatter(x, diffs, s=22, c=color, zorder=3,
               edgecolors="k", linewidths=0.4)
    m = diffs.mean()
    ax.hlines(m, -0.3, 0.3, color=color, lw=2.2, zorder=4)
    ax.set_xlim(-0.55, 0.55)
    ax.set_xticks([])
    ax.set_title(f"{title}\n{verdict}", fontsize=7.4)
    if hatch:
        ax.set_facecolor("#f4f4f4")


def fig_g1g2():
    r = load("g1_g2_paired_v2.json")["result"]
    w, s, o = r["G1_weak"], r["G1_strict"], r["G2_order"]
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 3.1), sharey=False)
    _strip(axes[0], w["paired_differences"], w["effect_band"], C_CONF,
           "G1-weak: $\\gamma_{\\mathrm{arm}}-\\gamma_{\\mathrm{static}}$",
           "confirmatory: INCONCLUSIVE (TIE)\n8/8 positive, $p=0.0078$; mean < band")
    _strip(axes[1], s["paired_differences"], s["effect_band"], C_DIAG,
           "G1-strict: $\\gamma_{\\mathrm{arm}}-\\max(\\gamma_{\\mathrm{avg}},\\gamma_{\\mathrm{best}})$",
           "DIAGNOSTIC (NOT_INTERPRETABLE)\n8/8 negative", hatch=True)
    _strip(axes[2], o["paired_differences"], o["effect_band"], C_DIAG,
           "G2: $\\gamma_{\\mathrm{ordered}}-\\mathrm{med}(\\gamma_{\\mathrm{perm}})$",
           "DIAGNOSTIC (NOT_INTERPRETABLE)\n$p=0.070$, not significant", hatch=True)
    axes[0].set_ylabel("paired difference (per evaluation seed)", fontsize=8)
    for ax in axes:
        ax.tick_params(axis="y", labelsize=7.5)
    # explicit margins: bbox heuristics clip the rotated ylabel / bottom spine
    fig.subplots_adjust(left=0.105, right=0.97, bottom=0.05, top=0.80, wspace=0.42)
    fig.savefig(OUT / "fig_g1g2_paired_differences.pdf")
    plt.close(fig)


# ---------------------------------------------------------- fig 3: G3 stages
def fig_g3():
    r = load("g3_robustness_v2.json")["result"]
    order = ["faithful", "mild_heterogeneity", "strong_heterogeneity",
             "directed", "signed"]
    labels = ["faithful", "mild het.", "strong het.", "directed", "signed"]
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    for i, st in enumerate(order):
        blk = r["by_stage"][st]
        d = np.asarray(blk["decision"]["paired_differences"])
        band = blk["decision"]["effect_band"]
        ax.add_patch(plt.Rectangle((i - 0.32, -band), 0.64, 2 * band,
                                   color=C_BAND, alpha=0.10, lw=0))
        ax.hlines([band, -band], i - 0.32, i + 0.32, color=C_BAND, ls=":", lw=0.9)
        x = i + np.linspace(-0.18, 0.18, len(d))
        ax.scatter(x, d, s=20, c=C_CONF, edgecolors="k", linewidths=0.4, zorder=3)
        ax.hlines(d.mean(), i - 0.28, i + 0.28, color=C_CONF, lw=2.2, zorder=4)
    ax.axhline(0, lw=0.8, c="k", alpha=0.7)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("$\\gamma_{\\mathrm{fast}}-\\gamma_{\\mathrm{static}}$ (per seed)")
    ax.set_title("G3 robustness stages: confirmatory, all INCONCLUSIVE\n"
                 "(means positive in every stage but inside each preregistered band)",
                 fontsize=8.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig_g3_stages.pdf")
    plt.close(fig)


# ------------------------------------------------------------- fig 4: G4
def fig_g4():
    r = load("g4_identifiability_v2.json")["result"]
    sync = r["by_async_variant"]["async_1_1"]
    asyn = r["by_async_variant"]["async_1_3"]
    metrics = [
        ("basis estimator\nprecision = recall", sync["basis_precision"], asyn["basis_precision"], 0.6),
        ("level-correlation\nbaseline precision", sync["levelcorr_precision"], asyn["levelcorr_precision"], None),
        ("contraction corr.\n(same realization)", sync["contraction_corr_same_realization"],
         asyn["contraction_corr_same_realization"], 0.5),
    ]
    x = np.arange(len(metrics))
    wdt = 0.34
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    b1 = ax.bar(x - wdt / 2, [m[1] for m in metrics], wdt, color=C_CONF,
                label="synchronous (1:1)")
    b2 = ax.bar(x + wdt / 2, [m[2] for m in metrics], wdt, color="#ff7f0e",
                label="asynchronous/LOCF (1:3)")
    for xi, m in zip(x, metrics):
        if m[3] is not None:
            ax.hlines(m[3], xi - 0.45, xi + 0.45, color=C_BAND, ls="--", lw=1.2)
            ax.annotate(f"bar {m[3]}", (xi + 0.30, m[3] + 0.02), fontsize=7, color=C_BAND)
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.3f}", (b.get_x() + b.get_width() / 2, b.get_height() + 0.015),
                        ha="center", fontsize=6.8)
    ax.set_xticks(x)
    ax.set_xticklabels([m[0] for m in metrics], fontsize=7.8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("value")
    ax.set_title("G4 identifiability: confirmatory, FAIL\n"
                 "precision/recall far below 0.6; asynchrony/LOCF collapses the contraction correlation",
                 fontsize=8.5)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig_g4_identifiability.pdf")
    plt.close(fig)


# ------------------------------------------------------ fig 5: gate summary
def fig_summary():
    gates = [
        ("G0A exact reproduction", "NOT_RUN", "#bdbdbd", "outside cheap-suite scope"),
        ("G0B calibrated demonstration", "PASS", C_OK, "calibrated demonstration only"),
        ("G0C minimal MSF", "INCONCLUSIVE", "#ff7f0e", "no $T_{\\mathrm{swt}}$ dependence resolved"),
        ("G1-weak switching vs static", "INCONCLUSIVE (TIE)", "#ff7f0e", "8/8 positive, below band"),
        ("G1-strict vs avg/best static", "NOT_INTERPRETABLE", C_DIAG, "diagnostic: 8/8 negative"),
        ("G2 temporal order", "NOT_INTERPRETABLE", C_DIAG, "diagnostic: not significant"),
        ("G3 robustness", "INCONCLUSIVE", "#ff7f0e", "positive but inside bands"),
        ("G4 identifiability", "FAIL", C_BAND, "P/R $\\ll$ 0.6; asynchrony collapse"),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, len(gates) - 0.5)
    for i, (name, verdict, color, note) in enumerate(reversed(gates)):
        ax.text(0.05, i, name, va="center", fontsize=8.4)
        ax.add_patch(plt.Rectangle((4.05, i - 0.30), 2.6, 0.60,
                                   facecolor=color, alpha=0.85, edgecolor="none"))
        ax.text(5.35, i, verdict, va="center", ha="center", fontsize=7.6,
                color="white", fontweight="bold")
        ax.text(6.85, i, note, va="center", fontsize=7.4, color="#444444")
    ax.axis("off")
    ax.set_title("Preregistered gate outcomes (attempt 1baa47da06fede2a, freeze v8)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_gate_summary.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_g0b()
    fig_g1g2()
    fig_g3()
    fig_g4()
    fig_summary()
    print("figures written to", OUT)
    for p in sorted(OUT.glob("*.pdf")):
        print("  ", p.name, p.stat().st_size, "bytes")
