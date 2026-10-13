#!/usr/bin/env python3
"""Option B: CONTENDED multi-task labels -- RUN INSIDE THE LINUX VM.

Why: on an idle machine each task runs alone, so priority is irrelevant to
outcome (v1 Finding 2). Here we create real CPU contention -- batches of K
programs launched simultaneously, ALL pinned to a single CPU -- so the
scheduler must choose who runs, tasks get preempted, and priority/policy
genuinely shift TURNAROUND (when a task finishes).

Per task in a batch we record:
  cpu_s        intrinsic CPU work (Tier-1 predicts this; ~contention-invariant)
  turnaround_s wall-clock from batch launch to this task's completion
  wait_s       turnaround - cpu_s  (time spent NOT running = scheduling delay)
  invol_ctxsw  involuntary preemptions (now non-zero under contention)
  policy,nice  the Tier-2a knob we assigned (OTHER/IDLE, nice level)

Target of interest = turnaround_s / wait_s, where Tier-1 (work) + Tier-2a
(priority) should BEAT Tier-1 alone -- the point of the whole exercise.

Output: dataset/labels_contended.csv
"""

import csv
import os
import random
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
BIN = ROOT / "dataset" / "_linux_bin"
CC = shutil.which("clang") or shutil.which("gcc")

PIN_CPU = 0            # pin everything to one core -> guaranteed contention
BATCH_SIZE = 8
N_BATCHES = 400
SEED = 7

SCHED_OTHER, SCHED_IDLE = 0, 5
# per-slot assignment inside each batch: (policy, nice). Mix of normal
# priorities + niced + SCHED_IDLE (finishes last under contention).
SLOT_PLAN = [
    (SCHED_OTHER, 0), (SCHED_OTHER, 0), (SCHED_OTHER, 0),
    (SCHED_OTHER, 10), (SCHED_OTHER, 19),
    (SCHED_IDLE, 0), (SCHED_IDLE, 0), (SCHED_IDLE, 0),
]
POLICY_NAME = {SCHED_OTHER: "OTHER", SCHED_IDLE: "IDLE"}


def compile_all():
    """Compile every corpus program to a native binary (reuse if present)."""
    BIN.mkdir(parents=True, exist_ok=True)
    progs = []
    jobs = [(f.stem, [f], []) for f in sorted((CORPUS / "synthetic").glob("*.c"))]
    for cat in ["kernel", "sequential", "app", "test"]:
        base = CORPUS / "tacle-bench" / "bench" / cat
        if base.exists():
            for d in sorted(base.iterdir()):
                if d.is_dir() and list(d.glob("*.c")):
                    jobs.append(("tacle_" + d.name, sorted(d.glob("*.c")),
                                 ["-I" + str(d)]))
    for pid, cfiles, flags in jobs:
        exe = BIN / pid
        if not exe.exists():
            r = subprocess.run([CC, "-O1", "-o", str(exe)] +
                               [str(f) for f in cfiles] + flags,
                               capture_output=True)
            if r.returncode != 0:
                continue
        progs.append((pid, exe))
    return progs


def run_batch(batch_id, members):
    """members: list of (pid_name, exe, policy, nice). Launch all pinned to
    PIN_CPU, reap in completion order, return per-task observation rows."""
    pids = {}
    t0 = time.monotonic()
    for name, exe, policy, nice in members:
        child = os.fork()
        if child == 0:
            try:
                os.sched_setaffinity(0, {PIN_CPU})
                os.sched_setscheduler(0, policy, os.sched_param(0))
                if policy == SCHED_OTHER and nice:
                    os.nice(nice)
            except (PermissionError, OSError):
                pass
            os.execv(str(exe), [str(exe)])
            os._exit(127)
        pids[child] = (name, policy, nice)

    rows = []
    batch_total_cpu = 0.0
    while pids:
        child, status, ru = os.wait4(-1, 0)
        t_done = time.monotonic()
        name, policy, nice = pids.pop(child)
        turnaround = t_done - t0
        rows.append({
            "batch_id": batch_id, "id": name,
            "policy": POLICY_NAME[policy], "nice": nice,
            "cpu_s": round(ru.ru_utime, 6),
            "turnaround_s": round(turnaround, 6),
            "wait_s": round(max(turnaround - ru.ru_utime, 0.0), 6),
            "invol_ctxsw": int(ru.ru_nivcsw),
            "batch_size": len(members),
        })
        batch_total_cpu += ru.ru_utime
    for r in rows:
        r["batch_total_cpu_s"] = round(batch_total_cpu, 6)
    return rows


def main():
    if CC is None:
        raise SystemExit("no clang/gcc -- `sudo apt install clang`")
    rng = random.Random(SEED)
    progs = compile_all()
    print("compiled %d programs; running %d contended batches of %d (pinned to CPU %d)"
          % (len(progs), N_BATCHES, BATCH_SIZE, PIN_CPU))

    all_rows = []
    for b in range(N_BATCHES):
        chosen = rng.sample(progs, BATCH_SIZE)
        plan = SLOT_PLAN[:]
        rng.shuffle(plan)  # decorrelate program identity from assigned policy
        members = [(name, exe, pol, nice)
                   for (name, exe), (pol, nice) in zip(chosen, plan)]
        all_rows.extend(run_batch(b, members))
        if (b + 1) % 100 == 0:
            print("  %d/%d batches" % (b + 1, N_BATCHES))

    out = ROOT / "dataset" / "labels_contended.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    print("wrote %d task-observations -> %s" % (len(all_rows), out))


if __name__ == "__main__":
    main()
