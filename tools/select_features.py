import itertools
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.feature_selection import mutual_info_regression


class FeatureSelector:
    META = ["id", "source", "true_burst", "hist_burst", "hist_maxrss"]
    FLOOR = 1e-6
    REDUNDANT = 0.8
    CHUNK = 500_000
    COLORS = {"synthetic": "#0072B2", "taclebench": "#E69F00"}

    def __init__(self, root, dataset, largest=9):
        self.folder = Path(root) / "dataset" / dataset
        self.plots = self.folder / "plots"
        self.largest = largest
        self.table = pd.read_csv(self.folder / "training_set.csv")
        self.names = [column for column in self.table.columns if column not in self.META]
        self.features = self.table[self.names].astype(float)
        self.target = np.log(self.table["true_burst"].clip(lower=self.FLOOR))
        self.correlation = self.features.corr(method="spearman").fillna(0.0)
        self.scores = self.relevance()

    def pearson(self, values):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return pearsonr(values, self.target).statistic

    def relevance(self):
        information = mutual_info_regression(self.features, self.target, random_state=0)
        rows = []
        for name, score in zip(self.names, information):
            values = self.features[name]
            varies = values.std() > 0
            rows.append({
                "feature": name,
                "mutual_info": score,
                "spearman_rho": spearmanr(values, self.target).statistic if varies else 0.0,
                "pearson_r_log1p": self.pearson(np.log1p(values)) if varies else 0.0,
            })
        return pd.DataFrame(rows)

    def redundant_pairs(self):
        rows = []
        for first, second in itertools.combinations(self.names, 2):
            rho = self.correlation.loc[first, second]
            if abs(rho) > self.REDUNDANT:
                rows.append({"feature_a": first, "feature_b": second, "spearman_rho": rho})
        pairs = pd.DataFrame(rows, columns=["feature_a", "feature_b", "spearman_rho"])
        return pairs.sort_values("spearman_rho", key=abs, ascending=False)

    def neighbours(self):
        rows = []
        for name in self.names:
            others = self.correlation[name].drop(index=name).sort_values(key=abs, ascending=False)
            for rank, (other, rho) in enumerate(others.items(), start=1):
                rows.append({"feature": name, "rank": rank, "most_correlated_with": other, "spearman_rho": rho})
        return pd.DataFrame(rows)

    def ranking(self):
        relevance = self.scores.set_index("feature")["mutual_info"]
        overlap = self.correlation.abs()
        chosen, rows = [], []
        remaining = list(self.names)
        while remaining:
            redundancy = {name: overlap.loc[name, chosen].mean() if chosen else 0.0 for name in remaining}
            best = max(remaining, key=lambda name: relevance[name] - redundancy[name])
            rows.append({
                "rank": len(chosen) + 1,
                "feature": best,
                "relevance": relevance[best],
                "avg_redundancy": redundancy[best],
                "mrmr_score": relevance[best] - redundancy[best],
            })
            chosen.append(best)
            remaining.remove(best)
        return pd.DataFrame(rows)

    def best_subset(self, size):
        relevance = self.scores["mutual_info"].to_numpy()
        overlap = self.correlation.abs().to_numpy()
        pairs = list(itertools.combinations(range(size), 2))
        candidates = itertools.combinations(range(len(self.names)), size)
        best_score, best = -np.inf, None
        while True:
            chunk = np.array(list(itertools.islice(candidates, self.CHUNK)), dtype=np.intp)
            if not len(chunk):
                break
            redundancy = sum(overlap[chunk[:, a], chunk[:, b]] for a, b in pairs) / len(pairs)
            score = relevance[chunk].mean(axis=1) - redundancy
            top = score.argmax()
            if score[top] > best_score:
                best_score, best = score[top], chunk[top]
        return best_score, [self.names[index] for index in best]

    def best_subsets(self):
        rows = []
        for size in range(2, self.largest + 1):
            score, subset = self.best_subset(size)
            rows.append({"m": size, "score": score, "subset": ", ".join(subset)})
            print(f"best {size}: {', '.join(subset)}")
        return pd.DataFrame(rows)

    def plot_correlation(self):
        figure, axis = plt.subplots(figsize=(11, 10))
        image = axis.imshow(self.correlation.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
        ticks = range(len(self.names))
        axis.set_xticks(ticks)
        axis.set_yticks(ticks)
        axis.set_xticklabels(self.names, rotation=90, fontsize=7)
        axis.set_yticklabels(self.names, fontsize=7)
        figure.colorbar(image, ax=axis, label="Spearman correlation", shrink=0.8)
        axis.set_title("Correlation between features")
        figure.tight_layout()
        figure.savefig(self.plots / "feature_correlation_heatmap.png", dpi=150)
        plt.close(figure)

    def plot_features(self):
        columns = 6
        rows = -(-len(self.names) // columns)
        figure, axes = plt.subplots(rows, columns, figsize=(columns * 3.0, rows * 2.6))
        axes = axes.flatten()
        rho = self.scores.set_index("feature")["spearman_rho"]
        for axis, name in zip(axes, self.names):
            for source, color in self.COLORS.items():
                mask = self.table["source"] == source
                axis.scatter(
                    np.log1p(self.features.loc[mask, name]),
                    self.target[mask],
                    s=6,
                    alpha=0.35,
                    color=color,
                    linewidths=0,
                )
            axis.set_title(f"{name} ({rho[name]:.2f})", fontsize=9)
            axis.tick_params(labelsize=7)
            axis.spines[["top", "right"]].set_visible(False)
        for axis in axes[len(self.names):]:
            axis.axis("off")
        handles = [
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=6, label=source)
            for source, color in self.COLORS.items()
        ]
        figure.legend(handles=handles, loc="lower right", frameon=False)
        figure.suptitle("log1p(feature) against log(burst time), Spearman correlation in brackets", fontsize=12)
        figure.tight_layout(rect=[0, 0, 1, 0.97])
        figure.savefig(self.plots / "feature_vs_target_grid.png", dpi=150)
        plt.close(figure)

    def run(self):
        self.plots.mkdir(parents=True, exist_ok=True)
        tables = {
            "feature_relevance.csv": self.scores.sort_values("mutual_info", ascending=False),
            "feature_redundancy_pairs.csv": self.redundant_pairs(),
            "feature_pairwise_full.csv": self.neighbours(),
            "mrmr_ranking.csv": self.ranking(),
            "best_subsets.csv": self.best_subsets(),
        }
        for name, table in tables.items():
            table.round(4).to_csv(self.folder / name, index=False)
        self.plot_correlation()
        self.plot_features()
        print(f"wrote {len(tables)} tables and 2 plots to {self.folder}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    for name in sys.argv[1:] or ["linux", "macos"]:
        FeatureSelector(root, name).run()
