#!/usr/bin/env python3
"""v0 label collector (macOS, native).

Because the corpus is I/O-free, one program execution == one CPU burst, so
per-run CPU time is the correct burst label for this corpus.

Method: compile native -O1, run R times per input variant, take the median of
child ru_utime (user CPU seconds via os.wait4 — robust to background load).
Synthetic programs get input variation via extra argv (argc feeds their LCG
seed and 'dyn' trip counts). Embench is skipped in v0 (needs its support
harness to produce a runnable; TACLeBench + synthetic have their own main).

Output: dataset/labels_macos.csv  (id, variant, argc, cpu_s_median, cpu_s_all)
"""

import csv
import os
import statistics
import subprocess
import sys
from pathlib import Path

LLVM = Path("/opt/homebrew/opt/llvm/bin")
ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
BIN = Path("/private/tmp/claude-501/-Users-davidstan-Documents-Projects-mox-TinyML"
           "/70c85ea3-b58a-46c5-b3ea-de1b9b4b9085/scratchpad/bin")

REPEATS = 5
TIMEOUT_S = 20
ARGC_VARIANTS = [1, 3, 5, 7, 9]  # number of argv entries incl. program name


def compile_native(pid, cfiles, extra_flags):
    exe = BIN / pid
    r = subprocess.run(
        [str(LLVM / "clang"), "-O1", "-o", str(exe)] +
        [str(f) for f in cfiles] + extra_flags,
        capture_output=True, text=True)
    return exe if r.returncode == 0 else None


def time_once(exe, argc):
    """Run once, return child user-CPU seconds via wait4, or None."""
    args = [str(exe)] + ["x"] * (argc - 1)
    try:
        pid = os.posix_spawn(str(exe), args, os.environ)
    except OSError:
        return None
    try:
        _, status, ru = os.wait4(pid, 0)
    except ChildProcessError:
        return None
    if os.waitstatus_to_exitcode(status) < 0:  # killed by signal
        return None
    return ru.ru_utime


def measure(pid, exe, argc):
    vals = []
    for _ in range(REPEATS):
        t = time_once(exe, argc)
        if t is None:
            return None
        vals.append(t)
    return vals


def main():
    BIN.mkdir(parents=True, exist_ok=True)
    rows, skipped = [], []

    jobs = []
    for f in sorted((CORPUS / "synthetic").glob("*.c")):
        jobs.append((f.stem, "synthetic", [f], [], ARGC_VARIANTS))
    for cat in ["kernel", "sequential", "app", "test"]:
        for d in sorted((CORPUS / "tacle-bench" / "bench" / cat).iterdir()):
            if d.is_dir() and list(d.glob("*.c")):
                jobs.append(("tacle_" + d.name, "taclebench",
                             sorted(d.glob("*.c")), ["-I" + str(d)], [1]))

    for i, (pid, source, cfiles, flags, variants) in enumerate(jobs):
        exe = compile_native(pid, cfiles, flags)
        if exe is None:
            skipped.append((pid, "compile"))
            continue
        for argc in variants:
            vals = measure(pid, exe, argc)
            if vals is None:
                skipped.append((pid, "run@argc%d" % argc))
                continue
            rows.append({
                "id": pid, "source": source, "argc": argc,
                "cpu_s_median": round(statistics.median(vals), 6),
                "cpu_s_min": round(min(vals), 6),
                "cpu_s_max": round(max(vals), 6),
            })
        if (i + 1) % 50 == 0:
            print("  %d/%d programs done" % (i + 1, len(jobs)), file=sys.stderr)

    out = ROOT / "dataset" / "labels_macos.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote %d label rows -> %s" % (len(rows), out))
    if skipped:
        print("skipped %d: %s" % (len(skipped), skipped[:8]))


if __name__ == "__main__":
    main()
