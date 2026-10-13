import csv
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from corpus import Corpus


class Toolchain:
    HOMEBREW = Path("/opt/homebrew/opt/llvm/bin")
    VERSIONS = range(22, 14, -1)

    def __init__(self):
        self.clang = self.find("clang")
        self.opt = self.find("opt")
        self.llvm_link = self.find("llvm-link")

    def find(self, name):
        bundled = self.HOMEBREW / name
        if bundled.exists():
            return str(bundled)
        for candidate in [name] + [f"{name}-{version}" for version in self.VERSIONS]:
            path = shutil.which(candidate)
            if path:
                return path
        raise SystemExit(f"{name} not found, install llvm and clang")

    def run(self, *arguments):
        return subprocess.run(list(arguments), capture_output=True, text=True, timeout=120)


class IrFunction:
    GROUPS = {
        "loads": {"load"},
        "stores": {"store"},
        "calls": {"call", "invoke"},
        "branches": {"br", "switch"},
        "icmps": {"icmp", "fcmp"},
        "addsubs": {"add", "sub"},
        "muls": {"mul", "fmul"},
        "divrems": {"udiv", "sdiv", "urem", "srem", "fdiv", "frem"},
        "bitops": {"and", "or", "xor", "shl", "lshr", "ashr"},
        "geps": {"getelementptr"},
        "phis": {"phi"},
        "selects": {"select"},
        "fpops": {"fadd", "fsub", "fptrunc", "fpext", "sitofp", "uitofp", "fptosi", "fptoui"},
    }
    CALL = re.compile(r"\bcall\b[^;]*@([\w.\-]+)\(")
    ALLOCA = re.compile(r"= alloca ([^,]+)")
    ARRAY = re.compile(r"\[(\d+) x i(\d+)\]")

    def __init__(self, name):
        self.name = name
        self.block_sizes = [0]
        self.opcodes = defaultdict(int)
        self.edges = 0
        self.callees = set()
        self.allocas = 0
        self.stack_bytes = 0
        self.calls_itself = False

    @property
    def blocks(self):
        return len(self.block_sizes)

    @property
    def instructions(self):
        return sum(self.block_sizes)

    @property
    def cyclomatic(self):
        return self.edges - self.blocks + 2

    def open_block(self):
        self.block_sizes.append(0)

    def add(self, opcode, line):
        self.block_sizes[-1] += 1
        for group, members in self.GROUPS.items():
            if opcode in members:
                self.opcodes[group] += 1
        if opcode == "br":
            self.edges += 2 if " i1 " in line else 1
        elif opcode == "switch":
            self.edges += line.count("label %")
        if opcode == "alloca":
            self.add_alloca(line)
        call = self.CALL.search(line)
        if call:
            self.callees.add(call.group(1))
            if call.group(1) == self.name:
                self.calls_itself = True

    def add_alloca(self, line):
        self.allocas += 1
        match = self.ALLOCA.search(line)
        if match:
            array = self.ARRAY.search(match.group(1))
            self.stack_bytes += int(array.group(1)) * int(array.group(2)) // 8 if array else 8


class IrModule:
    DEFINE = re.compile(r"^define .*@([\w.\-]+)\(")
    LABEL = re.compile(r"^([\w.\-]+):")
    INSTRUCTION = re.compile(r"^\s+(?:%[\w.\-]+ = )?(\w+)")

    def __init__(self, path):
        self.functions = {}
        self.parse(Path(path).read_text())

    def parse(self, text):
        current = None
        for line in text.splitlines():
            define = self.DEFINE.match(line)
            if define:
                current = IrFunction(define.group(1))
                self.functions[current.name] = current
                continue
            if current is None:
                continue
            if line.startswith("}"):
                current = None
                continue
            if self.LABEL.match(line):
                current.open_block()
                continue
            instruction = self.INSTRUCTION.match(line)
            if instruction:
                current.add(instruction.group(1), line)

    def call_depth(self):
        known = {}

        def depth(name, path):
            if name in known:
                return known[name]
            if name not in self.functions or name in path:
                return 0
            path.add(name)
            deepest = max((depth(callee, path) for callee in self.functions[name].callees), default=0)
            path.discard(name)
            known[name] = 1 + deepest
            return known[name]

        return max((depth(name, set()) for name in self.functions), default=0)


class OptReport:
    FUNCTION_PASSES = "print<loops>,print<scalar-evolution>,print<block-freq>,print<cost-model>"
    MODULE_PASSES = "print-callgraph-sccs"

    def __init__(self, toolchain, path):
        outputs = [
            toolchain.run(toolchain.opt, f"-passes={passes}", "-disable-output", str(path))
            for passes in (self.FUNCTION_PASSES, self.MODULE_PASSES)
        ]
        self.text = "".join(output.stdout + output.stderr for output in outputs)

    def loop_depths(self):
        return [int(depth) for depth in re.findall(r"Loop at depth (\d+)", self.text)]

    def trip_counts(self):
        counts = re.findall(r"backedge-taken count is (.+)$", self.text, re.M)
        counts = [count for count in counts if "max" not in count]
        static = sum(1 for count in counts if re.fullmatch(r"i\d+ [\d\-]+|[\d\-]+", count.strip()))
        return static, max(len(counts) - static, 0)

    def cost(self):
        return sum(int(cost) for cost in re.findall(r"estimated cost of (\d+)", self.text))

    def block_frequencies(self):
        frequencies = defaultdict(list)
        function = None
        for line in self.text.splitlines():
            header = re.search(r"block-frequency-info: ([\w.\-]+)", line)
            if header:
                function = header.group(1)
                continue
            value = re.search(r"float = ([\d.]+)", line)
            if value and function:
                frequencies[function].append(float(value.group(1)))
        return dict(frequencies)

    def mutual_recursion(self):
        for line in self.text.splitlines():
            component = re.match(r"SCC #\d+\s*:\s*(.+)", line)
            if not component:
                continue
            members = [name for name in component.group(1).split(",") if name.strip() and "external node" not in name]
            if len(members) > 1:
                return 1
        return 0


class FeatureExtractor:
    def __init__(self, root, output=None, scratch=None):
        self.root = Path(root)
        self.corpus = Corpus(self.root / "corpus")
        self.output = Path(output) if output else self.root / "dataset" / "features.csv"
        self.scratch = Path(scratch) if scratch else self.root / "dataset" / "_ll"
        self.toolchain = Toolchain()

    def compile(self, program):
        target = self.scratch / f"{program.name}.ll"
        parts = []
        for index, source in enumerate(program.files):
            part = target.with_suffix(f".part{index}.ll")
            result = self.toolchain.run(
                self.toolchain.clang, "-O1", "-emit-llvm", "-S", "-o", str(part), str(source), *program.flags
            )
            if result.returncode != 0:
                return None
            parts.append(part)
        if len(parts) == 1:
            parts[0].rename(target)
        elif self.toolchain.run(self.toolchain.llvm_link, "-S", "-o", str(target), *map(str, parts)).returncode != 0:
            return None
        return target

    def weighted_instructions(self, module, frequencies):
        total = 0.0
        for name, function in module.functions.items():
            weights = frequencies.get(name, [])
            if len(weights) == function.blocks:
                total += sum(weight * size for weight, size in zip(weights, function.block_sizes))
            else:
                total += function.instructions
        return round(total, 1)

    def features(self, program):
        path = self.compile(program)
        if path is None:
            print(f"skipped {program.name}: does not compile", file=sys.stderr)
            return None
        module = IrModule(path)
        report = OptReport(self.toolchain, path)
        functions = list(module.functions.values())
        depths = report.loop_depths()
        static_trips, dynamic_trips = report.trip_counts()
        frequencies = report.block_frequencies()
        row = {
            "id": program.name,
            "source": program.source,
            "n_funcs": len(functions),
            "bb_count": sum(function.blocks for function in functions),
            "inst_count": sum(function.instructions for function in functions),
            "cyclomatic_total": sum(function.cyclomatic for function in functions),
            "cyclomatic_max": max((function.cyclomatic for function in functions), default=0),
            "loop_count": len(depths),
            "max_loop_depth": max(depths, default=0),
            "static_trip_loops": static_trips,
            "dyn_trip_loops": dynamic_trips,
            "direct_recursion": int(any(function.calls_itself for function in functions)),
            "mutual_recursion": report.mutual_recursion(),
            "callgraph_depth": module.call_depth(),
            "tti_cost_sum": report.cost(),
            "freq_weighted_insts": self.weighted_instructions(module, frequencies),
            "bfi_max": max((max(values) for values in frequencies.values() if values), default=0.0),
            "n_allocas": sum(function.allocas for function in functions),
            "stack_bytes": sum(function.stack_bytes for function in functions),
        }
        for group in IrFunction.GROUPS:
            row[group] = sum(function.opcodes[group] for function in functions)
        return row

    def run(self, programs=None):
        self.scratch.mkdir(parents=True, exist_ok=True)
        rows = [self.features(program) for program in programs or self.corpus.programs()]
        rows = [row for row in rows if row]
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {self.output}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    FeatureExtractor(root, sys.argv[1] if len(sys.argv) > 1 else None).run()
