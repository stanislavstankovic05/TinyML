#!/usr/bin/env python3
"""Feature-subset comparison on the FULL pipeline (prediction -> SJF decision).

For each best subset (m=2..9 from best_subsets.csv) plus the all-30 baseline:
  variant A: Tier-1 subset only
  variant B: subset + Tier-2 (burst history + memory from ONE prior run)

Tier-2 definition (leak-free):
  hist rows   = the nice0_other / argc=1 rows of labels_linux (one "first run")
  target burst= median cpu_s over ALL OTHER rows (history row excluded)
  tier2 feats = log(hist_burst), hist_maxrss_kb

Pipeline per variant: RF-300, KFold-5 out-of-fold log-burst prediction ->
SJF simulation (K=20 tasks, 3000 workloads, same RNG for fairness) ->
prediction metrics + decision metrics.

Output: dataset/subset_sjf_comparison.csv + printed table.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_predict

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
K_TASKS = 20
N_WORKLOADS = 3000


def avg_wait(bursts):
    starts = np.concatenate([[0.0], np.cumsum(bursts)[:-1]])
    return starts.mean()


def sjf_metrics(true, pred, rng):
    n = len(true)
    fifo_w, pred_w, oracle_w = [], [], []
    for _ in range(N_WORKLOADS):
        idx = rng.choice(n, size=K_TASKS, replace=False)
        tb, pb = true[idx], pred[idx]
        fifo_w.append(avg_wait(tb))
        oracle_w.append(avg_wait(tb[np.argsort(tb)]))
        pred_w.append(avg_wait(tb[np.argsort(pb)]))
    fifo, oracle, predm = map(np.mean, (fifo_w, oracle_w, pred_w))
    return (100 * (fifo - predm) / fifo,
            100 * (fifo - predm) / (fifo - oracle))


def evaluate(name, cols, df, rng_seed=0):
    X = df[cols].astype(float)
    y = np.log(df["true_burst"].clip(lower=1e-6))
    rf = RandomForestRegressor(n_estimators=300, random_state=0, n_jobs=-1)
    pred_log = cross_val_predict(rf, X, y, cv=KFold(5, shuffle=True, random_state=0))
    r2 = 1 - ((y - pred_log) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    rho = spearmanr(y, pred_log).statistic
    rng = np.random.default_rng(rng_seed)  # same workloads for every variant
    red, cap = sjf_metrics(df["true_burst"].values, np.exp(pred_log), rng)
    return {"variant": name, "n_feats": len(cols), "R2": round(r2, 3),
            "spearman": round(rho, 3), "wait_cut_vs_fifo_%": round(red, 1),
            "oracle_captured_%": round(cap, 1)}


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features_linux.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_linux.csv")
    subs = pd.read_csv(ROOT / "dataset" / "best_subsets.csv")

    # --- leak-free split: history row vs target rows ---------------------
    hist = (lab[(lab.sched_grid == "nice0_other") & (lab.argc == 1)]
            .set_index("id")[["cpu_s_median", "maxrss_kb"]]
            .rename(columns={"cpu_s_median": "hist_burst",
                             "maxrss_kb": "hist_maxrss"}))
    target = (lab[~((lab.sched_grid == "nice0_other") & (lab.argc == 1))]
              .groupby("id")["cpu_s_median"].median().rename("true_burst"))
    df = feat.merge(target, on="id").merge(hist, on="id")
    df["hist_burst_log"] = np.log(df["hist_burst"].clip(lower=1e-6))

    tier1_all = [c for c in feat.columns if c not in ("id", "source")]
    tier2 = ["hist_burst_log", "hist_maxrss"]

    rows = []
    # baseline: all 30, with and without tier 2
    rows.append(evaluate("all30", tier1_all, df))
    rows.append(evaluate("all30+T2", tier1_all + tier2, df))
    # each best subset, with and without tier 2
    for _, r in subs.iterrows():
        cols = [c.strip() for c in r["subset"].split(",")]
        rows.append(evaluate("best%d" % r["m"], cols, df))
        rows.append(evaluate("best%d+T2" % r["m"], cols + tier2, df))
    # tier-2 alone (the classic history-only scheduler baseline)
    rows.append(evaluate("T2only", tier2, df))

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "dataset" / "subset_sjf_comparison.csv", index=False)
    print("=== subset comparison: prediction quality AND SJF decision quality ===")
    print("(K=%d tasks/workload, %d workloads, identical workload draws)\n"
          % (K_TASKS, N_WORKLOADS))
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
