import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


class SjfSimulator:
    SIZES = [5, 10, 20, 50]
    SIZE = 20

    def __init__(self, results, draws=3000, seed=0):
        self.results = Path(results)
        self.draws = draws
        self.seed = seed

    def available(self):
        return sorted(path.parent.name for path in self.results.glob("*/predictions.csv"))

    def draw(self, programs, size):
        generator = np.random.default_rng(self.seed)
        return np.argsort(generator.random((self.draws, programs)), axis=1)[:, :size]

    def wait(self, bursts):
        return (np.cumsum(bursts, axis=1) - bursts).mean()

    def simulate(self, true, predicted, size):
        chosen = self.draw(len(true), size)
        arrival = true[chosen]
        order = np.argsort(predicted[chosen], axis=1, kind="stable")
        fifo = self.wait(arrival)
        model = self.wait(np.take_along_axis(arrival, order, axis=1))
        oracle = self.wait(np.sort(arrival, axis=1))
        return {
            "wait_fifo": fifo,
            "wait_model": model,
            "wait_oracle": oracle,
            "wait_cut_pct": 100 * (fifo - model) / fifo,
            "oracle_pct": 100 * (fifo - model) / (fifo - oracle),
        }

    def average(self, predictions, size):
        runs = pd.DataFrame([
            self.simulate(run["true_burst"].to_numpy(), run["pred_burst"].to_numpy(), size)
            for _, run in predictions.groupby("seed")
        ])
        return {**runs.mean().to_dict(), "oracle_pct_std": runs["oracle_pct"].std()}

    def load(self, model):
        folder = self.results / model
        config = json.loads((folder / "config.json").read_text())
        predictions = pd.read_csv(folder / "predictions.csv")
        chosen = (predictions["feature_set"] == config["primary"]) & (predictions["config"] == "default")
        return predictions, predictions[chosen]

    def by_workload(self, default):
        return pd.DataFrame([{"workload_size": size, **self.average(default, size)} for size in self.SIZES])

    def by_configuration(self, predictions):
        rows = []
        for (feature_set, config), runs in predictions.groupby(["feature_set", "config"], sort=False):
            rows.append({"feature_set": feature_set, "config": config, **self.average(runs, self.SIZE)})
        return pd.DataFrame(rows)

    def run(self, models):
        rows = []
        for model in models:
            predictions, default = self.load(model)
            workloads = self.by_workload(default)
            workloads.round(6).to_csv(self.results / model / "sjf_workloads.csv", index=False)
            self.by_configuration(predictions).round(6).to_csv(
                self.results / model / "sjf_configurations.csv", index=False
            )
            rows.append({"model": model, **self.average(default, self.SIZE)})
            print(model)
            print(workloads.round(6).to_string(index=False))
        table = pd.DataFrame(rows).sort_values("oracle_pct", ascending=False)
        table.round(6).to_csv(self.results / "sjf_models.csv", index=False)
        print(table[["model", "wait_cut_pct", "oracle_pct", "oracle_pct_std"]].round(2).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: sjf_simulator.py <results folder> [model ...]")
    simulator = SjfSimulator(sys.argv[1])
    simulator.run(sys.argv[2:] or simulator.available())
