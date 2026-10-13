import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


class ModelResults:
    def __init__(self, folder):
        self.name = folder.name
        self.folder = folder
        self.config = json.loads((folder / "config.json").read_text())
        summary = pd.read_csv(folder / "summary.csv")
        scheduling = pd.read_csv(folder / "sjf_configurations.csv")
        self.table = summary.merge(scheduling, on=["feature_set", "config"])

    def by_features(self):
        return self.table[self.table["config"] == "default"]

    def default(self):
        rows = self.by_features()
        return rows[rows["feature_set"] == self.config["primary"]].iloc[0]

    def by_setting(self, parameter):
        rows = self.table[self.table["feature_set"] == self.config["primary"]].set_index("config")
        chosen = self.config["settings"][parameter]
        values = self.config["grid"][parameter]
        labels = ["default" if value == chosen else f"{parameter}={value}" for value in values]
        return values, rows.loc[labels]


class ResultPlotter:
    BLUE = "#0072B2"
    GRAY = "#888888"
    PANELS = {
        "spearman": ("spearman_mean", "spearman_std", "Spearman correlation"),
        "error": ("error_pct_mean", "error_pct_std", "median error (%)"),
        "oracle": ("oracle_pct", "oracle_pct_std", "share of oracle improvement (%)"),
    }

    def __init__(self, results):
        self.results = Path(results)
        folders = sorted(path.parent for path in self.results.glob("*/sjf_configurations.csv"))
        self.models = [ModelResults(folder) for folder in folders]

    def style(self, axis, label):
        axis.set_ylabel(label)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#dddddd", linewidth=0.6)
        axis.set_axisbelow(True)

    def line(self, axis, labels, rows, panel, color=None, name=None):
        mean, deviation, label = self.PANELS[panel]
        positions = range(len(labels))
        axis.errorbar(positions, rows[mean], yerr=rows[deviation], color=color or self.BLUE, marker="o",
                      markersize=4, linewidth=1.8, capsize=2, label=name)
        axis.set_xticks(positions)
        axis.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        self.style(axis, label)

    def plot_features(self, model):
        rows = model.by_features()
        figure, axes = plt.subplots(1, 3, figsize=(15, 4))
        for axis, panel in zip(axes, self.PANELS):
            self.line(axis, list(rows["feature_set"]), rows, panel)
        figure.suptitle(f"{model.name}: results by feature set")
        figure.tight_layout()
        figure.savefig(model.folder / "by_features.png", dpi=150)
        plt.close(figure)

    def plot_settings(self, model):
        parameters = list(model.config["grid"])
        if not model.config["sweep"] or not parameters:
            return
        figure, axes = plt.subplots(len(parameters), 2, figsize=(11, 3.6 * len(parameters)), squeeze=False)
        for row, parameter in zip(axes, parameters):
            values, rows = model.by_setting(parameter)
            for axis, panel in zip(row, ["spearman", "oracle"]):
                self.line(axis, values, rows, panel)
                axis.set_xlabel(parameter)
        figure.suptitle(f"{model.name}: results by setting ({model.config['primary']})")
        figure.tight_layout()
        figure.savefig(model.folder / "by_settings.png", dpi=150)
        plt.close(figure)

    def plot_models(self):
        table = pd.DataFrame([{"model": model.name, **model.default()} for model in self.models])
        table = table.sort_values("oracle_pct")
        best = table["oracle_pct"].max()
        colors = [self.BLUE if value == best else self.GRAY for value in table["oracle_pct"]]
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.2))
        for axis, panel in zip(axes, ["spearman", "oracle"]):
            mean, deviation, label = self.PANELS[panel]
            axis.barh(table["model"], table[mean], xerr=table[deviation], color=colors, height=0.6)
            axis.set_xlabel(label)
            axis.spines[["top", "right"]].set_visible(False)
        figure.suptitle("Models at their default configuration")
        figure.tight_layout()
        figure.savefig(self.results / "model_comparison.png", dpi=150)
        plt.close(figure)

    def plot_feature_comparison(self):
        figure, axes = plt.subplots(1, 2, figsize=(14, 4.5))
        palette = plt.get_cmap("tab10")
        for index, model in enumerate(self.models):
            rows = model.by_features()
            for axis, panel in zip(axes, ["spearman", "oracle"]):
                self.line(axis, list(rows["feature_set"]), rows, panel, palette(index), model.name)
        axes[0].legend(frameon=False, fontsize=8)
        figure.suptitle("Models by feature set")
        figure.tight_layout()
        figure.savefig(self.results / "feature_comparison.png", dpi=150)
        plt.close(figure)

    def run(self):
        for model in self.models:
            self.plot_features(model)
            self.plot_settings(model)
        self.plot_models()
        self.plot_feature_comparison()
        print(f"wrote plots for {len(self.models)} models to {self.results}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: plot_results.py <results folder>")
    ResultPlotter(sys.argv[1]).run()
