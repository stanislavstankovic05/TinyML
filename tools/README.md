# Tools

Helper scripts that sit around the runner: they build datasets, select features, simulate scheduling from saved predictions and plot results. The runner does not depend on them, it only needs a training set CSV.

Some of these scripts belong to the project on the `cpu-burst` branch and are marked in the table at the end. The others are general.

All commands run from the repository root. Intermediate and output files go to `dataset/`.

## Contents

- [Requirements](#requirements)
- [Pipeline](#pipeline)
- [Corpus](#corpus)
- [Static features](#static-features)
- [Labels](#labels)
- [Training set](#training-set)
- [Feature selection](#feature-selection)
- [Scheduling simulation](#scheduling-simulation)
- [Plots](#plots)
- [Scripts](#scripts)

## Requirements

- The Python packages in `requirements.txt`, plus matplotlib
- LLVM with `clang`, `opt` and `llvm-link` (developed on LLVM 22), for feature extraction
- git, to fetch the benchmark suites
- A Linux machine or virtual machine for the Linux and contended labels, for example [Lima](https://lima-vm.io) on macOS

```bash
pip install matplotlib
brew install llvm            # macOS
sudo apt install llvm clang  # Debian and Ubuntu
```

`extract_features.py` looks for the LLVM tools in the Homebrew location first and then on `PATH`, including versioned names such as `clang-18`.

## Pipeline

```
corpus -> extract_features -> collect_labels -> build_training_set -> select_features
                                                        |                   |
                                                        v                   v
                                                 runner.py  <------ best_subsets.csv
                                                        |
                                                        v
                                         sjf_simulator -> plot_results
```

## Corpus

Programs live under `corpus/`:

| Source | Role | Link |
| --- | --- | --- |
| TACLeBench | Features and labels | [github.com/tacle/tacle-bench](https://github.com/tacle/tacle-bench) |
| Embench IoT | Features only, these programs are not run | [github.com/embench/embench-iot](https://github.com/embench/embench-iot) |
| Synthetic | Features and labels, generated | `corpus/synthetic/` |

```bash
mkdir -p corpus
git clone https://github.com/tacle/tacle-bench corpus/tacle-bench
git clone https://github.com/embench/embench-iot corpus/embench-iot
python tools/gen_synth.py 320
```

`gen_synth.py` writes the synthetic programs and a `manifest.csv` to `corpus/synthetic/`. The count defaults to 320 and the generator is seeded, so the output is reproducible.

## Static features

```bash
python tools/extract_features.py
python tools/extract_features.py dataset/features_linux.csv
```

Compiles every program at `-O1`, runs the LLVM analysis printers and writes one row of 30 features per program to `dataset/features.csv`. The optional argument sets the output file.

The `linux` dataset reads `dataset/features_linux.csv` and the `macos` dataset reads `dataset/features.csv`. Run the extractor in the environment that matches the labels, because target dependent features such as instruction cost differ between platforms.

## Labels

```bash
python tools/collect_labels.py macos
python tools/collect_labels.py linux
python tools/collect_labels.py contended
```

| Collector | Output | What it measures |
| --- | --- | --- |
| `macos` | `dataset/labels_macos.csv` | CPU time of each program running alone, for several inputs |
| `linux` | `dataset/labels_linux.csv` | CPU time, system time, peak memory, page faults and context switches under four scheduling settings (normal, nice 10, batch, idle). Run it inside a Linux machine. |
| `contended` | `dataset/labels_contended.csv` | Batches of 8 programs pinned to one CPU and run at the same time, recording real turnaround and waiting time |

macOS has no history features and no memory column. The Linux machine must be able to read the repository, for example through a shared mount.

## Training set

```bash
python tools/build_training_set.py
python tools/build_training_set.py linux
```

Merges features with labels and writes `dataset/<name>/training_set.csv` for the datasets `linux` and `macos`. The target is the median CPU time. For the Linux dataset one earlier run per program becomes the history features and the remaining runs form the target.

## Feature selection

```bash
python tools/select_features.py
python tools/select_features.py linux
```

Ranks features by relevance to the target and redundancy with each other (mRMR), then searches every combination of each size from 2 to 9. Output in `dataset/<name>/`:

| File | Content |
| --- | --- |
| `feature_relevance.csv` | Correlation of each feature with the target |
| `feature_redundancy_pairs.csv`, `feature_pairwise_full.csv` | Correlation between features |
| `mrmr_ranking.csv` | mRMR ranking |
| `best_subsets.csv` | Best subset for each size, read by the runner |
| `plots/` | Correlation heatmap and feature versus target grid |

## Scheduling simulation

```bash
python tools/sjf_simulator.py <results folder> [model ...]
```

Run it on a folder written by the runner. It draws random batches of programs, all ready at once on one CPU, and executes them in three orders: first come first served (FIFO), ordered by predicted burst, and ordered by true burst (the oracle). It uses the saved out-of-fold predictions of the `primary` feature set at its default configuration. Without model names it processes every model in the folder.

Written per model: `sjf_workloads.csv` (batches of 5, 10, 20 and 50) and `sjf_configurations.csv` (every feature set and sweep configuration at a batch size of 20). Written to the folder: `sjf_models.csv`.

| Column | Meaning |
| --- | --- |
| `wait_fifo`, `wait_model`, `wait_oracle` | Average waiting time in each order |
| `wait_cut_pct` | Reduction of the average wait compared with FIFO |
| `oracle_pct` | Share of the oracle's improvement that the model achieves. 100 means the predictions are as good as knowing the true burst times. |
| `oracle_pct_std` | Standard deviation of `oracle_pct` over seeds |

The oracle is the optimal order for average waiting time when all jobs are ready at once on one CPU. It is a reference, not a model.

## Plots

```bash
python tools/plot_results.py <results folder>
```

Run it after the simulator, because it reads the simulator output. It writes:

- `by_features.png` and `by_settings.png` for each model
- `model_comparison.png`, all models at the default configuration
- `feature_comparison.png`, all models across feature sets

## Scripts

| Script | Purpose |
| --- | --- |
| `select_features.py` | Feature ranking and best subsets, general |
| `plot_results.py` | Comparison charts of runner results, general |
| `corpus.py` | Locates the programs of the corpus, `cpu-burst` |
| `gen_synth.py` | Generates the synthetic C programs, `cpu-burst` |
| `extract_features.py` | LLVM static feature extraction, `cpu-burst` |
| `collect_labels.py` | Measures run times, `cpu-burst` |
| `build_training_set.py` | Merges features and labels into training sets, `cpu-burst` |
| `sjf_simulator.py` | Scheduling simulation from saved predictions, `cpu-burst` |
