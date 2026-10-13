#!/usr/bin/env python3
"""The measurements: relevance (feature -> target) and redundancy
(feature <-> feature). This is the mRMR groundwork from features.md.

Relevance: Pearson r (linear), Spearman rho (monotonic/rank), mutual
information (any dependency, including non-monotonic) -- each feature vs
log(burst time). Sorted by MI, since that's the primary measure we agreed on.

Redundancy: Spearman correlation matrix between all feature pairs. Flags
pairs above |rho|=0.8 as redundant candidates (mRMR's penalty term made
concrete).

Output:
  dataset/feature_relevance.csv      -- one row per feature, sorted by MI
  dataset/feature_redundancy_pairs.csv -- pairs with |rho| > 0.8
  dataset/plots/feature_correlation_heatmap.png
"""

import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, spearmanr
from sklearn.feature_selection import mutual_info_regression

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
DROP = {"id", "source", "argc", "cpu_s_median", "cpu_s_min", "cpu_s_max"}
REDUNDANCY_THRESHOLD = 0.8


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_macos.csv")
    df = lab.merge(feat, on="id", suffixes=("", "_f"))
    df["log_cpu"] = np.log(df["cpu_s_median"].clip(lower=1e-6))

    feature_cols = [c for c in feat.columns if c not in DROP and c != "id"
                    and c != "source"]
    X = df[feature_cols].astype(float)
    y = df["log_cpu"].values

    # ---- relevance ------------------------------------------------------
    mi = mutual_info_regression(X, y, random_state=0)
    rows = []
    for i, col in enumerate(feature_cols):
        x = X[col].values
        x_log = np.log1p(x)  # avoids overflow on huge-range features (e.g.
                              # freq_weighted_insts ~1e12) and matches the plot
        if np.std(x) == 0:
            pear, spear = 0.0, 0.0
        else:
            # this scipy build's array-API vecdot path spuriously warns
            # "overflow" on inputs that top out at ~1e1 (verified, not real);
            # values below are unaffected
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                pear = pearsonr(x_log, y).statistic
            spear = spearmanr(x, y).statistic  # rank-based: transform-invariant
        rows.append({"feature": col, "mutual_info": round(mi[i], 4),
                     "spearman_rho": round(spear, 4),
                     "pearson_r_log1p": round(pear, 4)})
    rel = pd.DataFrame(rows).sort_values("mutual_info", ascending=False)
    rel.to_csv(ROOT / "dataset" / "feature_relevance.csv", index=False)

    print("=== RELEVANCE (feature -> burst time), sorted by mutual info ===")
    print(rel.to_string(index=False))

    # ---- redundancy -------------------------------------------------------
    corr = X.corr(method="spearman")
    pairs = []
    cols = corr.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) > REDUNDANCY_THRESHOLD:
                pairs.append({"feature_a": cols[i], "feature_b": cols[j],
                             "spearman_rho": round(r, 4)})
    red = pd.DataFrame(pairs).sort_values("spearman_rho", key=abs, ascending=False)
    red.to_csv(ROOT / "dataset" / "feature_redundancy_pairs.csv", index=False)

    print("\n=== REDUNDANCY: feature pairs with |rho| > %.1f ===" % REDUNDANCY_THRESHOLD)
    print(red.to_string(index=False) if len(red) else "(none)")

    # full per-feature ranking: for each feature, every OTHER feature ordered
    # by how correlated it is to that feature (the complete redundancy view,
    # not just the >0.8 pairs above)
    full_rows = []
    for f in cols:
        others = corr[f].drop(index=f).sort_values(key=lambda s: s.abs(),
                                                     ascending=False)
        for rank, (other, rho) in enumerate(others.items(), start=1):
            full_rows.append({"feature": f, "rank": rank,
                              "most_correlated_with": other,
                              "spearman_rho": round(rho, 4)})
    full_df = pd.DataFrame(full_rows)
    full_df.to_csv(ROOT / "dataset" / "feature_pairwise_full.csv", index=False)
    print("\nwrote dataset/feature_pairwise_full.csv (%d rows = 30 features x 29 others)"
          % len(full_df))

    # heatmap
    fig, ax = plt.subplots(figsize=(11, 10))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=90, fontsize=7)
    ax.set_yticklabels(cols, fontsize=7)
    fig.colorbar(im, ax=ax, label="Spearman rho", shrink=0.8)
    ax.set_title("Feature-feature redundancy (Spearman) -- diverging: blue=neg, red=pos, white=0")
    fig.tight_layout()
    out = ROOT / "dataset" / "plots" / "feature_correlation_heatmap.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150)
    print("\nwrote %s" % out)
    print("wrote dataset/feature_relevance.csv, dataset/feature_redundancy_pairs.csv")


if __name__ == "__main__":
    main()
