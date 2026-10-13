#!/usr/bin/env python3
"""mRMR (minimum Redundancy Maximum Relevance) greedy ranking.

Combines the two measurements already made:
  - relevance: mutual_info(feature, target)      [feature_relevance.csv]
  - redundancy: spearman correlation between features [pairwise matrix]

Greedy loop: start with the single most relevant feature. Then repeatedly
pick whichever remaining feature has the best score, where

    score(f) = relevance(f) - avg(|corr(f, s)| for s already picked)

i.e. reward usefulness, penalize looking like something we already have.
This produces a RANKING (order to add features in), not just a fixed set --
you read down the list and stop wherever your feature-count budget runs out.

Output: dataset/mrmr_ranking.csv, printed ranking with running mRMR score.
"""

import numpy as np
import pandas as pd

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
DROP = {"id", "source", "argc", "cpu_s_median", "cpu_s_min", "cpu_s_max"}


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_macos.csv")
    df = lab.merge(feat, on="id", suffixes=("", "_f"))
    df["log_cpu"] = np.log(df["cpu_s_median"].clip(lower=1e-6))

    feature_cols = [c for c in feat.columns if c not in DROP and c != "id"
                    and c != "source"]
    rel = pd.read_csv(ROOT / "dataset" / "feature_relevance.csv").set_index("feature")
    relevance = rel["mutual_info"]
    corr = df[feature_cols].corr(method="spearman").abs()

    remaining = set(feature_cols)
    selected = []
    rows = []

    # first pick: pure relevance, nothing selected yet to be redundant with
    first = relevance[list(remaining)].idxmax()
    selected.append(first)
    remaining.remove(first)
    rows.append({"rank": 1, "feature": first, "relevance": relevance[first],
                "avg_redundancy": 0.0, "mrmr_score": relevance[first]})

    while remaining:
        best_f, best_score, best_red = None, -1e9, None
        for f in remaining:
            red = corr.loc[f, selected].mean()
            score = relevance[f] - red
            if score > best_score:
                best_f, best_score, best_red = f, score, red
        selected.append(best_f)
        remaining.remove(best_f)
        rows.append({"rank": len(selected), "feature": best_f,
                    "relevance": relevance[best_f],
                    "avg_redundancy": best_red, "mrmr_score": best_score})

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "dataset" / "mrmr_ranking.csv", index=False)

    print("=== mRMR greedy ranking (best features first) ===")
    print(out.to_string(index=False, float_format=lambda x: "%.4f" % x))
    print("\nwrote dataset/mrmr_ranking.csv")


if __name__ == "__main__":
    main()
