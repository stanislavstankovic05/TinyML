import csv
import itertools
import random
import sys
from pathlib import Path


class SyntheticProgram:
    TRIP_COUNTS = {"s": 64, "l": 4096, "dyn": None}
    EXPRESSIONS = {
        "int": "acc += (x ^ (acc << 3)) + (x >> 2);",
        "muldiv": "acc += (x * 2654435761u) / ((x & 0xffu) + 1u);",
        "mixed": "acc += (x * 31u) ^ (acc / ((x & 0x3fu) + 1u)) + (x >> 1);",
    }
    MEMORY_ACCESS = {
        "seq": "arr[i & (ASIZE-1)] = acc; acc += arr[(i + 1) & (ASIZE-1)];",
        "stride": "arr[(i * 17u) & (ASIZE-1)] = acc; acc += arr[(i * 31u) & (ASIZE-1)];",
        "chase": "nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;",
    }
    RECURSIVE_FUNCTIONS = {
        "none": [],
        "direct": [
            "static u32 rec_f(u32 n, u32 acc) {",
            "  if (n == 0u) return acc;",
            "  return rec_f(n - 1u, acc + (n ^ (acc << 1)));",
            "}",
        ],
        "mutual": [
            "static u32 rec_b(u32 n, u32 acc);",
            "static u32 rec_a(u32 n, u32 acc) {",
            "  if (n == 0u) return acc;",
            "  return rec_b(n - 1u, acc + n);",
            "}",
            "static u32 rec_b(u32 n, u32 acc) {",
            "  if (n == 0u) return acc ^ 0x5aa5u;",
            "  return rec_a(n - 1u, acc + (acc << 2));",
            "}",
        ],
        "tree": [
            "static u32 rec_t(u32 n) {",
            "  if (n < 2u) return n + 1u;",
            "  return rec_t(n - 1u) + rec_t(n - 2u);",
            "}",
        ],
    }
    RECURSIVE_CALLS = {
        "direct": "  acc = rec_f((s & 63u) + 8u, acc);",
        "mutual": "  acc = rec_a((s & 31u) + 8u, acc);",
        "tree": "  acc += rec_t((s & 7u) + 10u);",
    }

    def __init__(self, name, loops, nest, trip, recursion, call_depth, branchiness, mem, mix):
        self.name = name
        self.loops = loops
        self.nest = nest
        self.trip = trip
        self.recursion = recursion
        self.call_depth = call_depth
        self.branchiness = branchiness
        self.mem = mem
        self.mix = mix

    def header(self):
        return [
            f"/* synthetic corpus program {self.name}",
            f" * loops={self.loops} nest={self.nest} trip={self.trip} rec={self.recursion}"
            f" calls={self.call_depth} branch={self.branchiness} mem={self.mem} mix={self.mix} */",
        ]

    def globals(self):
        lines = [
            "typedef unsigned int u32;",
            "static volatile u32 sink;",
            "static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }",
        ]
        if self.mem != "none":
            lines += ["#define ASIZE 1024", "static u32 arr[ASIZE];"]
        return lines

    def call_chain(self):
        lines = []
        for level in range(self.call_depth, 0, -1):
            body = f"chain{level + 1}(x + {level}u)" if level < self.call_depth else "x ^ (x >> 3)"
            lines.append(f"static u32 chain{level}(u32 x) {{ return {body} + {level * 7}u; }}")
        return lines

    def branches(self):
        return [
            f"if ((x & {1 << (index % 8)}u) == 0u) acc += {index * 13 + 1}u; else acc ^= (x >> {index % 5 + 1});"
            for index in range(self.branchiness)
        ]

    def statements(self):
        lines = ["u32 x = lcg(&s);", self.EXPRESSIONS[self.mix]] + self.branches()
        if self.mem != "none":
            lines.append(self.MEMORY_ACCESS[self.mem])
        if self.call_depth:
            lines.append("acc += chain1(x);")
        return lines

    def loop_nest(self, index):
        count = self.TRIP_COUNTS[self.trip]
        bound = f"{count}u" if count else "n"
        lines = []
        indent = "  "
        for depth in range(self.nest):
            counter = f"i{index}_{depth}"
            limit = bound if depth == 0 else "8u"
            lines.append(f"{indent}for (u32 {counter} = 0; {counter} < {limit}; {counter}++) {{")
            indent += "  "
        outer = f"i{index}_0"
        for statement in self.statements():
            lines.append(indent + statement.replace("i &", f"{outer} &").replace("(i ", f"({outer} "))
        for _ in range(self.nest):
            indent = indent[:-2]
            lines.append(indent + "}")
        return lines

    def work(self):
        lines = ["u32 work(u32 s, u32 n) {", "  u32 acc = s;"]
        if self.mem == "chase":
            lines.append("  u32 nxt = s & (ASIZE-1);")
        for index in range(max(self.loops, 1)):
            lines += self.loop_nest(index)
        if self.recursion in self.RECURSIVE_CALLS:
            lines.append(self.RECURSIVE_CALLS[self.recursion])
        return lines + ["  return acc;", "}"]

    def main(self):
        size = "((u32)argc * 512u) + 64u" if self.trip == "dyn" else "64u"
        return [
            "int main(int argc, char **argv) {",
            "  (void)argv;",
            "  u32 seed = 0x1234u + (u32)argc;",
            f"  u32 n = {size};",
            "  sink = work(seed, n);",
            "  return (int)(sink & 0x7f);",
            "}",
        ]

    def source(self):
        lines = (
            self.header()
            + self.globals()
            + self.RECURSIVE_FUNCTIONS[self.recursion]
            + self.call_chain()
            + self.work()
            + self.main()
        )
        return "\n".join(lines) + "\n"


class CorpusGenerator:
    KNOBS = {
        "loops": [0, 1, 2, 4],
        "nest": [1, 2, 3, 4],
        "trip": ["s", "l", "dyn"],
        "recursion": ["none", "direct", "mutual", "tree"],
        "call_depth": [0, 1, 3, 6],
        "branchiness": [0, 2, 4, 8],
        "mem": ["none", "seq", "stride", "chase"],
        "mix": ["int", "muldiv", "mixed"],
    }

    def __init__(self, output, seed=42):
        self.output = Path(output)
        self.seed = seed

    def choose(self, count):
        space = [
            combination
            for combination in itertools.product(*self.KNOBS.values())
            if not (combination[0] == 0 and combination[3] == "none")
        ]
        random.Random(self.seed).shuffle(space)
        return space[:count]

    def generate(self, count=320):
        self.output.mkdir(parents=True, exist_ok=True)
        manifest = []
        for index, combination in enumerate(self.choose(count)):
            name = f"synth_{index:04d}"
            program = SyntheticProgram(name, *combination)
            (self.output / f"{name}.c").write_text(program.source())
            manifest.append([name, *combination])
        with open(self.output / "manifest.csv", "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", *self.KNOBS])
            writer.writerows(manifest)
        print(f"wrote {len(manifest)} programs to {self.output}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 320
    CorpusGenerator(root / "corpus" / "synthetic").generate(count)
