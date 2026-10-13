#!/usr/bin/env python3
"""v1 label collector -- RUN INSIDE THE LINUX VM (lima/ubuntu).

Collects, per corpus program:
  Tier 2b (execution history):  utime, stime, maxrss, minflt, majflt,
                                voluntary + involuntary context switches
                                (nvcsw is actually populated on Linux, unlike
                                macOS which returned 0)
  Tier 2a (OS scheduling context, as an INJECTED experimental knob):
                                we launch each program under a grid of
                                nice values x scheduling policies, and record
                                what we set. For our controlled corpus these
                                are injected (not intrinsic), so the question
                                is: does burst behavior shift with priority?

Writes dataset/labels_linux.csv  -- does NOT touch labels_macos.csv.

Paths resolve relative to this script, so it works wherever lima mounts the
repo (lima shares $HOME by default -> same path inside the VM).

Requires: clang or gcc on PATH inside the VM.  (apt install clang)
"""

import csv
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
BIN = ROOT / "dataset" / "_linux_bin"

CC = shutil.which("clang") or shutil.which("gcc")
REPEATS = 5

# Tier-2a experimental grid: (label, nice, policy). SCHED_OTHER=0 is normal
# CFS; SCHED_BATCH=3 hints "non-interactive"; SCHED_IDLE=5 is lowest.
SCHED_OTHER, SCHED_BATCH, SCHED_IDLE = 0, 3, 5
POLICY_NAME = {SCHED_OTHER: "OTHER", SCHED_BATCH: "BATCH", SCHED_IDLE: "IDLE"}
GRID = [
    ("nice0_other", 0, SCHED_OTHER),
    ("nice10_other", 10, SCHED_OTHER),
    ("nice0_batch", 0, SCHED_BATCH),
    ("nice0_idle", 0, SCHED_IDLE),
]
ARGC_VARIANTS = [1, 5, 9]  # input variation, same idea as v0


def compile_native(pid, cfiles, extra_flags):
    exe = BIN / pid
    r = subprocess.run([CC, "-O1", "-o", str(exe)] +
                       [str(f) for f in cfiles] + extra_flags,
                       capture_output=True, text=True)
    return exe if r.returncode == 0 else None


def run_once(exe, argc, nice_val, policy):
    """Fork; child sets nice+policy then execs; parent wait4s for rusage."""
    args = [str(exe)] + ["x"] * (argc - 1)
    pid = os.fork()
    if pid == 0:  # child
        try:
            os.sched_setscheduler(0, policy,
                                  os.sched_param(0))  # prio 0 for OTHER/BATCH/IDLE
        except (PermissionError, OSError):
            pass
        try:
            if policy == SCHED_OTHER:
                os.nice(nice_val)
        except OSError:
            pass
        os.execv(str(exe), args)
        os._exit(127)
    _, status, ru = os.wait4(pid, 0)
    if os.waitstatus_to_exitcode(status) < 0:
        return None
    return ru


def measure(exe, argc, nice_val, policy):
    runs = []
    for _ in range(REPEATS):
        ru = run_once(exe, argc, nice_val, policy)
        if ru is None:
            return None
        runs.append(ru)
    med = lambda attr: statistics.median(getattr(r, attr) for r in runs)
    return {
        "cpu_s_median": round(med("ru_utime"), 6),
        "sys_s_median": round(med("ru_stime"), 6),
        "maxrss_kb": int(med("ru_maxrss")),
        "minflt": int(med("ru_minflt")),
        "majflt": int(med("ru_majflt")),
        "vol_ctxsw": int(med("ru_nvcsw")),
        "invol_ctxsw": int(med("ru_nivcsw")),
    }


def main():
    if CC is None:
        sys.exit("no clang/gcc found -- run `sudo apt install clang` in the VM")
    BIN.mkdir(parents=True, exist_ok=True)

    jobs = []
    for f in sorted((CORPUS / "synthetic").glob("*.c")):
        jobs.append((f.stem, "synthetic", [f], []))
    for cat in ["kernel", "sequential", "app", "test"]:
        base = CORPUS / "tacle-bench" / "bench" / cat
        if base.exists():
            for d in sorted(base.iterdir()):
                if d.is_dir() and list(d.glob("*.c")):
                    jobs.append(("tacle_" + d.name, "taclebench",
                                 sorted(d.glob("*.c")), ["-I" + str(d)]))

    rows, skipped = [], []
    for i, (pid, source, cfiles, flags) in enumerate(jobs):
        exe = compile_native(pid, cfiles, flags)
        if exe is None:
            skipped.append((pid, "compile"))
            continue
        variants = ARGC_VARIANTS if source == "synthetic" else [1]
        for argc in variants:
            for gname, nice_val, policy in GRID:
                m = measure(exe, argc, nice_val, policy)
                if m is None:
                    skipped.append((pid, "%s/argc%d" % (gname, argc)))
                    continue
                rows.append({"id": pid, "source": source, "argc": argc,
                             "sched_grid": gname, "nice": nice_val,
                             "policy": POLICY_NAME[policy], **m})
        if (i + 1) % 50 == 0:
            print("  %d/%d programs" % (i + 1, len(jobs)), file=sys.stderr)

    out = ROOT / "dataset" / "labels_linux.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote %d rows -> %s" % (len(rows), out))
    print("  (%d programs x %d sched-grid x input-variants)" %
          (len(jobs), len(GRID)))
    if skipped:
        print("skipped %d: %s" % (len(skipped), skipped[:8]))


if __name__ == "__main__":
    main()
