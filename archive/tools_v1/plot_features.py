#!/usr/bin/env python3
"""Visual first look: each Tier-1 feature plotted against the target (burst
time), as small multiples. Look for: does the cloud of points trend up/down,
or is it flat noise? That's the visual version of the correlation script.

x-axis: log1p(feature) -- our features are non-negative counts/costs, heavily
        right-skewed; log1p spreads them out so patterns are visible.
y-axis: log(cpu_s_median) -- same target the model was trained on.

Output: dataset/plots/feature_vs_target_grid.png
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent

# colorblind-safe 2-color categorical pair, fixed assignment (never cycled)
COLORS = {"synthetic": "#0072B2", "taclebench": "#E69F00"}

DROP = {"id", "source", "argc", "cpu_s_median", "cpu_s_min", "cpu_s_max"}


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_macos.csv")
    df = lab.merge(feat, on="id", suffixes=("", "_f"))
    df["log_cpu"] = np.log(df["cpu_s_median"].clip(lower=1e-6))

    feature_cols = [c for c in feat.columns if c not in DROP and c != "id"
                    and c != "source"]

    n = len(feature_cols)
    ncols = 6
    nrows = -(-n // ncols)  # ceil
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 3.0, nrows * 2.6))
    axes = axes.flatten()

    for i, col in enumerate(feature_cols):
        ax = axes[i]
        x = np.log1p(df[col].astype(float))
        y = df["log_cpu"]
        for src, color in COLORS.items():
            m = df["source"] == src
            ax.scatter(x[m], y[m], s=6, alpha=0.35, color=color,
                       linewidths=0, label=src)
        rho = spearmanr(df[col], df["log_cpu"]).statistic
        ax.set_title("%s  (ρ=%.2f)" % (col, rho), fontsize=9)
        ax.tick_params(labelsize=7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for j in range(n, len(axes)):
        axes[j].axis("off")

    handles = [plt.Line2D([0], [0], marker="o", color="w",
               markerfacecolor=c, markersize=6, label=s)
               for s, c in COLORS.items()]
    fig.legend(handles=handles, loc="lower right", frameon=False,
               bbox_to_anchor=(0.99, 0.01))
    fig.suptitle("Each Tier-1 feature vs log(burst time) -- ρ = Spearman rank correlation",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    out_dir = ROOT / "dataset" / "plots"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "feature_vs_target_grid.png"
    fig.savefig(out, dpi=150)
    print("wrote %s (%d features, %d rows)" % (out, n, len(df)))


if __name__ == "__main__":
    main()
