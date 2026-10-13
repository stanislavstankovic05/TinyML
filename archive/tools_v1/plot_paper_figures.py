#!/usr/bin/env python3
"""Three new figures for the LaTeX paper, built from the CSVs already saved
by earlier experiments (no re-training). Avoids dual-axis charts (two
separate panels instead) and uses a fixed, small categorical palette.

Output: dataset/plots/depth_sweep.png, subset_sweep.png, model_comparison.png
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
PLOTS = ROOT / "dataset" / "plots"
PLOTS.mkdir(exist_ok=True)

BLUE, ORANGE, GRAY = "#0072B2", "#E69F00", "#888888"

def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

# ---- 1) Depth sweep: two panels, oracle% and cost, sharing x -------------
d = pd.read_csv(ROOT / "dataset" / "rf_depth_finesweep.csv", keep_default_na=False)
d["depth_num"] = d["max_depth"].apply(lambda x: 22 if x == "None" else int(x))
d = d.sort_values("depth_num")
xt = [str(v) if v != 22 else "nelim." for v in d["depth_num"]]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
ax1.plot(range(len(d)), d["oracle_%"], color=BLUE, linewidth=2, marker="o", markersize=4, zorder=3)
best_i = d["oracle_%"].idxmax()
best_pos = d.index.get_loc(best_i)
ax1.scatter([best_pos], [d["oracle_%"].iloc[best_pos]], color=ORANGE, s=90, zorder=4,
           label="adâncime=3 (optim)")
ax1.set_xticks(range(len(d))); ax1.set_xticklabels(xt, fontsize=8)
ax1.set_xlabel("adâncime maximă"); ax1.set_ylabel("% din oracol")
ax1.set_title("Calitatea planificării vs. adâncime")
ax1.legend(frameon=False, fontsize=8, loc="lower right")
style(ax1)

ax2.plot(range(len(d)), d["est_ops"], color=GRAY, linewidth=2, marker="o", markersize=4, zorder=3)
ax2.scatter([best_pos], [d["est_ops"].iloc[best_pos]], color=ORANGE, s=90, zorder=4)
ax2.set_xticks(range(len(d))); ax2.set_xticklabels(xt, fontsize=8)
ax2.set_xlabel("adâncime maximă"); ax2.set_ylabel("operații / predicție (estimat)")
ax2.set_title("Cost de inferență vs. adâncime")
style(ax2)

fig.tight_layout()
fig.savefig(PLOTS / "depth_sweep.png", dpi=180)
print("wrote depth_sweep.png")

# ---- 2) Subset-size sweep: RF vs ExtraTrees, oracle% vs m -----------------
s = pd.read_csv(ROOT / "dataset" / "rf_vs_extratrees_by_subset.csv")
order = [f"best{m}" for m in range(2, 10)] + ["all30"]
piv = s.pivot(index="subset", columns="model", values="oracle_%").reindex(order)
xlabels = [o.replace("best", "").replace("all30", "toate\n30") for o in order]

fig, ax = plt.subplots(figsize=(7.5, 4))
ax.plot(range(len(piv)), piv["RandomForest(100,depth=4)"], color=BLUE, linewidth=2,
        marker="o", markersize=5, label="Random Forest", zorder=3)
ax.plot(range(len(piv)), piv["ExtraTrees(100,depth=6)"], color=ORANGE, linewidth=2,
        marker="s", markersize=5, label="Extra Trees", zorder=3)
ax.axvline(5, color="#cccccc", linewidth=1, linestyle="--", zorder=1)  # m=7 index
ax.text(5.1, 60, "salt la m=7", fontsize=8, color="#888888")
ax.set_xticks(range(len(piv))); ax.set_xticklabels(xlabels, fontsize=9)
ax.set_xlabel("mărimea subsetului de caracteristici (m)")
ax.set_ylabel("% din oracol")
ax.set_title("Calitatea planificării vs. numărul de caracteristici folosite")
ax.legend(frameon=False, fontsize=9)
style(ax)
fig.tight_layout()
fig.savefig(PLOTS / "subset_sweep.png", dpi=180)
print("wrote subset_sweep.png")

# ---- 3) Model family comparison: horizontal bars, sorted -----------------
m = pd.read_csv(ROOT / "dataset" / "final_model_summary.csv").sort_values("oracle_%_mean")
colors = [BLUE if i >= len(m) - 2 else GRAY for i in range(len(m))]  # highlight top-2 (tied)

fig, ax = plt.subplots(figsize=(7.5, 4.2))
bars = ax.barh(m["model"], m["oracle_%_mean"], xerr=m["oracle_%_std"],
               color=colors, height=0.6, error_kw={"linewidth": 1, "ecolor": "#555555"}, zorder=3)
ax.set_xlabel("% din oracol (medie ± deviație standard, 5 rulări)")
ax.set_title("Compararea familiilor de modele")
ax.tick_params(axis="y", labelsize=9)
style(ax)
ax.grid(axis="x", color="#dddddd", linewidth=0.6, zorder=0)
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(PLOTS / "model_comparison.png", dpi=180)
print("wrote model_comparison.png")
