# Tool reference

This page documents the command line tools. The project overview and results are in the [main README](../README.md).

Tools for predicting the CPU burst time of a program from features that are known before it runs, and for measuring how much that prediction helps a shortest-job-first (SJF) scheduler.

The repository contains two parts:

- `tools/` builds the data: a corpus of C programs, static features extracted with LLVM, measured run times, a training set, and a feature ranking.
- `runner.py` and `models/` train and evaluate regression models on a training set. Everything is described by a YAML config, and new model families are added by creating one small file.

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Building a dataset](#building-a-dataset)
- [Running models](#running-models)
- [Configuration reference](#configuration-reference)
- [Results](#results)
- [Scheduling simulation and plots](#scheduling-simulation-and-plots)
- [Adding a model family](#adding-a-model-family)
- [Project layout](#project-layout)
- [Exit codes](#exit-codes)
- [Troubleshooting](#troubleshooting)

## How it works

1. Each program is compiled to LLVM IR and described by 30 static features: instruction mix, loop structure, estimated trip counts, call graph shape, stack use, and similar properties.
2. Each program is run and its CPU time is recorded. This is the target, the burst time.
3. Features are ranked by relevance to the target and redundancy with each other (mRMR). For every size `m` from 2 to 9 the best subset is stored as `best2` ... `best9`.
4. Models predict the logarithm of the burst time. Evaluation is repeated k-fold cross-validation with one repeat per seed, so every prediction is made by a model that never saw that program.
5. The scheduling simulator orders random batches of programs by predicted burst time and compares the average waiting time with first-come-first-served (FIFO) and with the ideal order (the oracle, which sorts by the true burst time).

Some datasets also carry history features (`hist_burst_log`, `hist_maxrss`) taken from one earlier run of the same program. They are available as the `history` feature set when the training set contains them.

## Requirements

- Python 3.10 or newer (developed on 3.13)
- numpy, pandas, scipy, scikit-learn, matplotlib, PyYAML (see `requirements.txt`)
- Only for building a dataset from source code:
  - LLVM with `clang`, `opt` and `llvm-link` (developed on LLVM 22)
  - git, to fetch the benchmark suites
  - for Linux scheduling labels from a macOS host, a Linux virtual machine such as [Lima](https://lima-vm.io)

Training and evaluating models needs only the Python packages and a training set.

## Installation

```bash
git clone <repository-url>
cd <repository-directory>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

LLVM, only needed for feature extraction:

```bash
brew install llvm            # macOS
sudo apt install llvm clang  # Debian and Ubuntu
```

`tools/extract_features.py` looks for the LLVM tools in the Homebrew location first and then on `PATH`, including versioned names such as `clang-18`.

Check the installation:

```bash
python runner.py help
python runner.py families
```

## Quick start

With a training set already built, for example `dataset/linux/training_set.csv` and its `best_subsets.csv`:

```bash
cat > run.yml <<'EOF'
models: [random_forest, extra_trees]
data:
  training_set: dataset/linux/training_set.csv
output: models/results/linux
features: [best7, all]
seeds: [101, 202, 303]
EOF

python runner.py check run.yml
python runner.py run.yml
python tools/sjf_simulator.py models/results/linux
python tools/plot_results.py models/results/linux
```

`check` validates the config and fits every model once without saving anything. Run it before a long job.

## Building a dataset

All commands run from the repository root. Each step writes into `dataset/`, which is not tracked by git.

### 1. Corpus

The corpus is a set of C programs under `corpus/`:

```bash
mkdir -p corpus
git clone https://github.com/tacle/tacle-bench corpus/tacle-bench
git clone https://github.com/embench/embench-iot corpus/embench-iot
python tools/gen_synth.py 320
```

`gen_synth.py` writes the synthetic programs and their `manifest.csv` to `corpus/synthetic/`. The count defaults to 320 and the generator is seeded, so the output is reproducible. TACLeBench programs are used for labels. Embench programs are parsed for features but are not run.

### 2. Static features

```bash
python tools/extract_features.py
```

This compiles every program at `-O1`, runs the LLVM analysis printers and writes `dataset/features.csv`. An optional argument sets the output file:

```bash
python tools/extract_features.py dataset/features_linux.csv
```

The `linux` dataset reads `features_linux.csv` and the `macos` dataset reads `features.csv`. Run the extractor in the environment that matches the labels, because target dependent features such as instruction cost differ between platforms.

### 3. Labels

```bash
python tools/collect_labels.py macos       # writes dataset/labels_macos.csv
python tools/collect_labels.py linux       # writes dataset/labels_linux.csv
python tools/collect_labels.py contended   # writes dataset/labels_contended.csv
```

| Collector | What it measures |
| --- | --- |
| `macos` | CPU time of each program running alone, for several inputs |
| `linux` | CPU time, system time, peak memory, page faults and context switches under four scheduling settings (normal, nice 10, batch, idle). Run it inside a Linux machine. |
| `contended` | Batches of 8 programs pinned to one CPU and run at the same time, recording real turnaround and waiting time |

macOS has no history features and no memory column. The Linux machine must be able to read the repository, for example through a shared mount.

### 4. Training set

```bash
python tools/build_training_set.py            # linux and macos
python tools/build_training_set.py linux
```

This merges features with labels and writes `dataset/<name>/training_set.csv`. For the Linux dataset one earlier run per program becomes the history features, and the remaining runs form the target.

### 5. Feature selection

```bash
python tools/select_features.py               # linux and macos
python tools/select_features.py linux
```

Output in `dataset/<name>/`:

| File | Content |
| --- | --- |
| `feature_relevance.csv` | Correlation of each feature with the target |
| `feature_redundancy_pairs.csv`, `feature_pairwise_full.csv` | Correlation between features |
| `mrmr_ranking.csv` | mRMR ranking |
| `best_subsets.csv` | Best subset for each size from 2 to 9, used by the runner |
| `plots/` | Correlation heatmap and feature versus target grid |

## Running models

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

`params` lists every parameter that can be used in `settings` or `grid`:

```bash
python runner.py params gradient_boosting
```

Built-in families:

| Family | Estimator | Scaled |
| --- | --- | --- |
| `random_forest` | `RandomForestRegressor` | no |
| `extra_trees` | `ExtraTreesRegressor` | no |
| `gradient_boosting` | `HistGradientBoostingRegressor` | no |
| `decision_tree` | `DecisionTreeRegressor` | no |
| `mlp` | `MLPRegressor` | yes |
| `svr` | `SVR` (RBF kernel) | yes |
| `knn` | `KNeighborsRegressor` | yes |
| `ridge` | `Ridge` | yes |

Scaled families are wrapped in a `StandardScaler` that is fitted inside each cross-validation fold.

## Configuration reference

| Key | Required | Default | Meaning |
| --- | --- | --- | --- |
| `models` | no | `all` | `all`, a family name, or a list. An entry can be a mapping with `family` (required), `name`, `settings` and `grid`. |
| `data.training_set` | yes | | Path to the training set CSV |
| `data.subsets` | no | `best_subsets.csv` beside the training set | Path to the feature subsets CSV |
| `output` | yes | | Folder for results, one subfolder per model name |
| `features` | no | every available set | Feature sets to evaluate |
| `primary` | no | first of `features` | Feature set used for the settings sweep and for the scheduling simulation |
| `sweep` | no | `true` | Vary each grid setting one at a time |
| `seeds` | no | `[101, 202, 303, 404, 505]` | One cross-validation repeat per seed |
| `folds` | no | `5` | Cross-validation folds |

Relative paths start at the repository root. Absolute paths and `~` also work.

### Feature sets

| Name | Columns |
| --- | --- |
| `best2` ... `best9` | The best subset of that size from `best_subsets.csv` |
| `all` | Every static feature |
| `history` | `hist_burst_log` and `hist_maxrss`, only when the training set has them |
| `a+b` | The union of two sets, for example `best7+history` |

When `features` is omitted, every set is evaluated, plus `<primary>+history` when history exists.

### Named variants

A model entry can override any parameter of the underlying scikit-learn estimator and define its own sweep. This runs the default forest and a deeper variant side by side:

```yaml
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
```

Parameters are validated against the estimator. A misspelled name is rejected with a suggestion, `random_state` is rejected because it comes from `seeds`, and every setting is test-fitted by `check` before anything runs.

Model names must be unique. Give a `name` to every entry of a family that appears more than once.

### Sweep

With `sweep: true`, each value in a model's `grid` is evaluated one at a time with all other settings left at their defaults, on the `primary` feature set. The default value is reported as `default`; the others are named `parameter=value`.

## Results

For each model the runner writes `<output>/<model>/`:

| File | Content |
| --- | --- |
| `summary.csv` | Mean and standard deviation over seeds, per feature set and configuration |
| `runs.csv` | One row per feature set, configuration and seed |
| `predictions.csv` | Out-of-fold prediction for every program, seed and configuration |
| `config.json` | Everything needed to reproduce the run |

Metrics:

| Metric | Meaning |
| --- | --- |
| `r2` | Coefficient of determination on the log burst time. 1 is perfect, 0 is no better than predicting the mean. |
| `spearman` | Rank correlation between predicted and true burst. This is what ordering depends on. |
| `error_pct` | Median absolute percentage error of the predicted burst time, for programs with a measured burst above zero |

The simulator and plotter add to the same folders and to the top-level results folder:

```
<output>/
  sjf_models.csv
  model_comparison.png
  feature_comparison.png
  <model>/
    summary.csv  runs.csv  predictions.csv  config.json
    sjf_workloads.csv  sjf_configurations.csv
    by_features.png  by_settings.png
```

## Scheduling simulation and plots

```bash
python tools/sjf_simulator.py <results folder> [model ...]
python tools/plot_results.py <results folder>
```

Run the runner first, then the simulator, then the plotter, because the plotter reads the simulator output.

The simulator draws random batches of programs, all arriving at once on one CPU, and executes them in three orders: FIFO, ordered by predicted burst, and ordered by true burst (the oracle). It uses the saved out-of-fold predictions of the `primary` feature set at its default configuration. Without model names it processes every model found in the folder.

| Column | Meaning |
| --- | --- |
| `wait_fifo`, `wait_model`, `wait_oracle` | Average waiting time in each order |
| `wait_cut_pct` | Reduction of the average wait compared with FIFO |
| `oracle_pct` | Share of the oracle's improvement that the model achieves. 100 means the predictions are as good as knowing the true burst times. |
| `oracle_pct_std` | Standard deviation of `oracle_pct` over seeds |

`sjf_workloads.csv` repeats the measurement for batches of 5, 10, 20 and 50 programs. `sjf_configurations.csv` covers every feature set and sweep configuration at a batch size of 20.

`plot_results.py` writes:

- `by_features.png` and `by_settings.png` for each model
- `model_comparison.png`, all models at the default configuration
- `feature_comparison.png`, all models across feature sets

## Adding a model family

Create a file in `models/`. It is discovered automatically; no registration is needed.

```python
from sklearn.ensemble import AdaBoostRegressor

from models.base import BurstModel


class AdaBoostModel(BurstModel):
    family = "ada_boost"
    estimator_class = AdaBoostRegressor
    settings = {"n_estimators": 50}
    grid = {"n_estimators": [10, 25, 50, 100], "learning_rate": [0.1, 0.5, 1.0]}
```

The class attributes:

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

A file that fails to import is reported as a warning on stderr and skipped; the other families keep working.

## Project layout

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
tools/
  corpus.py                 locates the programs of the corpus
  gen_synth.py              generates the synthetic C programs
  extract_features.py       LLVM static feature extraction
  collect_labels.py         measures burst times (macos, linux, contended)
  build_training_set.py     merges features and labels
  select_features.py        feature ranking and best subsets
  sjf_simulator.py          scheduling simulation
  plot_results.py           comparison charts
```

On the `main` branch the generated and local material (`corpus/`, `dataset/`, `configs/`, `models/results/`) is listed in `.gitignore`, so the tool can be used on its own.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | The run finished but at least one model failed. The other models are still saved. |
| 2 | Configuration or input error, reported as `error: ...` on stderr |
| 130 | Interrupted |

## Troubleshooting

- `training set ... not found`: run `tools/build_training_set.py` for that dataset, or point `data.training_set` at the right file.
- `feature subsets ... not found`: run `tools/select_features.py`, or set `data.subsets`.
- `unknown model family`: the message lists the available families and any file in `models/` that failed to load.
- `unknown feature set`: use `best2` to `best9`, `all`, `history`, or a `+` combination. `history` exists only when the training set has history columns.
- `clang`, `opt` or `llvm-link` not found: install LLVM and make sure it is on `PATH`.
- A `ridge` or `svr` run on the `all` feature set can print overflow warnings or produce extreme predictions, because the 30 features are strongly redundant. Use a `best` subset or a tree-based family. Convergence warnings from `mlp` are suppressed.
