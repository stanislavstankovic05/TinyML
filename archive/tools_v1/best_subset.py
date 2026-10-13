#!/usr/bin/env python3
"""Exhaustive best-subset search, for each m = 2..MAX_M.

Unlike the greedy mRMR ranking (which builds a set one feature at a time and
can miss the true best combination), this checks every possible combination
of m features and keeps the actual best one, scored by:

    score(S) = mean(relevance(f) for f in S) - mean(|corr(i,j)| for i<j in S)
               \\_______ D(S): average usefulness ______/   \\_ R(S): average overlap _/

Same idea as before (relevance minus redundancy), just applied to a whole set
at once instead of one feature at a time -- this is the textbook mRMR set
criterion (difference form).

Cost control: checking every combination of ALL 30 features stops being fast
once m gets large (C(30,9) = 14.3M). Past FULL_SEARCH_LIMIT combinations, we
restrict the search to the top CANDIDATE_POOL features from the earlier
greedy mRMR ranking instead of all 30 -- well justified, since a feature
ranked near the bottom (near-zero relevance AND high redundancy) essentially
never belongs in an optimal set anyway. Each switch is printed explicitly.
"""

import itertools
import math
import time

import numpy as np
import pandas as pd

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
DROP = {"id", "source", "argc", "cpu_s_median", "cpu_s_min", "cpu_s_max"}

MAX_M = 9
FULL_SEARCH_LIMIT = 3_000_000   # switch to restricted pool above this many combos
CANDIDATE_POOL = 15             # size of restricted pool once we switch


def best_subset_for_m(m, names, relevance, corr, full_n):
    n = len(names)
    best_score, best_idx = -1e9, None
    for idx in itertools.combinations(range(n), m):
        rel_mean = relevance[list(idx)].mean()
        if m > 1:
            sub = corr[np.ix_(idx, idx)]
            off_diag_sum = sub.sum() - m  # subtract the m self-correlations (=1)
            redund_mean = off_diag_sum / (m * (m - 1))
        else:
            redund_mean = 0.0
        score = rel_mean - redund_mean
        if score > best_score:
            best_score, best_idx = score, idx
    return best_score, [names[i] for i in best_idx]


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_macos.csv")
    df = lab.merge(feat, on="id", suffixes=("", "_f"))
    df["log_cpu"] = np.log(df["cpu_s_median"].clip(lower=1e-6))

    feature_cols = [c for c in feat.columns if c not in DROP and c != "id"
                    and c != "source"]
    rel_df = pd.read_csv(ROOT / "dataset" / "feature_relevance.csv").set_index("feature")
    mrmr_order = pd.read_csv(ROOT / "dataset" / "mrmr_ranking.csv")["feature"].tolist()

    corr_full_df = df[feature_cols].corr(method="spearman").abs()

    results = []
    for m in range(2, MAX_M + 1):
        n_full = len(feature_cols)
        n_combos_full = math.comb(n_full, m)

        if n_combos_full <= FULL_SEARCH_LIMIT:
            names = feature_cols
            pool_note = "full 30-feature search"
        else:
            names = mrmr_order[:CANDIDATE_POOL]
            pool_note = "restricted to top %d mRMR candidates (full search would be %s combos)" % (
                CANDIDATE_POOL, format(n_combos_full, ","))

        relevance = rel_df.loc[names, "mutual_info"].values
        corr = corr_full_df.loc[names, names].values

        n_combos_used = math.comb(len(names), m)
        t0 = time.time()
        score, subset = best_subset_for_m(m, names, relevance, corr, n_full)
        elapsed = time.time() - t0

        results.append({"m": m, "score": round(score, 4),
                        "subset": ", ".join(subset), "pool": pool_note,
                        "combos_checked": n_combos_used, "seconds": round(elapsed, 2)})
        print("m=%d  score=%.4f  [%s combos, %.2fs, %s]" %
              (m, score, format(n_combos_used, ","), elapsed, pool_note))
        print("     best subset: %s" % ", ".join(subset))

    out = pd.DataFrame(results)
    out.to_csv(ROOT / "dataset" / "best_subsets.csv", index=False)
    print("\nwrote dataset/best_subsets.csv")


if __name__ == "__main__":
    main()
