import difflib
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    pass


def suggest(word, options):
    close = difflib.get_close_matches(str(word), [str(option) for option in options], n=1)
    return f" (did you mean {close[0]}?)" if close else ""


def freeze(value):
    return tuple(freeze(item) for item in value) if isinstance(value, list) else value


class TrainingSet:
    META = ["id", "source", "true_burst", "hist_burst", "hist_maxrss"]
    FLOOR = 1e-6

    def __init__(self, path):
        self.frame = self.read(Path(path))
        for column in ("id", "true_burst"):
            if column not in self.frame.columns:
                raise ConfigError(f"training set {path} has no {column} column")
        self.static = [column for column in self.frame.columns if column not in self.META]
        self.history = []
        if "hist_burst" in self.frame.columns:
            self.frame["hist_burst_log"] = np.log(self.frame["hist_burst"].clip(lower=self.FLOOR))
            self.history = ["hist_burst_log", "hist_maxrss"]
        self.validate(path)
        self.ids = self.frame["id"].to_numpy()
        self.burst = self.frame["true_burst"].to_numpy()
        self.target = np.log(self.frame["true_burst"].clip(lower=self.FLOOR)).to_numpy()

    def read(self, path):
        if not path.exists():
            raise ConfigError(f"training set {path} not found, tools/build_training_set.py creates it")
        try:
            return pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as error:
            raise ConfigError(f"training set {path} cannot be read: {error}")

    def validate(self, path):
        used = self.static + self.history + ["true_burst"]
        text = [column for column in used if not pd.api.types.is_numeric_dtype(self.frame[column])]
        if text:
            raise ConfigError(f"training set {path} has non numeric columns: {text[:5]}")
        empty = [column for column in used if self.frame[column].isna().any()]
        if empty:
            raise ConfigError(f"training set {path} has missing values in: {empty[:5]}")
        if not self.static:
            raise ConfigError(f"training set {path} has no feature columns")

    def matrix(self, columns):
        return self.frame[columns].astype(float)


class FeatureSets:
    def __init__(self, data, path):
        if not Path(path).exists():
            raise ConfigError(f"feature subsets {path} not found, tools/select_features.py creates them")
        subsets = pd.read_csv(path)
        for column in ("m", "subset"):
            if column not in subsets.columns:
                raise ConfigError(f"feature subsets {path} has no {column} column")
        self.sets = {f"best{row.m}": [name.strip() for name in row.subset.split(",")] for row in subsets.itertuples()}
        for name, columns in self.sets.items():
            missing = [column for column in columns if column not in data.frame.columns]
            if missing:
                raise ConfigError(f"{name} in {path} uses columns the training set lacks: {missing}")
        self.sets["all"] = list(data.static)
        if data.history:
            self.sets["history"] = list(data.history)

    def columns(self, name):
        columns = []
        for part in str(name).split("+"):
            if part not in self.sets:
                raise ConfigError(f"unknown feature set {part!r}{suggest(part, self.sets)}, available: {', '.join(self.sets)}")
            columns += [column for column in self.sets[part] if column not in columns]
        return columns

    def standard(self, primary):
        names = list(self.sets)
        if "history" in self.sets and "history" not in primary.split("+"):
            names.append(f"{primary}+history")
        return names


class BurstModel:
    family = None
    estimator_class = None
    features = "best7"
    settings = {}
    grid = {}
    scaled = False

    def __init__(self, name=None, settings=None, grid=None):
        self.name = name or self.family
        self.accepted = self.estimator_class().get_params(deep=False)
        self.seeded = "random_state" in self.accepted
        given = {key: freeze(value) for key, value in (settings or {}).items()}
        self.check_names(given, "setting")
        self.settings = {**type(self).settings, **given}
        self.grid = self.checked_grid(type(self).grid if grid is None else grid)

    def check_names(self, names, label):
        for name in names:
            if name == "random_state":
                raise ConfigError(f"{self.name}: random_state is set from the seeds list, not as a {label}")
            if name not in self.accepted:
                raise ConfigError(
                    f"{self.name}: unknown {label} {name!r}{suggest(name, self.accepted)}, "
                    f"'runner.py params {self.family}' lists them"
                )

    def checked_grid(self, grid):
        self.check_names(grid, "grid parameter")
        for parameter, values in grid.items():
            if not isinstance(values, (list, tuple)) or not values:
                raise ConfigError(f"{self.name}: grid for {parameter} must be a non empty list")
        return {parameter: [freeze(value) for value in values] for parameter, values in grid.items()}

    def effective(self, parameter):
        return self.settings.get(parameter, self.accepted[parameter])

    def build(self, settings, seed):
        parameters = {**settings, "random_state": seed} if self.seeded else dict(settings)
        estimator = self.estimator_class(**parameters)
        return make_pipeline(StandardScaler(), estimator) if self.scaled else estimator

    def variations(self):
        for parameter, values in self.grid.items():
            for value in values:
                if value != self.effective(parameter):
                    yield f"{parameter}={value}", {**self.settings, parameter: value}

    def description(self):
        resolved = {**{parameter: self.effective(parameter) for parameter in self.grid}, **self.settings}
        return {
            "family": self.family,
            "settings": {name: str(value) for name, value in resolved.items()},
            "grid": {name: [str(value) for value in values] for name, values in self.grid.items()},
        }


class Experiment:
    METRICS = ["r2", "spearman", "error_pct"]

    def __init__(self, model, config):
        self.model = model
        self.config = config
        self.data = TrainingSet(config.training_set)
        self.feature_sets = FeatureSets(self.data, config.subsets)
        self.primary = config.primary or (config.features[0] if config.features else model.features)
        self.names = self.selected()
        self.output = config.output / model.name
        if config.folds < 2 or config.folds > len(self.data.ids):
            raise ConfigError(f"folds must be between 2 and the {len(self.data.ids)} programs, got {config.folds}")
        self.runs = []
        self.predictions = []

    def selected(self):
        names = list(self.config.features) or self.feature_sets.standard(self.primary)
        if self.primary not in names:
            names.insert(0, self.primary)
        for name in names:
            self.feature_sets.columns(name)
        return names

    def configurations(self):
        yield "default", self.model.settings
        if self.config.sweep:
            yield from self.model.variations()

    def count(self):
        return len(self.names) + len(list(self.model.variations())) * int(self.config.sweep)

    def check(self):
        matrix = self.data.matrix(self.feature_sets.columns(self.primary))
        for config, settings in self.configurations():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self.model.build(settings, self.config.seeds[0]).fit(matrix, self.data.target)
            except Exception as error:
                raise ConfigError(f"{self.model.name} {config}: {type(error).__name__}: {error}")

    def predict(self, columns, settings, seed):
        folds = KFold(self.config.folds, shuffle=True, random_state=seed)
        estimator = self.model.build(settings, seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", RuntimeWarning)
            return cross_val_predict(estimator, self.data.matrix(columns), self.data.target, cv=folds)

    def score(self, predicted):
        target, burst = self.data.target, self.data.burst
        measured = burst > 0
        error = np.abs(np.exp(predicted) - burst)[measured] / burst[measured]
        return {
            "r2": 1 - ((target - predicted) ** 2).sum() / ((target - target.mean()) ** 2).sum(),
            "spearman": spearmanr(target, predicted).statistic,
            "error_pct": 100 * np.median(error),
        }

    def evaluate(self, feature_set, config, settings):
        columns = self.feature_sets.columns(feature_set)
        for seed in self.config.seeds:
            predicted = self.predict(columns, settings, seed)
            run = {"feature_set": feature_set, "config": config, "seed": seed}
            self.runs.append({**run, **self.score(predicted)})
            self.predictions.append(
                pd.DataFrame({**run, "id": self.data.ids, "true_burst": self.data.burst, "pred_burst": np.exp(predicted)})
            )

    def summary(self, runs):
        grouped = runs.groupby(["feature_set", "config"], sort=False)[self.METRICS]
        table = grouped.agg(["mean", "std"])
        table.columns = [f"{metric}_{statistic}" for metric, statistic in table.columns]
        table = table.reset_index()
        table.insert(2, "n_features", [len(self.feature_sets.columns(name)) for name in table["feature_set"]])
        return table

    def save(self):
        self.output.mkdir(parents=True, exist_ok=True)
        runs = pd.DataFrame(self.runs)
        summary = self.summary(runs)
        runs.round(4).to_csv(self.output / "runs.csv", index=False)
        summary.round(4).to_csv(self.output / "summary.csv", index=False)
        pd.concat(self.predictions).to_csv(self.output / "predictions.csv", index=False, float_format="%.6g")
        description = {
            "model": self.model.name,
            **self.model.description(),
            "training_set": str(self.config.training_set),
            "subsets": str(self.config.subsets),
            "primary": self.primary,
            "feature_sets": self.names,
            "sweep": self.config.sweep,
            "seeds": self.config.seeds,
            "folds": self.config.folds,
        }
        (self.output / "config.json").write_text(json.dumps(description, indent=2) + "\n")
        return summary

    def run(self):
        for name in self.names:
            self.evaluate(name, "default", self.model.settings)
        if self.config.sweep:
            for config, settings in self.model.variations():
                self.evaluate(self.primary, config, settings)
        summary = self.save()
        print(f"{self.model.name}: {len(summary)} configurations saved to {self.output}")
        print(summary[["feature_set", "config", "spearman_mean", "error_pct_mean"]].to_string(index=False))
