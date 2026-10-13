import sys
from pathlib import Path

import pandas as pd


class History:
    def __init__(self, schedule, argc, columns):
        self.schedule = schedule
        self.argc = argc
        self.columns = columns

    def mask(self, labels):
        return (labels["sched_grid"] == self.schedule) & (labels["argc"] == self.argc)


class DatasetSpec:
    def __init__(self, name, features, labels, history=None):
        self.name = name
        self.features = features
        self.labels = labels
        self.history = history


class Datasets:
    SPECS = {
        "linux": DatasetSpec(
            "linux",
            "features_linux.csv",
            "labels_linux.csv",
            History("nice0_other", 1, {"cpu_s_median": "hist_burst", "maxrss_kb": "hist_maxrss"}),
        ),
        "macos": DatasetSpec("macos", "features.csv", "labels_macos.csv"),
    }

    @classmethod
    def get(cls, name):
        if name not in cls.SPECS:
            raise SystemExit(f"unknown dataset {name}, available: {', '.join(cls.SPECS)}")
        return cls.SPECS[name]


class TrainingSetBuilder:
    def __init__(self, root, spec):
        self.root = Path(root) / "dataset"
        self.spec = spec
        self.features = pd.read_csv(self.root / spec.features)
        self.labels = pd.read_csv(self.root / spec.labels)

    def burst(self, labels):
        return labels.groupby("id")["cpu_s_median"].median().rename("true_burst")

    def build(self):
        history = self.spec.history
        if history is None:
            return self.features.merge(self.burst(self.labels), on="id")
        first = history.mask(self.labels)
        past = self.labels[first].set_index("id")[list(history.columns)].rename(columns=history.columns)
        return self.features.merge(self.burst(self.labels[~first]), on="id").merge(past, on="id")

    def save(self):
        table = self.build()
        folder = self.root / self.spec.name
        folder.mkdir(parents=True, exist_ok=True)
        table.to_csv(folder / "training_set.csv", index=False)
        print(f"{self.spec.name}: wrote {len(table)} programs to {folder / 'training_set.csv'}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    for name in sys.argv[1:] or Datasets.SPECS:
        TrainingSetBuilder(root, Datasets.get(name)).save()
