# Feature Notes — TinyML-in-Kernel Project

Status snapshot of decisions made so far. Two target problems, both placed on
existing eBPF mechanisms rather than raw kernel patching.

## Placement (confirmed)

| Problem | Kernel mechanism | Notes |
|---|---|---|
| CPU burst-time prediction | `sched_ext` (Linux 6.12+, eBPF-pluggable scheduler class) | Meta has informally experimented with ML burst prediction here; no full published framework yet — this is the more open gap of the two. |
| Page replacement / eviction | `cache_ext` (SOSP '25, eBPF `struct_ops` framework, [github.com/cache-ext/cache_ext](https://github.com/cache-ext/cache_ext)) | Space is more crowded: `LearnedCache` (perceptron, built directly on `cache_ext`), `ML-CLOCK`, and "Cache is King" all already exist here. |

Models shortlisted for both problems: **decision tree / random forest**, and **MLP**.

---

# Problem 1 — CPU Burst-Time Prediction

Two-tier design. Tier 1 = static, extracted once at compile time, available
immediately (solves cold start). Tier 2 = dynamic, accumulated at runtime,
blended in as execution history builds.

## TIER 1 — AGREED static features (LLVM, compile-time, one-time cost)

### Control flow / structure
| Feature | LLVM source | What it tells us |
|---|---|---|
| Loop count | `LoopInfo` | How much repeated work exists |
| Max loop nesting depth | `LoopInfo` | Multiplicative work amplification (nested = worse) |
| Recursion presence | Call-graph SCC (Tarjan) | Unbounded/hard-to-bound execution depth |
| Max call-graph depth | Call graph | How deep the work fans out |
| Cyclomatic complexity | CFG edge/node count | Branchiness — proxy for path unpredictability |
| Static instruction count | IR instruction count per function | Raw size / rough work proxy |
| Static loop trip counts | `ScalarEvolution` (SCEV) | Exact iteration counts where statically resolvable |

### Cost & frequency (LLVM computes these already — stronger than raw counts)
| Feature | LLVM source | What it tells us |
|---|---|---|
| Block execution frequency | `BlockFrequencyInfo` | Statically estimated **relative execution frequency per basic block** — the static equivalent of profiling. Stronger single signal than loop/cyclomatic counts. |
| Target-aware cost estimate | `TargetTransformInfo` (TTI) `getInstructionCost`, summed and weighted by `BlockFrequencyInfo` | A free, rough, **per-target static WCET-ish number**. LLVM ships the per-instruction cost model per backend — no simulator to build. |

### Memory
| Feature | LLVM source | What it tells us |
|---|---|---|
| Memory access pattern | `ScalarEvolution` | Affine/strided (`a[i]`) vs pointer-chasing — predicts cache behavior |
| Stack frame size | Sum of `alloca` sizes | Memory footprint — **directly relevant given kilobyte-scale MCU SRAM** |

### Instruction mix
| Feature | LLVM source | What it tells us |
|---|---|---|
| Opcode histogram | IR opcode counts: loads, stores, int arith, FP, compare/branch, GEP | Cheap bag-of-instruction-types vector; tabular-model friendly (good for decision trees) |

## TIER 2 splits into TWO kinds (important distinction, 2026-07-20)

Runtime features are not one bucket. Two sub-tiers with different
availability:

### Tier 2a — OS scheduling context (runtime, but available AT DISPATCH)
Exists the moment a task hits the runqueue. **No execution history needed**,
no "first run" problem. This is what a real scheduler actually reads, and
**we cannot get it from compilation** — but eBPF/`sched_ext` reads it
directly from `task_struct`, so it's accessible later, cheaply. Confirmed
Linux `task_struct` scheduler fields:
- **nice** (−20…+19), **static_prio**, **prio** (effective priority)
- **sched_class / policy**: SCHED_DEADLINE > FIFO/RR > OTHER(CFS) > BATCH > IDLE
- **vruntime** — accumulated weighted CPU time (CFS core signal)
- **kernel vs userspace** thread (`PF_KTHREAD`) — the kernel/user split
- cgroup membership, CPU affinity mask, RT priority, thread count
Framing: Tier 1 = *what the code is*; Tier 2a = *how the OS treats it now*;
Tier 2b = *what it did last time*.

### Tier 2b — Execution history (runtime, needs prior runs)
The historical-burst family below. Unavailable on first run — the reason
Tier 1 exists (cold start).

From the grid-computing ML burst-prediction literature (Helmy et al.,
GWA-T-4 AuverGrid trace). **Note: these come from grid computing — needs
translation to the MCU/embedded context.**

| Feature | What it tells us | MCU translation note |
|---|---|---|
| Historical burst average | Classic OS baseline: τₙ₊₁ = α·tₙ + (1−α)τₙ | Direct — this is the baseline we must beat |
| `UsedMemory` | Memory consumed per process | Direct |
| `ReqTime` | Requested/estimated execution time | Maps to task deadline/period in RTOS |
| `SubmitTime` | When process entered the queue | Maps to task arrival/release time |
| `NProcs` | Number of allocated processors | **Likely drop** — single-core MCU target |

Literature models tried: KNN, SVM, Decision Tree, Random Forest, ANN, XGBoost.
**Random Forest and KNN consistently outperformed**; burst time correlated
strongly with used CPU time and memory specifically.

---

## AVAILABLE but NOT selected — LLVM analyses we could add later

### Control flow
- **Basic block count / CFG edge count** — raw structural size, very cheap
- **Irreducible control flow presence** — loops entered from multiple points (`goto`-heavy); red flag for unpredictable timing
- **Indirect call / indirect branch count** — function pointers, virtual dispatch, jump tables; count itself measures "how predictable is this function"
- **`BranchProbabilityInfo`** — per-branch static probability heuristics (loop exits unlikely, null checks unlikely). Feeds `BlockFrequencyInfo`, so partly already captured.

### Memory / dependencies
- **Alias analysis (basic-AA / TBAA)** — whether pointers may alias; gates vectorizability, indicates memory-access predictability
- **`DependenceAnalysis`** — loop-carried dependencies; are iterations independent or chained
- **Global / TLS variable touch count** — does the function read/write shared state (side-effect indicator)

### Parallelism
- **Loop Vectorizer legality + width** — is a loop vectorizable and at what width, without actually vectorizing. *Low value on Cortex-M0+ (no SIMD)* — relevant only if we port to a beefier target.

### Function attributes (LLVM infers these for free during optimization)
- **`readnone` / `readonly`** — pure / no-write functions; easier to predict and reorder
- **`nounwind`** — no exception handling in this path
- **Leaf-function flag** — calls nothing; trivially bounds analysis depth
- **Known library call presence** (`malloc`, `memcpy`, `memset`) — known, often size-dependent costs; can be modelled separately from user code
- **Exception handling presence** (`invoke` / `landingpad`) — adds unpredictability. *Less relevant on bare-metal MCU without C++ exceptions.*

### If profile data ever becomes available
- **PGO `!prof` branch-weight metadata** — real profile runs attach measured branch weights directly onto IR. Upgrades `BlockFrequencyInfo` from heuristic guess to measured. **Natural bridge between Tier 1 and Tier 2** — still attached statically to the IR, but informed by a previous real run.

---

## Design rationale & open items

**Why two tiers:** purely dynamic/historical features are unavailable on a
process's first invocation (cold start). Static features cost nothing at
decision time (one-time compile cost) and cover exactly that gap; dynamic
features then refine the prediction as history accumulates.

**Feature count is a cost, not free.** Every added feature grows the model's
input layer → more MACs per inference → directly worse on the crossover curve
this thesis is measuring. Start narrow, add only features that earn their
keep. This is why the "available but not selected" list stays unselected.

**Closest prior art — must be cited, not treated as untouched ground:**
[PrETi](https://arxiv.org/abs/2503.13679) (Xu et al. 2025, Kiel University +
Mercedes-Benz). LLVM passes instrument the IR to *simulate* execution
(instruction counts, simulated data-cache hits/misses, simulated 2-bit branch
predictor), producing features combined with historical timing data, fed to
ML regression to predict function execution time before hardware measurement.
Validated on an **Infineon Aurix TC387** (automotive MCU) — close to our
hardware space.

Two concrete differences from our idea (this is the framing to use — not
"nobody has done this"):
1. **Feature type**: PrETi's features require *running a simulator* over the
   LLVM IR (cache/branch simulation) — heavier one-time cost. Ours are plain
   structural graph metrics + LLVM's built-in analyses — no simulation.
2. **System framing**: PrETi is an **offline, development-time** tool — used
   during CI/testing, feeding a separate static scheduling-analysis pipeline.
   It is not live inside a scheduler. Our two-tier design (static features
   for cold start, blended with accumulating runtime history at every actual
   dispatch decision, live inside `sched_ext`) was not found in the search
   pass — this is the part of the pitch that still holds.

Other precedent: MilepostGCC (ML-guided compiler heuristics from static
program features), Ithemal (ML cost model for x86 basic blocks), static WCET
analysis (aiT).

**Open implementation question (noted, not solved):** since placement is
`sched_ext` (eBPF), static metadata must reach the in-kernel program — likely
embedded in an ELF section at compile time, loaded into a BPF map keyed by
binary/process identity at `execve`.

**Status: burst prediction feature set CLOSED for now.**

---

# Feature Selection Methodology

The approach we want is a named, citable method: **mRMR (minimum Redundancy
Maximum Relevance)**, [Peng, Long & Ding, IEEE TPAMI 2005](https://pubmed.ncbi.nlm.nih.gov/16119262/).
Point 4 below is a separate named problem: **cost-sensitive / budgeted
feature selection**.

## 1. Relevance (feature ↔ burst time)

- **Pearson** — linear only. KML used it. Will miss non-linear relations
  (nesting depth is likely multiplicative, not linear).
- **Spearman** — rank/monotonic, tolerates non-linearity. Better default.
- **Mutual information** (`mutual_info_regression`) — captures *any*
  dependency. **Primary measure**; mRMR is built on it.
- **Permutation importance** — shuffle a feature, measure degradation.
  Most honest "does it earn its place" test. KML used this.
- **SHAP** — per-feature contribution + direction. MicroSchedNet used it.

→ Use MI for mRMR ranking, permutation importance as final sanity check.

## 2. Redundancy (feature ↔ feature)

- **Spearman/Pearson correlation matrix** — cheap first pass
- **Pairwise mutual information** — catches non-linear redundancy
- **VIF (Variance Inflation Factor)** — catches *group* multicollinearity,
  e.g. f₃ ≈ f₁ + f₂, which pairwise correlation misses entirely. **Likely
  relevant here**: instruction count vs block count vs cyclomatic complexity.

**Critical nuance — redundancy tolerance is model-dependent:**
- **Trees / random forests tolerate correlated features** — they just pick
  one at each split. Little accuracy cost.
- **MLPs / linear models suffer** — collinearity destabilizes weights.
- **Trap**: correlated features *split* their importance in tree-based
  importance measures, making both look weak when jointly strong. Don't drop
  on low tree-importance alone if features are correlated with each other.

→ We may end up with **two different optimal feature sets**, one per model
family. That's a legitimate finding, not a problem.

## 3. Selecting m relevant + independent features

mRMR greedy criterion per candidate feature f:

```
score(f) = MI(f ; burst_time)  −  (1/|S|) · Σ MI(f ; s)   for s already in S
           └── relevance ──┘         └──── redundancy ────┘
```

Alternatives: **RFE** (train, drop weakest, repeat), **Lasso/L1** (zeroes
redundant features), **Boruta** (shadow features), **CFS**.

**Practical point at our scale:** optimal subset selection is NP-hard in
general (2ⁿ subsets) — that's *why* mRMR is greedy. But with n ≈ 12–15,
2¹⁵ ≈ 32,768 subsets is trivially exhaustible on a laptop. **We can do
exhaustive search and get the genuinely optimal subset at each m.** Use mRMR
to rank/sanity-check, but don't settle for greedy's approximation when the
exact answer is affordable. Defensible methodological detail for the thesis.

## 4. Optimal m under cost — THIS IS THE THESIS

### (a) The two tiers have different cost structures — weight them differently

| Tier | Extraction cost | Marginal cost of one more feature |
|---|---|---|
| **Tier 1 (static LLVM)** | One-time at compile, amortized ≈0 per decision | Wider input vector (few MACs) + few bytes in BPF map. **Cheap.** |
| **Tier 2 (dynamic runtime)** | **Per decision, in the hot path** — maintain/update EMAs, deltas, counters on every event | Often **larger than the inference itself** |

→ A mildly-useful *static* feature may be worth keeping while an
equally-useful *dynamic* feature is not. Standard mRMR assumes uniform
feature cost; ours are not uniform. Cost-weighted criterion:

```
score(f) = [ relevance(f) − redundancy(f, S) ] / cost(f)
```

with `cost(f)` in **actual RP2040 cycles** = extraction cost + marginal
inference cost. This is [cost-sensitive feature selection](https://onlinelibrary.wiley.com/doi/abs/10.1002/sta4.427);
the tier asymmetry is a novel-ish wrinkle worth writing up.

### (b) TRAP: prediction accuracy ≠ system benefit

**Most important methodological point.** A 5% better burst prediction is
worth **zero** if it doesn't change which task the scheduler picks. Measure:

1. **Decision flips** — how often does the better prediction change the
   actual scheduling decision?
2. **Flip quality** — of those changes, how many were improvements?

LRB did exactly this with their **"good decision ratio"** metric instead of
raw prediction error. Adopt the same discipline.

### (c) The experimental procedure (= the thesis experiment)

1. Rank features by cost-weighted mRMR
2. For m = 1…n, train best model on top-m subset (exhaustive at our scale)
3. Measure **real inference cost** per m on RP2040 (GPIO-toggle method)
4. Measure prediction quality per m
5. **Convert to decision quality** — fraction of decisions changed, and
   whether better
6. Convert to the system metric that matters (energy, deadline misses,
   makespan)
7. Plot **net = benefit − cost vs m**. Peak = optimal m.
   **That curve IS the crossover result.**

## Two cheap wins to test early

- **Predict log(burst time), not raw.** Burst times are heavily right-skewed.
  LRB predicted `log(time-to-next-request)` for exactly this reason.
  Usually improves fit substantially at zero runtime cost.
- **We may not need regression at all.** The scheduler only needs *ordering*
  — "short/medium/long" may be enough. KML classified workload *types*;
  ALPS bucketed functions into 4 groups. Classification into 3–4 buckets is
  dramatically cheaper than regression and may lose nothing that matters.
  **Test early** — if it holds, it moves the whole crossover curve favourably.

---

# Data Plan (burst prediction)

**No ready-made dataset exists** pairing LLVM static features with measured
burst times — PrETi says so explicitly ("there is no publicly available large
dataset… training data is typically gathered shortly before the training
phase"). Timing labels are only valid per hardware+compiler config, so they
are inherently non-portable. **We build our own** — standard move, citable,
and the dataset becomes a thesis artifact.

What exists but is only half-usable:
- Grid/cluster traces (AuverGrid, Google, Azure) — durations but no source
  code → no LLVM features possible (Tier-2 only)
- BHive (Ithemal) — measured throughput, x86 basic blocks, not ARM/processes
- CodeComplex/CoRCoD — complexity classes, not times

**PrETi's dataset recipe (template to copy):** 1,348 samples =
`real_world` (60 algorithms → 766 test cases, representativeness) +
`simple_loop` (568 synthetic cases iterating rare operators — division etc. —
because real code's operator frequencies are too skewed to learn rare-op
costs from realistic code alone). Real + synthetic mix is the right idea.

## Corpus search results (2026-07 session)

- **[TACLeBench](https://github.com/tacle/tacle-bench)** — 102 programs, ANSI
  C99, **all self-contained: zero stdlib/OS dependencies** → trivial to
  compile bare-metal for RP2040 AND clean for LLVM analysis (no external
  calls muddying the call graph). Built by WCET community for timing research.
- **[Embench](https://github.com/embench/embench-iot)** — 19 real-world
  benchmarks sized for ≥64kB ROM/RAM embedded targets.
- **[ExeBench](https://github.com/jordiae/exebench)** (MAPS '22) — 700k
  *executable* C functions from GitHub with auto-generated IO examples.
  **Scale-up path** if 121 programs prove too few; labels measured by us.
- **[AnghaBench](https://ieeexplore.ieee.org/document/9370322/)** — 1M
  compilable but NOT executable C files. Only useful for feature-distribution
  statistics. Skip for now.
- **[IBM Project CodeNet](https://github.com/IBM/Project_CodeNet)** — 13.9M
  submissions with **CPU-runtime + memory metadata and inputs**. Wrong
  hardware/granularity for our labels, but a legitimate **pretraining /
  transfer-learning corpus** (train static→runtime-class at scale, fine-tune
  on our measured data). Optional.

**Official scheduling datasets — what they contain, and the key gap
(verified schemas, 2026-07-20):**
- **Google Borg 2019** ([schema](https://github.com/google/cluster-data/blob/master/ClusterData2019.md)):
  per-task priority, scheduling class, CPU/mem request limits, 5-min CPU-usage
  histograms, MapReduce parent-job links, constraints.
- **Alibaba 2018** ([schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/trace_2018.md)):
  job→task→instance DAG, plan_cpu/plan_mem requests, instance_num, start/end
  times, **inter-task dependencies** (a feature we don't have).
- **AuverGrid** (burst-prediction papers): SubmitTime, NProcs, UsedMemory, ReqTime.

**THE STRUCTURAL GAP (defensible novelty):** every official dataset has
priority + resource requests + timing, but **ZERO code structure** — jobs are
opaque, you can't compute loop depth from a Borg task. Our dataset is the
mirror image: rich code structure, no OS context yet. **No public dataset
has both Tier-1 (code structure) AND Tier-2a (OS priority/class).** Combining
them is a feature set the published datasets structurally cannot provide.

**Additional due-diligence pass (confirms no shortcut exists):**
- **[BHive](https://github.com/ithemal/bhive)** (Ithemal's dataset) — 300K x86-64
  basic blocks, real measured throughput, Haswell/Skylake/Ivy Bridge, public.
  Closest analog in spirit (code + real HW timing at scale) but wrong ISA,
  wrong granularity (block throughput ≠ scheduler-interrupted burst), wrong
  label semantic. **Not usable as final dataset, but see pilot idea below.**
- Alibaba Cluster Trace 2018, Google/Azure cluster traces, GWA-T-1/T-4 —
  real production scheduling durations, but **no source code** (opaque
  jobs/containers) → zero LLVM feature extraction possible. Tier-2-only.
- `sched_switch` tracing tooling (Perfetto, `schedviz`, LITMUS-RT
  feather-trace, `perf sched`) — these are the **standard tools**, not
  datasets; confirms our planned collection method matches what the field
  actually uses.
- MicroSchedNet — reconfirmed: no dataset or code release found anywhere.

**Pilot idea before committing to our own collection:** use BHive to sanity
-check the core assumption — do static features (or the LLVM TTI cost model)
actually correlate with real measured hardware timing at all — cheaply, on a
laptop, before spending effort on RP2040 data collection. Weak correlation
there = early warning; strong correlation = confidence boost. Not a
replacement dataset, a validation step.

**DECIDED: primary corpus = Embench + TACLeBench (~121 programs).** With
input variation and per-burst labeling (each run → many `sched_switch`
bursts), this yields thousands–tens of thousands of labeled samples — same
order as PrETi's 1,348.

## Pipeline

1. **Corpus**: **Embench + TACLeBench** (decided, above) + small
   parameterized synthetic generator (knobs: loop depth × trip count ×
   recursion × memory pattern) to fill feature-space corners.
   BEEBS/MiBench/PolyBench available as extras if needed.
2. **Tier-1 extraction**: our LLVM pass at compile time → one static feature
   vector per program.
3. **Labels**: a *burst* = on-CPU interval between blocking/preemption
   events, **not total runtime**. Collect via eBPF tracing of `sched_switch`
   while corpus runs. Each program → many burst samples; Tier-2 features
   evolve across them.
4. **Vary inputs** per binary — input-driven variation is what Tier-2
   history captures; must be present in the data.
5. **Split BY PROGRAM, not by sample** (GroupKFold). Same-program bursts in
   both train and test = leakage (model memorizes program identity).
   Held-out programs = exactly the cold-start test for Tier 1.
6. Log-transform labels, then train (models: DT/RF, MLP).

## BUILD STATUS (2026-07-19) — corpus + extraction DONE

- `corpus/embench-iot/` + `corpus/tacle-bench/` cloned; **76 real programs**
  compile clean to LLVM IR (19 Embench with `-DGLOBAL_SCALE_FACTOR=1
  -DCPU_MHZ=1 -DWARMUP_HEAT=1`; 57 TACLeBench kernel/sequential/app/test;
  3 `parallel` apps skipped for now).
- `tools/gen_synth.py` — synthetic generator, 8 knobs (loops, nest, trip,
  recursion, call_depth, branchiness, mem pattern, opcode mix);
  **320 programs** emitted to `corpus/synthetic/` + `manifest.csv` ground
  truth. All compile `-Wall -Werror`; computation survives `-O2` (volatile
  sink + LCG input dependence).
- `tools/extract_features.py` — compiles at **-O1**, runs LLVM 22 analysis
  printers (`print<loops>`, `print<scalar-evolution>`, `print<block-freq>`,
  `print<cost-model>` in one pipeline; `print-callgraph-sccs` separately —
  module pass can't join function-pass pipeline), parses IR text for
  CFG/opcodes/allocas/call graph. Output: **`dataset/features.csv`, 396 rows
  × 30 features**.
- **Validation vs synthetic ground truth: 516/516 checks pass**; nest-depth
  extraction exact (manifest 1/2/3/4 → extracted 1.00/2.00/3.00/4.00).

**Key design finding:** extracting at -O1 means features describe the binary
that runs, not the source. LLVM's tail-recursion elimination turns
tail-recursive functions into loops — so `direct`/`mutual` recursion knobs
legitimately extract as loops; only non-tail (`tree`) recursion survives as
recursion. Validation expectations were corrected accordingly. This is the
right choice (the scheduler sees the optimized binary) and worth a paragraph
in the thesis.

**Known preprocessing item:** `freq_weighted_insts` spans to ~1e12 on deeply
nested programs (BFI multiplies per nest level) → log-transform before
training.

## LABELS v0 (2026-07-19) — DONE, first model trained

**Key simplification:** corpus is I/O-free by construction → a program never
voluntarily blocks → **whole execution = one burst = total CPU time is the
correct label**. No eBPF/Linux needed for v0. Three-stage label plan:
- **v0 (done)**: macOS native, `ru_utime` via `os.wait4`, median of 5 runs,
  argv-driven input variation for synthetics. `tools/collect_labels_macos.py`
  → `dataset/labels_macos.csv`, **1,657 rows** (320 synth × 5 variants +
  57 TACLeBench), zero skips.
- **v1 (later)**: Linux VM (Lima/UTM) with `sched_switch` eBPF tracing —
  true burst semantics + `sched_ext` deployment leg.
- **v2 (thesis-grade)**: RP2040 bare-metal over UART — cycle-exact, no OS
  noise. TACLeBench + synthetics are stdlib-free → compile bare-metal clean.

**First model results (RF-300, GroupKFold BY PROGRAM, log-space target —
this is pure Tier-1 cold-start on never-seen programs, the hardest case):**
- held-out R² = 0.497, Spearman = 0.673
- **3-bucket (short/med/long) accuracy = 61.6% vs 33% chance** — the
  "classification instead of regression" idea has legs
- Top features: `log_fwi` (BFI-weighted insts) importance 0.59 — the
  "static equivalent of profiling" prediction was right; then bitops,
  bfi_max, tti_cost_sum. Structural counts (loops, cyclomatic) contribute
  little once fwi is present — redundancy in action, mRMR will prune.

**Caveats:** macOS/M-chip labels (exec noise floor ~1ms pollutes sub-ms
TACLeBench programs); no Tier-2 features yet (history should raise ceiling
substantially); labels are prototyping-grade, not thesis-grade.

## mRMR RESULT (2026-07-19) — first Tier-1-only feature ranking

`tools/feature_correlation.py` (relevance = mutual info, redundancy = full
pairwise Spearman matrix, `dataset/feature_pairwise_full.csv`) →
`tools/mrmr_rank.py` (greedy mRMR: score = relevance − avg redundancy w/
already-picked). Full ranking: `dataset/mrmr_ranking.csv`.

**Top 9 (score stays positive, natural cutoff — recommended shortlist):**
static_trip_loops, bitops, phis, branches, max_loop_depth, direct_recursion,
icmps, dyn_trip_loops, bb_count.

**Key finding:** `freq_weighted_insts` and `bfi_max` — ranked #1–2 by raw
correlation with target (0.66, 0.62) — drop to rank 24/27 in the mRMR
ranking, because they're 96–98% redundant with `max_loop_depth` (picked at
rank 5). Confirms the redundancy penalty is doing real work, not just
re-sorting relevance. `bitops` (unremarkable alone) jumps to #2 for the
opposite reason: decent relevance + almost zero overlap with what's already
picked.

**Note:** redundancy term uses Spearman correlation (already computed) as a
practical stand-in for mRMR's textbook pairwise-mutual-information — flag if
formalizing for the thesis write-up.

**Still open:** exhaustive-subset search on this reduced ~9-feature
candidate set (now tractable, unlike all 30) to find the true optimal m
rather than trusting greedy; cost-weighting by RP2040 cycles (Section 4a of
the methodology) not yet applied — this ranking is relevance/redundancy
only, no cost term yet.

## LABELS v1 (2026-07-20) — DONE, collected in Lima Ubuntu VM

Setup: Lima (Apache-2.0, CNCF) ARM64 Ubuntu, `vz`-accelerated. Mac home
mounted at real path `/Users/davidstan/...` but **read-only** → worked in
guest `~/tinyml`, copied CSVs back with `limactl copy`. VM has clang/LLVM 21
(Mac has 22). Ran `extract_features.py` + `collect_labels_linux.py` in-VM.
Outputs on Mac: `dataset/features_linux.csv`, `dataset/labels_linux.csv`
(4,068 rows = 377 programs × 4 sched-grid × input variants). macOS v0 files
untouched; full v0 set archived in `dataset/v0_macos_archive/`.

### Finding 1 — LLVM version changes the features (methodological)
clang-22 (mac) vs clang-21 (linux) features **NOT identical**: 40/396
programs differ on inst_count, 19 on bb_count, plus loop/cyclomatic/opcode
drift. Within one toolchain it's deterministic, but **the extraction
toolchain must be pinned and reported** in the thesis. Linux features pair
with Linux labels (same clang 21) → internally consistent.

### Finding 2 — Tier-2a (priority/policy) is FLAT on this corpus (predicted)
Burst time across the nice/policy grid is essentially identical:
nice0/nice10/BATCH/IDLE all mean ≈0.0030s, median ≈0.00058s. **nice/policy
affect WHEN you're scheduled, not total CPU work** — and on an uncontended
VM running one task at a time, priority is irrelevant to burst length.
→ Tier-2a scheduling-context features are **useless for burst prediction
UNLESS the workload has CPU contention** (multiple tasks competing). This is
a workload-design finding, not a failure: to make Tier-2a matter we must run
the corpus under contention (the realistic scheduler scenario).

### Finding 3 — Tier-2b context switches ≈ 0 (predicted)
vol_ctxsw always =1 (just the exit transition), invol_ctxsw mean 0.07. Our
pure-CPU no-blocking corpus generates ~no context switches. → context-switch
features are dead for this corpus; only meaningful with blocking/contended
workloads. The Tier-2b features that DO carry signal and are intrinsic:
memory (maxrss) and **historical burst average** (derived from repeat runs,
the classic OS baseline).

**Takeaway for feature strategy:** on the current single-task, non-blocking
corpus, the useful feature set is **Tier-1 (static) + Tier-2b history
(burst average, memory)**. Scheduling-context (Tier-2a) and context-switch
features need a *contended, multi-task* workload to have any signal — that's
the next workload-design decision if we want them.

## OPTION B — CONTENDED WORKLOAD (2026-07-20) — Tier-2a VINDICATED

`tools/collect_labels_contended.py` (in VM): batches of 8 corpus programs
launched simultaneously, ALL pinned to CPU 0 → real contention. Per slot a
policy/nice assigned (OTHER nice0/10/19 + SCHED_IDLE), decorrelated from
program identity. 400 batches → **3,200 task-observations**,
`dataset/labels_contended.csv`. Target of interest = TURNAROUND (wall-clock
to completion), not intrinsic burst.

**Confirmed the mechanism:**
- Intrinsic CPU work invariant to policy (IDLE vs OTHER medians identical)
  → Tier-1 predicts *work*, scheduling doesn't change it.
- Turnaround now monotonic in priority: OTHER-nice0 0.0058 → nice10 0.0077
  → nice19 0.0100 → IDLE 0.0109 (+88%, finishes last by design).
- Involuntary preemptions 1–10 (mean 2.1), up from ~0.07 uncontended.
- Spearman(turnaround): cpu_s 0.52, is_idle 0.28, nice 0.10 → BOTH tiers.

**THE BLENDING RESULT (predict log turnaround, RF, held-out programs):**
| Feature set | R² | Spearman |
|---|---|---|
| A) Tier-1 static only | 0.211 | 0.425 |
| B) + Tier-2a (policy, nice) | 0.314 | 0.578 |
| C) + system load (batch_total_cpu) | 0.554 | 0.714 |

Tier-2a lift: **+0.102 R²**. System-load context: **+0.240 R²**.
Tier-1-only 0.21 → all tiers 0.55.

**The finding (clean thesis story):** the OS-context features were not
useless — they were **conditionally useless**. Flat/dead on the uncontended
v1 corpus (Finding 2), they contribute real signal the moment CPU contention
exists (the realistic scheduler scenario). So the feature tiers have
*regimes*: Tier-1 governs intrinsic work always; Tier-2a + system-load
governs scheduling outcomes ONLY under load. This "when does each tier
matter" result is itself publishable and directly answers the user's
original priority/type-feature question empirically.

## SJF SIMULATION (2026-07-20) — CORE CLAIM DEMONSTRATED

`tools/sjf_simulation.py`. Closes the "prediction accuracy ≠ decision
quality" loop. Single-CPU non-preemptive, all ready at t=0; true burst =
uncontended cpu_s (labels_linux); pred burst = Tier-1 RF, out-of-fold
(honest cold-start); avg waiting time per task; 3000 workloads per size.

| K | avg_wait FIFO | SJF-pred | SJF-oracle | pred cuts FIFO by | oracle captured |
|---|---|---|---|---|---|
| 5 | 0.00582 | 0.00266 | 0.00136 | 54.4% | 71.0% |
| 10 | 0.01296 | 0.00602 | 0.00307 | 53.6% | 70.2% |
| 20 | 0.02742 | 0.01253 | 0.00653 | 54.3% | 71.3% |
| 50 | 0.07079 | 0.03265 | 0.01684 | 53.9% | 70.7% |

**Headline: static compile-time features alone, fed into SJF, cut average
waiting time ~54% vs FIFO and capture ~71% of the theoretical maximum
(perfect burst oracle).** Stable across workload size.

**Subtle but important:** "picked THE true-shortest first" drops 28%→1.4% as
K grows (5→50), yet wait-reduction holds ~54%. → SJF doesn't need the exact
argmin; approximate ordering (Spearman ~0.67) captures most of the benefit.
Decision-quality is about ordering, not exact-shortest ID. Good thesis nuance.

**Caveats:** idealized SJF (all ready t=0, 1 CPU, non-preemptive — real world
has arrivals/preemption/multicore); burst labels are VM prototyping-grade,
not RP2040; but the RELATIVE result (pred vs oracle vs FIFO) is what matters
and should transfer.

**On priority (clarified):** priority is ASSIGNED at launch, known at dispatch
for free (Tier-2a) — not discovered by running. SJF ignores priority anyway
(orders by burst). The contended/turnaround work still stands as proof
Tier-2a features carry signal under load, but it's separate from this core
SJF result.

## SUBSET × TIER-2 COMPARISON (2026-07-20) — big findings

`tools/subset_sjf_comparison.py`. Each best-N subset + all30, with/without
Tier-2. Tier-2 = leak-free history: prior-run burst (nice0_other/argc=1 row,
excluded from target) + its memory. K=20, 3000 workloads, identical draws.
Full table: `dataset/subset_sjf_comparison.csv`. (Note: all30 baseline reads
53.4%/69.9% here vs 54.3%/71.3% in sjf_simulation.py — target excludes the
history row here; internally consistent within this table.)

**Tier-1-only (wait-cut% / oracle-captured%):**
best2 44.0/57.5 · best5 49.3/64.6 · best7 55.1/72.1 · **best8 57.7/75.6** ·
best9 57.3/75.0 · all30 53.4/69.9

**Finding A — mRMR best-subsets are BAD predictors.** best2/3/4 have
*negative R²* (predict worse than the mean). The exhaustive best_subset
criterion optimized independence over relevance → loaded up on
direct_recursion/mutual_recursion (independent but ~zero signal). **The mRMR
set criterion picked the wrong objective for prediction.** Fix: relevance-
greedy top-k from the mutual-info ranking (static_trip_loops, phis, branches,
bb_count, cyclomatic_max...) instead. Citable methodological lesson.

**Finding B — best8 (8 feats) BEATS all30** (57.7 vs 53.4). Fewer well-chosen
features > full set; the extra 22 add noise. But the good subsets need the
high-relevance features back (m≥7).

**Finding C — Tier-2 history DOMINATES.** T2-only (2 feats: prior burst +
memory) = 70.3/92.1, beating the best static-only config (best8 75.6 oracle).
Two history features > thirty static. Adding T2 to anything saturates ~72/94:
best2+T2 (4 feats) = 70.3/92.0 ≈ all30+T2 (32 feats) = 72.2/94.5.

**Thesis mapping (clean):**
- Tier-2b history = king predictor (classic exp-average wisdom, quantified:
  2 feats → 92% oracle). The WARM-start story.
- Tier-1 static = the COLD-START story (its designed role): ~75% oracle with
  zero history, for never-seen programs.
- **Crossover win:** near-peak model is TINY — best2+T2 = 4 features → 92%
  oracle. Small model = low on-device inference cost = crossover favorable.

**NEXT:** (a) re-select Tier-1 by relevance-greedy top-k (fix Finding A),
(b) SRTF/arrivals/multicore SJF variants, (c) quantized integer 4-feature
model → RP2040 inference-cost (crossover curve — headline deliverable),
(d) sched_ext/eBPF deployment leg.

---

# Problem 2 — Page Replacement / Eviction

## Literature features — `LearnedCache` (perceptron on `cache_ext`)

Final feature set after discarding features that didn't generalize (e.g. raw
access counts, which were tracer-start-dependent):

- Delta time between last accesses of the page
- Delta time between last access of the inode
- Delta time between last 2 accesses of the inode (2nd- and 3rd-to-last)
- Distance from last access within the file
- File size in pages
- Relative exponential moving average (EMA) of page accesses (half-life 1s)
- Relative EMA of inode accesses
- *(training label, not an input feature)* Time from last access to eviction

Model: single-layer perceptron trained as a **Bradley-Terry pairwise ranker**
(score two candidate pages, evict the lower-scoring one). Features discretized
into 10 quantile bins + one-hot encoded.

**Key implementation detail — directly relevant to our integer-only core:**
eBPF forbids floating point. LearnedCache quantizes float weights into
fixed-point integers with a scale factor + zero-point. Same problem our MCU
core faces, already solved once for eBPF.

## Larger-scale precedent — LRB (NSDI '20, CDN caching)

Different domain, same idea. Feature design deliberately built to *subsume*
what classic heuristics already use:

- 32 "delta" features (time since 1st, 2nd, … 32nd-to-last access) — delta1
  alone reproduces LRU; sum of delta1..k reproduces LRU-K
- 10 exponentially-decayed counters (EDCs) at different decay rates
- Static features (object size, content type)

**Status: OPEN** — not finalized, revisit next session.

---

# Model Family Comparison (burst prediction, 2026-07-20) — SWITCH RECOMMENDED

7 model families, same 5-seed protocol, on best7 (9 static feats) and all30.
Full results: `dataset/model_comparison_best7.csv`,
`dataset/model_comparison_all30.csv`.

**best7 results (R² / Spearman / burst_err% / wait_cut% / oracle%):**
Ridge −0.06/0.52/74.7/50.2/66.2 · DT-depth4 0.05/0.53/69.9/54.8/72.2 ·
DT-depth8 −0.22/0.50/53.4/54.3/71.6 · **RF-300 (old default) 0.08/0.54/62.1/
55.9/73.6** · RF-20(tiny) 0.16/0.58/65.0/57.3/75.4 · **GradBoost-50small
0.18/0.58/66.6/58.3/76.7** · MLP(8-4) −0.66/0.57/72.1/55.1/72.5.

**DECISION: switch default model to small Gradient Boosting** (~50 shallow
trees, e.g. sklearn HistGradientBoostingRegressor max_iter=50 max_depth=4).
Beats RF-300 on every metric (76.7% vs 73.6% oracle) while being a fraction
of the size — pure win, not a tradeoff. Also MCU-friendly shape (fixed small
set of if/else comparisons, easier to hand-port to integer C than a 300-tree
forest).

**Also: RF-300 was oversized all along.** RF-20 (20 shallow trees) nearly
matches RF-300 (75.4 vs 73.6) at ~15x smaller — no accuracy was being bought
by the extra trees.

**Two caveats on record:**
- MLP scored worst (−0.66 R²) but with NO tuning on 377 samples — likely
  undertrained, not a real verdict. Revisit if MLP wanted specifically
  (quantizes cleanly for RP2040).
- Ridge on all30 got the single best oracle% (79.0%) despite R²=−3172
  (numerically broken from multicollinearity) — SJF only needs rank order,
  which survived (Spearman 0.61) even though magnitudes are nonsense. NOT
  deployable as-is; fixable with a larger regularization alpha. Interesting
  confirmation of the "ordering survives bad predictions" finding, not a
  recommendation.

**NEXT:** (a) retune MLP properly before ruling it out, (b) re-run
mRMR/best-subset selection using GradBoost instead of RF (feature ranking
may shift with the new model family), (c) quantized GradBoost or MLP →
RP2040 crossover measurement.

---

# Model Sweep Round 2 (2026-07-20) — NEW BEST MODEL, RF re-tuned, MLP verdict confirmed

Full results: `dataset/model_sweep_full.csv`. All on best7 (9 static feats),
5-seed protocol.

**RF sweep (16 configs, n_estimators x max_depth):** shallow wins decisively
— every depth=None config is at the BOTTOM. Best: **RF(n=100,depth=4) =
79.0% oracle**, R²=0.19 — big jump from old default RF(300,None)=73.6%.
Tree count barely matters (50/100/300 nearly identical); DEPTH was the
whole story. With 377 samples, unlimited depth overfits.

**MLP sweep (7 architectures x reg x early-stopping) — genuine underperform,
not an artifact.** Best after real tuning: MLP(16,8) alpha=0.1 = 62.1%
oracle, R² still negative (−0.38). Confirmed with early stopping, multiple
architectures, regularization sweep — not just bad defaults. **Verdict:
MLP underperforms trees on this dataset (377 samples, 9 features) — likely
insufficient data for a neural net to beat tree-based structure-finding.**

**NEW OVERALL BEST: ExtraTreesRegressor(100, depth=6) = 81.8% oracle**,
R²=0.16, Spearman=0.59. Beats every RF config, GradBoost, everything tried
to date.

**SVR has a distinct, valuable profile:** oracle=79.6% (close 2nd), but
**burst error only 23.3%** vs 60-70%+ for every tree model — dramatically
better-CALIBRATED absolute predictions even though ranking quality is
similar. If the raw predicted value is ever needed (not just ordering),
SVR is the honest choice over any tree model.

**KNN underperforms literature expectations** (grid-computing burst papers
found KNN was their best model) — here it tops out at 70.5% (k=15), behind
every tree method and SVR. Likely cause: code-structure features behave
differently in distance-space than grid-job resource features (memory,
submit time), or 377 samples/9 dims too sparse for KNN's metric. Real,
citable discrepancy — worth a sentence in the thesis, not silently dropped.

**Updated model recommendation:**
1. **ExtraTrees(100,d=6)** — best decision quality (81.8%). Ensemble of 100
   shallow trees — check RP2040 inference cost before committing (may be
   large next to GradBoost-50).
2. **SVR(rbf)** — best CALIBRATED magnitude (23% err), close decision
   quality (79.6%). Different tradeoff: fewer "parameters" (support vectors)
   but kernel evaluation may be expensive on MCU — needs cost check.
3. **RF(100,depth=4)** — 79.0%, straightforward to quantize/port (fixed
   shallow trees), good balance candidate.
4. GradBoost-50 (prior pick) — now confirmed 3rd-4th place, not the winner.
5. MLP, KNN — deprioritized for this feature set/dataset size.

**Still open, larger than any single model choice:** none of the above have
been checked against actual RP2040 inference cost. The best DECISION-quality
model (ExtraTrees, 100 trees) is not necessarily the best CROSSOVER model —
that's the multi-objective question the thesis is actually about. Model
choice should be finalized only after cost measurement, not before.

**NEXT:** (a) estimate/measure inference cost (cycles) for ExtraTrees(100,6)
vs SVR(rbf) vs RF(100,4) vs GradBoost-50 — the actual crossover-relevant
comparison, (b) quantize the winner to integer, (c) RP2040 measurement.

---

# Cost Calculation + Final Model Decision (2026-07-20)

**Correction:** best7 = 7 features (not 9 as mistakenly written earlier —
`m` in best_subsets.csv IS the feature count).

**Fresh-seed re-run (seeds 101/202/303/404/505, distinct from earlier 0-4)
confirmed RF and ExtraTrees are a STATISTICAL TIE on prediction quality:**
RF(100,d4) 80.2±1.9% oracle vs ExtraTrees(100,d6) 80.1±1.2% — gap smaller
than the noise. Earlier "ExtraTrees wins" (81.8 vs 79.0) was partly a lucky
seed draw on the original 0-4 set. GradBoost-50 78.1±1.5, SVR 79.1±1.9,
DecisionTree 73.5±2.4, KNN 69.9±0.6, Ridge 64.0±2.1, MLP 62.8±5.4 (worst
AND least stable even after real tuning).

**Cost calculation (operation-count proxy from REAL fitted models, not just
config caps — inspected actual tree depths/node counts and actual SVR
support-vector count):**

| Model | ops/inference (worst case) | Basis |
|---|---|---|
| RF(100,depth=4) | **~500** | 100 trees × depth-4 (confirmed actual, not just cap) = 400 comparisons + 100 additions. 2,880 nodes stored. Pure integer. |
| ExtraTrees(100,depth=6) | ~700 | 100×6=600 comparisons + 100 additions. 5,652 nodes stored (~2x RF memory). Pure integer. |
| SVR(rbf,C=1) | **~10,000–23,000** | 281 support vectors actually used (75% of 377 training samples — barely compressed). EACH needs a 7-dim distance calc (20 ops) + ONE `exp()` call. |

**Why SVR is disqualified for deployment despite best raw accuracy (22%
error, vs 65-70% for trees):** `exp()` is a transcendental function; RP2040
(Cortex-M0+) has NO FPU, no hardware transcendentals. Must be done in
software (lookup table/polynomial), realistically 15-60 cycle-equivalents
per call. × 281 calls = 20-45x more expensive than either tree model.
**Also disqualified for the eBPF/Linux leg** — eBPF forbids floating point
too, same wall.

**FINAL MODEL DECISION: RandomForest(100 trees, depth=4).** Ties
ExtraTrees on accuracy (statistically indistinguishable), costs 40% less
(500 vs 700 ops), and is far cheaper than SVR (20-45x) despite SVR's better
calibration. RF(100,4) is THE model going into quantization + RP2040
measurement.

**Note — these are proxy/estimated costs (integer-op counts from inspecting
real fitted models), not measured RP2040 cycles.** Real measurement (GPIO
toggle + logic analyzer, per the methodology section) still required before
any number goes in the thesis. This calculation's job was model SELECTION
before spending hardware time — done.

**burst_err_% clarified for the record:** median(|pred-true|/true × 100)
across programs — i.e. "for a typical program, prediction misses by this
% of the true value" (magnitude of miss, not direction). RF/ExtraTrees
~65-70% is real but tolerable BECAUSE SJF only needs ordering, not exact
value (established finding: decision quality survives large prediction
error). Partly inflated by VM label noise floor (17% of programs round to
0.000000s) — should shrink on RP2040 cycle-exact labels.

**NEXT:** (a) quantize RF(100,depth=4) to integer C (thresholds + feature
indices, no floats anywhere — trees are naturally quantization-friendly),
(b) port to RP2040, (c) GPIO-toggle cycle measurement — the actual
crossover curve.

---

# RF vs ExtraTrees by subset size (2026-07-20)

Full grid, both families x every best-N subset (2-9) + all30, 5 fresh seeds.
Table: `dataset/rf_vs_extratrees_by_subset.csv`.

Oracle % by subset size:
| m | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 9 | all30 |
|---|---|---|---|---|---|---|---|---|---|
| RF(100,d4) | 59.4 | 58.7 | 58.2 | 69.1 | 63.4 | **80.2** | 80.5 | 79.8 | 77.4 |
| ExtraTrees(100,d6) | 63.1 | 58.0 | 59.0 | 68.9 | 56.2 | **80.1** | 80.9 | 81.6 | 80.9 |

**Sharp cliff at m=7: jumps from ~58-69% (m=2-6) to ~80% (m=7+), both
families.** Confirms the earlier finding: small mRMR-selected subsets chase
independence over relevance (direct_recursion, mutual_recursion...) and stay
weak until the search pool is large enough to include genuinely relevant
features (branches, phis, cyclomatic_max — the ones ranked high by mutual
info, not by the flawed exhaustive-redundancy criterion). m=7,8,9 form a
tight plateau; all30 does NOT clearly beat them (RF even drops to 77.4 at
all30 — a real, if modest, redundancy cost at shallow depth that the
earlier deep/unlimited-depth RF experiment didn't show).

**Practical pick: best7.** Statistically tied with best8/best9/all30 on
oracle%, but cheapest to EXTRACT (7 LLVM analyses instead of 8/9/30) — note
this saves extraction cost specifically, not tree-traversal cost (that's
fixed by depth x n_trees regardless of candidate-pool size, since only
features actually split on cost anything at inference).

## Depth correction (2026-07-20): fine sweep finds depth=3, not depth=4

Original sweep only tested depth in {4,6,8,None} — coarse, missed the peak.
Fine sweep, every depth 1-20 + None, RF(100 trees) on best7, same 5-seed
protocol:

| depth | 1 | 2 | **3** | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 12 | 15 | 20 | None |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle % | 73.5 | 78.0 | **81.2** | 80.2 | 80.2 | 80.1 | 78.7 | 78.2 | 77.6 | 77.5 | 77.0 | 76.7 | 76.7 | 76.7 |
| est. ops | 200 | 300 | **400** | 500 | 600 | 700 | 800 | 900 | 1000 | 1100 | 1300 | 1587 | 1718 | 1723 |

**Depth 3 dominates on BOTH axes** — highest oracle% of anything tested to
date (81.2%, beats every earlier RF/ExtraTrees config) AND cheaper (~400
vs ~500 ops). Clean textbook overfitting curve: sharp rise 1→3, peak at 3,
smooth monotonic decay to a plateau at ~76.7% (depth ≥15 — the tree
naturally stops growing around real depth 16-17 regardless of the depth
cap, so "unlimited" isn't actually unlimited in practice for this data).
Full table: `dataset/rf_depth_finesweep.csv`.

**FINAL (corrected): RandomForest(100 trees, depth=3) on the best7 feature
set.** ~400 ops/inference, 81.2% oracle — the best result of the entire
project to date, on the cheapest RF config found.
