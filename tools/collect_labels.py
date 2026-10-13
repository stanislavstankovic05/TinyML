import csv
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from corpus import Corpus


class Compiler:
    HOMEBREW = Path("/opt/homebrew/opt/llvm/bin/clang")

    def __init__(self):
        self.path = str(self.HOMEBREW) if self.HOMEBREW.exists() else shutil.which("clang") or shutil.which("gcc")
        if not self.path:
            raise SystemExit("no C compiler found, install clang")

    def build(self, program, target):
        command = [self.path, "-O1", "-o", str(target), *map(str, program.files), *program.flags]
        return subprocess.run(command, capture_output=True, text=True).returncode == 0


class LabelCollector:
    OUTPUT = None

    def __init__(self, root, output=None, programs=None):
        self.root = Path(root)
        self.programs = programs or Corpus(self.root / "corpus").runnable()
        self.binaries = self.root / "dataset" / "_bin"
        self.output = Path(output) if output else self.root / "dataset" / self.OUTPUT
        self.compiler = Compiler()
        self.skipped = []

    def binary(self, program, reuse=False):
        self.binaries.mkdir(parents=True, exist_ok=True)
        target = self.binaries / program.name
        if reuse and target.exists():
            return target
        if self.compiler.build(program, target):
            return target
        self.skipped.append(f"{program.name}: compile")
        return None

    def collect(self):
        raise NotImplementedError

    def run(self):
        rows = self.collect()
        with open(self.output, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {self.output}")
        if self.skipped:
            print(f"skipped {len(self.skipped)}: {self.skipped[:8]}")


class SoloCollector(LabelCollector):
    OUTPUT = "labels_macos.csv"
    REPEATS = 5
    INPUTS = [1, 3, 5, 7, 9]

    def inputs(self, program):
        return self.INPUTS if program.source == "synthetic" else [1]

    def arguments(self, binary, argc):
        return [str(binary)] + ["x"] * (argc - 1)

    def execute(self, binary, argc):
        try:
            child = os.posix_spawn(str(binary), self.arguments(binary, argc), os.environ)
            _, status, usage = os.wait4(child, 0)
        except OSError:
            return None
        return None if os.waitstatus_to_exitcode(status) < 0 else usage

    def repeat(self, *call):
        runs = []
        for _ in range(self.REPEATS):
            usage = self.execute(*call)
            if usage is None:
                return None
            runs.append(usage)
        return runs

    def collect(self):
        rows = []
        for program in self.programs:
            binary = self.binary(program)
            if binary is None:
                continue
            for argc in self.inputs(program):
                runs = self.repeat(binary, argc)
                if runs is None:
                    self.skipped.append(f"{program.name}: run argc={argc}")
                    continue
                times = [usage.ru_utime for usage in runs]
                rows.append({
                    "id": program.name,
                    "source": program.source,
                    "argc": argc,
                    "cpu_s_median": round(statistics.median(times), 6),
                    "cpu_s_min": round(min(times), 6),
                    "cpu_s_max": round(max(times), 6),
                })
        return rows


class LinuxCollector(SoloCollector):
    OUTPUT = "labels_linux.csv"
    INPUTS = [1, 5, 9]
    OTHER, BATCH, IDLE = 0, 3, 5
    POLICIES = {OTHER: "OTHER", BATCH: "BATCH", IDLE: "IDLE"}
    SCHEDULES = [
        ("nice0_other", 0, OTHER),
        ("nice10_other", 10, OTHER),
        ("nice0_batch", 0, BATCH),
        ("nice0_idle", 0, IDLE),
    ]
    USAGE = {
        "cpu_s_median": ("ru_utime", 6),
        "sys_s_median": ("ru_stime", 6),
        "maxrss_kb": ("ru_maxrss", None),
        "minflt": ("ru_minflt", None),
        "majflt": ("ru_majflt", None),
        "vol_ctxsw": ("ru_nvcsw", None),
        "invol_ctxsw": ("ru_nivcsw", None),
    }

    def execute(self, binary, argc, nice, policy):
        child = os.fork()
        if child == 0:
            try:
                os.sched_setscheduler(0, policy, os.sched_param(0))
            except OSError:
                pass
            try:
                if policy == self.OTHER:
                    os.nice(nice)
            except OSError:
                pass
            os.execv(str(binary), self.arguments(binary, argc))
            os._exit(127)
        _, status, usage = os.wait4(child, 0)
        return None if os.waitstatus_to_exitcode(status) < 0 else usage

    def summarize(self, runs):
        row = {}
        for column, (field, digits) in self.USAGE.items():
            median = statistics.median(getattr(usage, field) for usage in runs)
            row[column] = round(median, digits) if digits else int(median)
        return row

    def collect(self):
        rows = []
        for program in self.programs:
            binary = self.binary(program)
            if binary is None:
                continue
            for argc in self.inputs(program):
                for label, nice, policy in self.SCHEDULES:
                    runs = self.repeat(binary, argc, nice, policy)
                    if runs is None:
                        self.skipped.append(f"{program.name}: {label} argc={argc}")
                        continue
                    rows.append({
                        "id": program.name,
                        "source": program.source,
                        "argc": argc,
                        "sched_grid": label,
                        "nice": nice,
                        "policy": self.POLICIES[policy],
                        **self.summarize(runs),
                    })
        return rows


class ContendedCollector(LabelCollector):
    OUTPUT = "labels_contended.csv"
    CPU = 0
    BATCHES = 400
    SEED = 7
    OTHER, IDLE = 0, 5
    POLICIES = {OTHER: "OTHER", IDLE: "IDLE"}
    SLOTS = [(OTHER, 0), (OTHER, 0), (OTHER, 0), (OTHER, 10), (OTHER, 19), (IDLE, 0), (IDLE, 0), (IDLE, 0)]

    def launch(self, binary, policy, nice):
        child = os.fork()
        if child == 0:
            try:
                os.sched_setaffinity(0, {self.CPU})
                os.sched_setscheduler(0, policy, os.sched_param(0))
                if policy == self.OTHER and nice:
                    os.nice(nice)
            except OSError:
                pass
            os.execv(str(binary), [str(binary)])
            os._exit(127)
        return child

    def batch(self, number, members):
        started = time.monotonic()
        running = {self.launch(binary, policy, nice): (name, policy, nice) for name, binary, policy, nice in members}
        rows = []
        total = 0.0
        while running:
            child, _, usage = os.wait4(-1, 0)
            turnaround = time.monotonic() - started
            name, policy, nice = running.pop(child)
            total += usage.ru_utime
            rows.append({
                "batch_id": number,
                "id": name,
                "policy": self.POLICIES[policy],
                "nice": nice,
                "cpu_s": round(usage.ru_utime, 6),
                "turnaround_s": round(turnaround, 6),
                "wait_s": round(max(turnaround - usage.ru_utime, 0.0), 6),
                "invol_ctxsw": int(usage.ru_nivcsw),
                "batch_size": len(members),
            })
        for row in rows:
            row["batch_total_cpu_s"] = round(total, 6)
        return rows

    def collect(self):
        generator = random.Random(self.SEED)
        compiled = [(program.name, self.binary(program, reuse=True)) for program in self.programs]
        compiled = [(name, binary) for name, binary in compiled if binary]
        rows = []
        for number in range(self.BATCHES):
            chosen = generator.sample(compiled, len(self.SLOTS))
            slots = list(self.SLOTS)
            generator.shuffle(slots)
            members = [(name, binary, policy, nice) for (name, binary), (policy, nice) in zip(chosen, slots)]
            rows.extend(self.batch(number, members))
        return rows


if __name__ == "__main__":
    collectors = {"macos": SoloCollector, "linux": LinuxCollector, "contended": ContendedCollector}
    if len(sys.argv) != 2 or sys.argv[1] not in collectors:
        raise SystemExit("usage: collect_labels.py macos|linux|contended")
    collectors[sys.argv[1]](Path(__file__).resolve().parent.parent).run()
