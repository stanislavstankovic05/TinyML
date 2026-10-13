import importlib
import inspect
import sys
from pathlib import Path

import yaml

from models.base import ROOT, BurstModel, ConfigError, Experiment, suggest


class RunConfig:
    KEYS = {"models", "data", "output", "features", "primary", "sweep", "seeds", "folds"}
    DATA_KEYS = {"training_set", "subsets"}
    MODEL_KEYS = {"family", "name", "settings", "grid"}

    def __init__(self, values, root=ROOT):
        if not isinstance(values, dict):
            raise ConfigError("the config must be a mapping of keys to values")
        self.root = Path(root)
        self.check_keys(values, self.KEYS, "the config")
        data = values.get("data") or {}
        if not isinstance(data, dict):
            raise ConfigError("data must hold training_set and optionally subsets")
        self.check_keys(data, self.DATA_KEYS, "data")
        self.training_set = self.resolve(self.require(data, "training_set", "data.training_set"))
        subsets = data.get("subsets")
        self.subsets = self.resolve(subsets) if subsets else self.training_set.parent / "best_subsets.csv"
        self.output = self.resolve(self.require(values, "output", "output"))
        self.models = self.entries(values.get("models", "all"))
        self.features = self.names(values.get("features") or [], "features")
        self.primary = None if values.get("primary") is None else str(values["primary"])
        self.sweep = self.flag(values.get("sweep", True), "sweep")
        self.seeds = self.integers(values.get("seeds", [101, 202, 303, 404, 505]), "seeds")
        self.folds = self.integers([values.get("folds", 5)], "folds")[0]

    @classmethod
    def load(cls, path, root=ROOT):
        source = Path(path)
        if not source.exists():
            raise ConfigError(f"config file {path} not found")
        try:
            values = yaml.safe_load(source.read_text())
        except yaml.YAMLError as error:
            raise ConfigError(f"{path} is not valid yaml: {error}")
        return cls({} if values is None else values, root)

    def check_keys(self, values, allowed, where):
        unknown = sorted(set(values) - allowed)
        if not unknown:
            return
        hint = ", settings now belong inside each model entry" if "settings" in unknown else suggest(unknown[0], allowed)
        raise ConfigError(f"unknown keys in {where}: {unknown}{hint}, allowed: {sorted(allowed)}")

    def require(self, values, key, label):
        if not values.get(key):
            raise ConfigError(f"{label} is required")
        return values[key]

    def resolve(self, value):
        path = Path(str(value)).expanduser()
        return path if path.is_absolute() else self.root / path

    def names(self, value, label):
        items = [value] if isinstance(value, str) else value
        if not isinstance(items, list):
            raise ConfigError(f"{label} must be a name or a list of names")
        return [str(item) for item in items]

    def flag(self, value, label):
        if not isinstance(value, bool):
            raise ConfigError(f"{label} must be true or false")
        return value

    def integers(self, values, label):
        if not isinstance(values, list) or not values or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in values
        ):
            raise ConfigError(f"{label} must be a non empty list of whole numbers")
        return values

    def entries(self, value):
        items = value if isinstance(value, list) else [value]
        return [self.entry(item) for item in items]

    def entry(self, item):
        if item == "all":
            return "all"
        if isinstance(item, str):
            item = {"family": item}
        if not isinstance(item, dict):
            raise ConfigError("each model must be a family name or an entry with family, name, settings, grid")
        self.check_keys(item, self.MODEL_KEYS, "a model entry")
        if not item.get("family"):
            raise ConfigError("every model entry needs a family")
        for key in ("settings", "grid"):
            if item.get(key) is not None and not isinstance(item[key], dict):
                raise ConfigError(f"{key} of {item['family']} must be a mapping")
        return {key: item.get(key) for key in self.MODEL_KEYS}


class Registry:
    SKIP = {"base", "__init__"}

    def __init__(self):
        self.folder = ROOT / "models"
        self.families = {}
        self.broken = {}
        self.discover()

    def discover(self):
        for path in sorted(self.folder.glob("*.py")):
            if path.stem in self.SKIP:
                continue
            try:
                module = importlib.import_module(f"models.{path.stem}")
            except Exception as error:
                self.broken[path.name] = f"{type(error).__name__}: {error}"
                continue
            for _, member in inspect.getmembers(module, inspect.isclass):
                if issubclass(member, BurstModel) and member.family and member.__module__ == module.__name__:
                    self.add(member, path.name)

    def add(self, member, source):
        if member.estimator_class is None:
            self.broken[source] = f"{member.__name__} has no estimator_class"
        elif member.family in self.families:
            self.broken[source] = f"family {member.family} is already defined"
        else:
            self.families[member.family] = member

    def warnings(self):
        return [f"{name} was not loaded, {reason}" for name, reason in self.broken.items()]

    def family(self, name):
        if name not in self.families:
            skipped = f", files that failed to load: {', '.join(self.broken)}" if self.broken else ""
            raise ConfigError(
                f"unknown model family {name!r}{suggest(name, self.families)}, "
                f"available: {', '.join(self.families)}{skipped}"
            )
        return self.families[name]

    def create(self, entries):
        models = []
        for entry in entries:
            if entry == "all":
                models += [family() for family in self.families.values()]
                continue
            family = self.family(entry["family"])
            models.append(family(entry["name"], entry["settings"], entry["grid"]))
        names = [model.name for model in models]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ConfigError(f"model names must be unique, give a name to the entries called {repeated}")
        return models


class Runner:
    def __init__(self, config, registry=None):
        self.config = config
        self.registry = registry or Registry()

    @classmethod
    def from_file(cls, path):
        return cls(RunConfig.load(path))

    def prepare(self):
        experiments = [Experiment(model, self.config) for model in self.registry.create(self.config.models)]
        for experiment in experiments:
            experiment.check()
        return experiments

    def check(self):
        for experiment in self.prepare():
            configurations = experiment.count()
            fits = configurations * len(self.config.seeds) * self.config.folds
            print(f"{experiment.model.name} ({experiment.model.family}): {configurations} configurations, {fits} fits")
        print(f"all models passed, results would go to {self.config.output}")
        return 0

    def run(self):
        failed = {}
        experiments = self.prepare()
        for experiment in experiments:
            try:
                experiment.run()
            except Exception as error:
                failed[experiment.model.name] = f"{type(error).__name__}: {error}"
                print(f"FAILED {experiment.model.name}: {failed[experiment.model.name]}", file=sys.stderr)
        done = [experiment.model.name for experiment in experiments if experiment.model.name not in failed]
        print(f"finished: {len(done)} saved, {len(failed)} failed")
        return 1 if failed else 0


class Help:
    USAGE = """\
usage
  python runner.py <config.yml>         run every model described in the config
  python runner.py check <config.yml>   validate the config and test each model once, nothing is saved
  python runner.py families             list the model families with their settings
  python runner.py params <family>      list every parameter a family accepts
  python runner.py help                 show this text

config keys
  models      all, a family name, or a list of them; an entry can also be a mapping with
              family (required), name, settings and grid, to create a named variant of a family
  data        training_set (required) and subsets, default best_subsets.csv beside the training set
  output      folder for the results, one subfolder per model name (required)
  features    feature sets to evaluate, default every one:
              best2 to best9, all, history, or a+b to join sets, for example best7+history
  primary     feature set used for the settings sweep, default the first of features
  sweep       true to vary each grid setting one at a time, default true
  seeds       list of whole numbers, one cross validation repeat per seed, default 101 202 303 404 505
  folds       cross validation folds, default 5

settings accept any parameter of the family's scikit-learn model, grid takes lists of values to sweep.
relative paths start at the repo root, absolute paths and ~ also work.

example
  models:
    - random_forest
    - family: random_forest
      name: rf_deep
      settings: {max_depth: 8, min_samples_leaf: 2}
      grid: {max_depth: [4, 6, 8, 10]}
  data:
    training_set: dataset/linux/training_set.csv
  output: models/results/linux/trees
  features: [best7, best7+history]
  seeds: [101, 202]

a new family is a file in models/ with a class like random_forest.py, it is found automatically.
"""

    def __init__(self, registry):
        self.registry = registry

    def text(self):
        return f"{self.USAGE}\nfamilies: {', '.join(self.registry.families)}"

    def families(self):
        lines = []
        for name, family in self.registry.families.items():
            path = f"{family.estimator_class.__module__.split('.')[0]}.{family.estimator_class.__name__}"
            sweep = "; ".join(f"{key}: {', '.join(map(str, values))}" for key, values in family.grid.items())
            settings = ", ".join(f"{key}={value}" for key, value in family.settings.items())
            lines += [name, f"  model     {path}{' with standard scaling' if family.scaled else ''}",
                      f"  settings  {settings}", f"  sweep     {sweep}"]
        return "\n".join(lines)

    def params(self, name):
        family = self.registry.family(name)
        accepted = family.estimator_class().get_params(deep=False)
        lines = [f"{name}: {family.estimator_class.__name__}, random_state comes from the seeds"]
        for key, default in accepted.items():
            if key == "random_state":
                continue
            used = f"   family setting {family.settings[key]}" if key in family.settings else ""
            lines.append(f"  {key:<24} default {default}{used}")
        return "\n".join(lines)


class Cli:
    HELP = {"help", "-h", "--help"}

    def __init__(self):
        self.registry = Registry()

    def dispatch(self, arguments):
        guide = Help(self.registry)
        if not arguments or arguments[0] in self.HELP:
            print(guide.text())
            return 0
        command, rest = arguments[0], arguments[1:]
        if command == "families":
            print(guide.families())
            return 0
        if command == "params":
            if len(rest) != 1:
                raise ConfigError("usage: runner.py params <family>")
            print(guide.params(rest[0]))
            return 0
        if command == "check":
            if len(rest) != 1:
                raise ConfigError("usage: runner.py check <config.yml>")
            return Runner(RunConfig.load(rest[0]), self.registry).check()
        if rest:
            raise ConfigError("usage: runner.py <config.yml>, 'runner.py help' lists the commands")
        return Runner(RunConfig.load(command), self.registry).run()

    def run(self, arguments):
        for line in self.registry.warnings():
            print(f"warning: {line}", file=sys.stderr)
        try:
            return self.dispatch(arguments)
        except ConfigError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("interrupted", file=sys.stderr)
            return 130


if __name__ == "__main__":
    sys.exit(Cli().run(sys.argv[1:]))
