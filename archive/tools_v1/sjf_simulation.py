#!/usr/bin/env python3
"""SJF scheduling simulation: does Tier-1 burst prediction actually improve
scheduling, or is it just an accurate number that changes no decisions?

This closes the loop flagged all along (LRB "good decision ratio"): a better
prediction is worthless unless it changes the scheduler's choice for the
better. We measure that directly.

Setup (classic single-CPU, non-preemptive, all tasks ready at t=0):
  - true burst  = measured cpu_s (uncontended Linux, intrinsic work)
  - pred burst  = Tier-1 RF model, OUT-OF-FOLD (each program predicted by a
                  model that never trained on it -- honest cold-start)
  - workload    = random sample of K programs; we sweep K
  - schedulers  : FIFO (arrival), RANDOM, SJF-oracle (sort by true burst),
                  SJF-pred (sort by predicted burst)
  - metric      : average waiting time per task (SJF provably minimizes it)

Headline numbers:
  - % waiting-time reduction of SJF-pred vs FIFO   (did prediction help?)
  - fraction of the oracle's improvement captured  (how close to ideal?)
Output: dataset/sjf_results.csv + printed summary.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_predict

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
RNG = np.random.default_rng(0)
WORKLOAD_SIZES = [5, 10, 20, 50]
N_WORKLOADS = 3000


def avg_wait(bursts_in_run_order):
    """Non-preemptive single CPU, all ready at t=0: task k waits for the sum
    of all bursts scheduled before it. Return mean waiting time."""
    starts = np.concatenate([[0.0], np.cumsum(bursts_in_run_order)[:-1]])
    return starts.mean()


def main():
    feat = pd.read_csv(ROOT / "dataset" / "features_linux.csv")
    lab = pd.read_csv(ROOT / "dataset" / "labels_linux.csv")

    # one canonical burst per program = median cpu_s over all its runs
    burst = lab.groupby("id")["cpu_s_median"].median().rename("true_burst")
    df = feat.merge(burst, on="id")
    feat_cols = [c for c in feat.columns if c not in ("id", "source")]
    X = df[feat_cols].astype(float)
    y = np.log(df["true_burst"].clip(lower=1e-6))

    # out-of-fold predictions: honest (each program predicted by a model that
    # didn't see it). One row per program -> plain KFold is leak-free.
    rf = RandomForestRegressor(n_estimators=300, random_state=0, n_jobs=-1)
    y_pred_log = cross_val_predict(rf, X, y, cv=KFold(5, shuffle=True,
                                                      random_state=0))
    df["pred_burst"] = np.exp(y_pred_log)

    true = df["true_burst"].values
    pred = df["pred_burst"].values
    n = len(df)

    rows = []
    for K in WORKLOAD_SIZES:
        acc = {k: [] for k in ["fifo", "random", "sjf_oracle", "sjf_pred"]}
        good_decisions = 0
        for _ in range(N_WORKLOADS):
            idx = RNG.choice(n, size=K, replace=False)
            tb, pb = true[idx], pred[idx]

            # FIFO = arrival order (the random sample order itself)
            acc["fifo"].append(avg_wait(tb))
            # RANDOM = an independent shuffle
            acc["random"].append(avg_wait(tb[RNG.permutation(K)]))
            # SJF-oracle = ascending TRUE burst
            acc["sjf_oracle"].append(avg_wait(tb[np.argsort(tb)]))
            # SJF-pred = ascending PREDICTED burst, waits computed on TRUE burst
            order = np.argsort(pb)
            acc["sjf_pred"].append(avg_wait(tb[order]))
            # "good decision": did we pick the truly-shortest task to run first?
            if np.argmin(pb) == np.argmin(tb):
                good_decisions += 1

        m = {k: float(np.mean(v)) for k, v in acc.items()}
        fifo, oracle, predw = m["fifo"], m["sjf_oracle"], m["sjf_pred"]
        red_vs_fifo = (fifo - predw) / fifo
        captured = (fifo - predw) / (fifo - oracle) if fifo > oracle else float("nan")
        rows.append({
            "workload_size": K,
            "avg_wait_fifo": round(fifo, 6),
            "avg_wait_random": round(m["random"], 6),
            "avg_wait_sjf_pred": round(predw, 6),
            "avg_wait_sjf_oracle": round(oracle, 6),
            "pred_reduction_vs_fifo_%": round(100 * red_vs_fifo, 1),
            "oracle_improvement_captured_%": round(100 * captured, 1),
            "picked_true_shortest_first_%": round(100 * good_decisions / N_WORKLOADS, 1),
        })

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "dataset" / "sjf_results.csv", index=False)
    print("=== SJF simulation: does Tier-1 burst prediction improve scheduling? ===")
    print("(avg waiting time per task; lower = better; %s workloads each)\n" % N_WORKLOADS)
    print(out.to_string(index=False))
    print("\nRead: 'reduction vs FIFO' = did prediction help at all.")
    print("      'oracle captured'    = how close to the best physically possible.")
    print("      'picked true shortest'= decision-level accuracy (LRB good-decision ratio).")


if __name__ == "__main__":
    main()
