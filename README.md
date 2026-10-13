# TinyML

A wrapper tool that trains and evaluates scikit-learn regression models on a CSV training set. Everything is described by a YAML config: which models, which data, which feature sets, which settings to sweep.

Given a config, the runner:

- builds every model you list, from the built-in families or your own,
- evaluates each one with repeated k-fold cross-validation on the feature sets you choose,
- optionally sweeps one setting at a time to show its effect,
- saves per-model predictions, metrics and the exact configuration used.

A new model family is one small file. Scripts that build datasets and post-process results are separate and are documented in [tools/README.md](tools/README.md).

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Input files](#input-files)
- [Configuration](#configuration)
- [Feature sets](#feature-sets)
- [Model families](#model-families)
- [Named variants and sweeps](#named-variants-and-sweeps)
- [Output](#output)
- [Adding a model family](#adding-a-model-family)
- [Exit codes](#exit-codes)
- [Troubleshooting](#troubleshooting)
- [Layout](#layout)

## Requirements

- Python 3.10 or newer (developed on 3.13)
- numpy, pandas, scipy, scikit-learn, PyYAML (listed in `requirements.txt`)

## Installation

```bash
git clone <repository-url>
cd <repository-directory>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Check that it works:

```bash
python runner.py help
python runner.py families
```

## Quick start

Write a config:

```yaml
models: [random_forest, extra_trees]
data:
  training_set: data/training_set.csv
output: results
features: [best7, all]
seeds: [101, 202, 303]
```

Validate it, then run it:

```bash
python runner.py check config.yml
python runner.py config.yml
```

`check` validates the config, loads the data and fits every model once. Nothing is saved. Run it before a long job.

A run prints a summary table per model and writes the results under `<output>/<model name>/`.

## Commands

```
python runner.py <config.yml>         run every model described in the config
python runner.py check <config.yml>   validate the config and test each model once, nothing is saved
python runner.py families             list the model families with their settings
python runner.py params <family>      list every parameter a family accepts
python runner.py help                 show the usage text
```

`families` shows what is available and the default sweep of each family:

```
random_forest
  model     sklearn.RandomForestRegressor
  settings  n_estimators=100, max_depth=3
  sweep     max_depth: 1, 2, 3, ...
```

`params` lists every parameter that can be used in `settings` or `grid` for a family:

```bash
python runner.py params gradient_boosting
```

## Input files

The runner needs a training set and, to use the `best` feature sets, a subsets file.

### Training set

A CSV with one row per sample.

| Column | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Sample identifier |
| `true_burst` | yes | Target value, not negative. Models are trained on its logarithm, with values floored at 1e-6. |
| `source` | no | Free label, ignored |
| `hist_burst`, `hist_maxrss` | no | Extra measurements. When present they form the `history` feature set. |
| any other column | | A numeric feature |

Every feature column must be numeric and free of missing values. The runner stops with a clear message otherwise.

### Subsets file

A CSV with the columns `m` and `subset`, where `subset` is a comma separated list of feature names:

```
m,subset
2,"feature_a, feature_b"
3,"feature_a, feature_b, feature_c"
```

Each row becomes a feature set named `best<m>`. By default the runner reads `best_subsets.csv` from the folder of the training set. Set `data.subsets` to use another file.

## Configuration

| Key | Required | Default | Meaning |
| --- | --- | --- | --- |
| `models` | no | `all` | `all`, a family name, or a list. An entry can be a mapping with `family` (required), `name`, `settings` and `grid`. |
| `data.training_set` | yes | | Path to the training set CSV |
| `data.subsets` | no | `best_subsets.csv` beside the training set | Path to the subsets CSV |
| `output` | yes | | Folder for results, one subfolder per model name |
| `features` | no | every available set | Feature sets to evaluate |
| `primary` | no | first of `features` | Feature set used for the settings sweep |
| `sweep` | no | `true` | Vary each grid setting one at a time |
| `seeds` | no | `[101, 202, 303, 404, 505]` | One cross-validation repeat per seed |
| `folds` | no | `5` | Cross-validation folds |

Relative paths start at the repository root. Absolute paths and `~` also work. Unknown keys are rejected with a suggestion.

Each seed runs a full cross-validation with its own shuffle and its own model random state. Metrics are reported as the mean and standard deviation over seeds, so more seeds give a more reliable estimate at a proportional cost.

## Feature sets

| Name | Columns |
| --- | --- |
| `best2` ... `best9` | The subset with that `m` in the subsets file |
| `all` | Every feature column |
| `history` | `hist_burst_log` and `hist_maxrss`, only when the training set has them |
| `a+b` | The union of two sets, for example `best7+history` |

When `features` is omitted every set is evaluated, plus `<primary>+history` when history exists.

## Model families

| Family | Estimator | Standard scaling |
| --- | --- | --- |
| `random_forest` | `RandomForestRegressor` | no |
| `extra_trees` | `ExtraTreesRegressor` | no |
| `gradient_boosting` | `HistGradientBoostingRegressor` | no |
| `decision_tree` | `DecisionTreeRegressor` | no |
| `mlp` | `MLPRegressor` | yes |
| `svr` | `SVR` (RBF kernel) | yes |
| `knn` | `KNeighborsRegressor` | yes |
| `ridge` | `Ridge` | yes |

Scaled families are wrapped in a `StandardScaler` that is fitted inside each cross-validation fold, so no information leaks from the test fold.

## Named variants and sweeps

A model entry can override any parameter of the underlying scikit-learn estimator and define its own sweep. This runs the default forest and a deeper variant side by side:

```yaml
models:
  - random_forest
  - family: random_forest
    name: rf_deep
    settings: {max_depth: 8, min_samples_leaf: 2}
    grid: {max_depth: [4, 6, 8, 10]}
data:
  training_set: data/training_set.csv
output: results
features: [best7, best7+history]
seeds: [101, 202]
```

- `settings` overrides the family defaults. Any parameter listed by `params <family>` is accepted.
- `grid` lists values to sweep. With `sweep: true` each value is evaluated one at a time with every other setting left at its default, on the `primary` feature set. The default value is reported as `default`, the others as `parameter=value`.
- `name` gives the variant its own results folder. Model names must be unique, so name every entry of a family that appears more than once.

Parameters are validated against the estimator. A misspelled name is rejected with a suggestion, `random_state` is rejected because it comes from `seeds`, and every setting is test-fitted by `check` before anything runs.

## Output

For each model the runner writes `<output>/<model name>/`:

| File | Content |
| --- | --- |
| `summary.csv` | Mean and standard deviation over seeds, per feature set and configuration |
| `runs.csv` | One row per feature set, configuration and seed |
| `predictions.csv` | Out-of-fold prediction for every sample, seed and configuration |
| `config.json` | Everything needed to reproduce the run |

Every prediction is out of fold: it comes from a model that did not see that sample during training.

Metrics:

| Metric | Meaning |
| --- | --- |
| `r2` | Coefficient of determination on the log target. 1 is perfect, 0 is no better than predicting the mean. |
| `spearman` | Rank correlation between predicted and true values |
| `error_pct` | Median absolute percentage error of the prediction, over samples with a target above zero |

If one model fails, the others still run and are saved. The failure is reported and the exit code is 1.

## Adding a model family

Create a file in `models/`. It is discovered automatically, no registration is needed.

```python
from sklearn.ensemble import AdaBoostRegressor

from models.base import BurstModel


class AdaBoostModel(BurstModel):
    family = "ada_boost"
    estimator_class = AdaBoostRegressor
    settings = {"n_estimators": 50}
    grid = {"n_estimators": [10, 25, 50, 100], "learning_rate": [0.1, 0.5, 1.0]}
```

| Attribute | Meaning |
| --- | --- |
| `family` | Name used in configs and on the command line |
| `estimator_class` | Any scikit-learn regressor |
| `settings` | Default parameters, overridable in a config |
| `grid` | Parameters swept when `sweep` is on |
| `scaled` | Set to `True` to standardize features inside each fold |
| `features` | Default primary feature set when the config does not name one, `best7` unless changed |

Then:

```bash
python runner.py families
python runner.py params ada_boost
```

A file that fails to import is reported as a warning on stderr and skipped. The other families keep working.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | The run finished but at least one model failed. The other models are still saved. |
| 2 | Configuration or input error, reported as `error: ...` on stderr |
| 130 | Interrupted |

## Troubleshooting

- `training set ... not found`: point `data.training_set` at the right file.
- `feature subsets ... not found`: create the subsets file or set `data.subsets`.
- `unknown model family`: the message lists the available families and any file in `models/` that failed to load.
- `unknown feature set`: use `best2` to `best9`, `all`, `history`, or a `+` combination. `history` exists only when the training set has history columns.
- A `ridge` or `svr` run on the `all` feature set can print overflow warnings or produce extreme predictions when the features are strongly redundant. Use a `best` subset or a tree-based family.

## Layout

```
runner.py                   command line entry point, config loading, model registry
models/
  base.py                   training set, feature sets, BurstModel, cross-validated Experiment
  random_forest.py          one file per model family
  extra_trees.py
  gradient_boosting.py
  decision_tree.py
  mlp.py
  svr.py
  knn.py
  ridge.py
tools/                      dataset and result tools, see tools/README.md
requirements.txt
```

Generated and local material (`corpus/`, `dataset/`, `configs/`, `models/results/`) is listed in `.gitignore` and is not part of the repository.
