#!/usr/bin/env python3
"""Tier-1 static feature extractor.

Compiles every corpus program to LLVM IR (-O1), runs LLVM analysis printers,
parses IR text, and writes one CSV row per program.

Features (per program, aggregated over functions):
  structure : n_funcs, bb_count, inst_count, cyclomatic_total, cyclomatic_max
  loops     : loop_count, max_loop_depth, static_trip_loops, dyn_trip_loops
  recursion : direct_recursion, mutual_recursion (0/1)
  calls     : callgraph_depth (longest acyclic call-chain)
  cost      : tti_cost_sum, tti_cost_freq_weighted, bfi_max
  memory    : n_allocas, stack_bytes
  opcodes   : loads, stores, calls, branches, icmps, addsubs, muls, divrems,
              bitops, geps, phis, selects, fpops
"""

import csv
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

def _tool(name):
    """Resolve an LLVM tool by name across macOS Homebrew and Linux (where
    binaries are often version-suffixed, e.g. opt-18). Returns a full path."""
    import shutil
    brew = Path("/opt/homebrew/opt/llvm/bin") / name
    if brew.exists():
        return str(brew)
    for cand in [name] + [f"{name}-{v}" for v in range(22, 14, -1)]:
        p = shutil.which(cand)
        if p:
            return p
    raise SystemExit("LLVM tool '%s' not found -- in the VM run "
                     "`sudo apt install llvm clang`" % name)


CLANG = _tool("clang")
OPT = _tool("opt")
LLVM_LINK = _tool("llvm-link")
ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
SCRATCH = ROOT / "dataset" / "_ll"  # portable scratch inside the repo

OPCODE_GROUPS = {
    "loads": {"load"}, "stores": {"store"}, "calls": {"call", "invoke"},
    "branches": {"br", "switch"}, "icmps": {"icmp", "fcmp"},
    "addsubs": {"add", "sub"}, "muls": {"mul", "fmul"},
    "divrems": {"udiv", "sdiv", "urem", "srem", "fdiv", "frem"},
    "bitops": {"and", "or", "xor", "shl", "lshr", "ashr"},
    "geps": {"getelementptr"}, "phis": {"phi"}, "selects": {"select"},
    "fpops": {"fadd", "fsub", "fptrunc", "fpext", "sitofp", "uitofp",
              "fptosi", "fptoui"},
}
INST_RE = re.compile(r"^\s+(?:%[\w.\-]+ = )?(\w+)")
LABEL_RE = re.compile(r"^([\w.\-]+):")
DEFINE_RE = re.compile(r"^define .*@([\w.\-]+)\(")
CALL_RE = re.compile(r"\bcall\b[^;]*@([\w.\-]+)\(")
ALLOCA_RE = re.compile(r"= alloca ([^,]+)")
ARRAY_RE = re.compile(r"\[(\d+) x i(\d+)\]")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def compile_to_ll(cfiles, out_ll, extra_flags):
    """Compile one or more .c files and llvm-link them into out_ll."""
    parts = []
    for i, f in enumerate(cfiles):
        part = out_ll.with_suffix(".part%d.ll" % i)
        r = run([CLANG, "-O1", "-emit-llvm", "-S", "-o", str(part),
                 str(f)] + extra_flags)
        if r.returncode != 0:
            return False, r.stderr.splitlines()[:2]
        parts.append(str(part))
    if len(parts) == 1:
        Path(parts[0]).rename(out_ll)
    else:
        r = run([LLVM_LINK, "-S", "-o", str(out_ll)] + parts)
        if r.returncode != 0:
            return False, r.stderr.splitlines()[:2]
    return True, None


def parse_ir(ll_path):
    """Parse .ll text: functions, blocks (in order), opcodes, edges, allocas."""
    funcs = {}  # name -> dict
    cur = None
    for line in ll_path.read_text().splitlines():
        m = DEFINE_RE.match(line)
        if m:
            cur = {"blocks": [], "insts_per_block": [], "opcodes": defaultdict(int),
                   "edges": 0, "calls_to": set(), "allocas": 0, "stack_bytes": 0,
                   "self_call": False, "name": m.group(1)}
            funcs[m.group(1)] = cur
            cur["blocks"].append("entry")
            cur["insts_per_block"].append(0)
            continue
        if cur is None:
            continue
        if line.startswith("}"):
            cur = None
            continue
        lm = LABEL_RE.match(line)
        if lm:
            cur["blocks"].append(lm.group(1))
            cur["insts_per_block"].append(0)
            continue
        im = INST_RE.match(line)
        if not im:
            continue
        op = im.group(1)
        cur["insts_per_block"][-1] += 1
        for group, ops in OPCODE_GROUPS.items():
            if op in ops:
                cur["opcodes"][group] += 1
        if op == "br":
            cur["edges"] += 2 if " i1 " in line else 1
        elif op == "switch":
            cur["edges"] += line.count("label %")
        if op == "alloca":
            cur["allocas"] += 1
            am = ALLOCA_RE.search(line)
            if am:
                ar = ARRAY_RE.search(am.group(1))
                cur["stack_bytes"] += (int(ar.group(1)) * int(ar.group(2)) // 8
                                       if ar else 8)
        cm = CALL_RE.search(line)
        if cm:
            callee = cm.group(1)
            cur["calls_to"].add(callee)
            if callee == cur["name"]:
                cur["self_call"] = True
    return funcs


def callgraph_depth(funcs):
    """Longest call chain, cycles collapsed (each visited-set guarded)."""
    memo = {}

    def depth(f, stack):
        if f in memo:
            return memo[f]
        if f not in funcs or f in stack:
            return 0
        stack.add(f)
        d = 1 + max((depth(c, stack) for c in funcs[f]["calls_to"]), default=0)
        stack.discard(f)
        memo[f] = d
        return d

    return max((depth(f, set()) for f in funcs), default=0)


def parse_analyses(ll_path):
    """Run opt printers; return loops/scev/bfi/cost data keyed per function."""
    out = {}
    r = run([OPT,
             "-passes=print<loops>,print<scalar-evolution>,print<block-freq>,"
             "print<cost-model>",
             "-disable-output", str(ll_path)])
    # module-level pass must run in its own pipeline
    r2 = run([OPT, "-passes=print-callgraph-sccs",
              "-disable-output", str(ll_path)])
    text = r.stdout + r.stderr + r2.stdout + r2.stderr
    out["loop_count"] = len(re.findall(r"Loop at depth \d+", text))
    depths = [int(d) for d in re.findall(r"Loop at depth (\d+)", text)]
    out["max_loop_depth"] = max(depths, default=0)
    trips = re.findall(r"backedge-taken count is (.+)$", text, re.M)
    trips = [t for t in trips if "max" not in t]  # keep only the exact counts
    static = sum(1 for t in trips if re.fullmatch(r"i\d+ [\d\-]+|[\d\-]+", t.strip()))
    out["static_trip_loops"] = static
    out["dyn_trip_loops"] = max(len(trips) - static, 0)
    out["tti_cost_sum"] = sum(int(c) for c in
                              re.findall(r"estimated cost of (\d+)", text))
    # BFI: per-function ordered float list
    bfi = defaultdict(list)
    fname = None
    for line in text.splitlines():
        m = re.search(r"block-frequency-info: ([\w.\-]+)", line)
        if m:
            fname = m.group(1)
            continue
        m = re.search(r"float = ([\d.]+)", line)
        if m and fname:
            bfi[fname].append(float(m.group(1)))
    out["bfi"] = dict(bfi)
    # mutual recursion: any SCC line listing >1 function
    out["mutual_recursion"] = 0
    for line in text.splitlines():
        m = re.match(r"SCC #\d+\s*:\s*(.+)", line)
        if m and len([f for f in m.group(1).split(",") if f.strip()
                      and "external node" not in f]) > 1:
            out["mutual_recursion"] = 1
    return out


def extract(pid, source, cfiles, extra_flags):
    ll = SCRATCH / (pid + ".ll")
    ok, err = compile_to_ll(cfiles, ll, extra_flags)
    if not ok:
        print("  SKIP %s: %s" % (pid, err), file=sys.stderr)
        return None
    funcs = parse_ir(ll)
    an = parse_analyses(ll)

    row = {"id": pid, "source": source, "n_funcs": len(funcs)}
    row["bb_count"] = sum(len(f["blocks"]) for f in funcs.values())
    row["inst_count"] = sum(sum(f["insts_per_block"]) for f in funcs.values())
    cyclo = [f["edges"] - len(f["blocks"]) + 2 for f in funcs.values()]
    row["cyclomatic_total"] = sum(cyclo)
    row["cyclomatic_max"] = max(cyclo, default=0)
    row["loop_count"] = an["loop_count"]
    row["max_loop_depth"] = an["max_loop_depth"]
    row["static_trip_loops"] = an["static_trip_loops"]
    row["dyn_trip_loops"] = an["dyn_trip_loops"]
    row["direct_recursion"] = int(any(f["self_call"] for f in funcs.values()))
    row["mutual_recursion"] = an["mutual_recursion"]
    row["callgraph_depth"] = callgraph_depth(funcs)
    row["tti_cost_sum"] = an["tti_cost_sum"]
    # freq-weighted instruction count: zip BFI order with block order
    weighted = 0.0
    for name, f in funcs.items():
        freqs = an["bfi"].get(name, [])
        if len(freqs) == len(f["insts_per_block"]):
            weighted += sum(fr * n for fr, n in zip(freqs, f["insts_per_block"]))
        else:
            weighted += sum(f["insts_per_block"])  # fallback: unweighted
    row["freq_weighted_insts"] = round(weighted, 1)
    row["bfi_max"] = max((max(v) for v in an["bfi"].values() if v), default=0.0)
    row["n_allocas"] = sum(f["allocas"] for f in funcs.values())
    row["stack_bytes"] = sum(f["stack_bytes"] for f in funcs.values())
    for g in OPCODE_GROUPS:
        row[g] = sum(f["opcodes"][g] for f in funcs.values())
    return row


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    rows = []

    # synthetic: one file each
    for f in sorted((CORPUS / "synthetic").glob("*.c")):
        r = extract(f.stem, "synthetic", [f], [])
        if r:
            rows.append(r)

    # taclebench: one dir each (kernel/sequential/app/test)
    for cat in ["kernel", "sequential", "app", "test"]:
        for d in sorted((CORPUS / "tacle-bench" / "bench" / cat).iterdir()):
            if not d.is_dir():
                continue
            cfiles = sorted(d.glob("*.c"))
            if not cfiles:
                continue
            r = extract("tacle_" + d.name, "taclebench", cfiles,
                        ["-I" + str(d)])
            if r:
                rows.append(r)

    # embench: one dir each, needs defines + support include
    emb = CORPUS / "embench-iot"
    for d in sorted((emb / "src").iterdir()):
        if not d.is_dir():
            continue
        cfiles = sorted(d.glob("*.c"))
        if not cfiles:
            continue
        r = extract("embench_" + d.name, "embench", cfiles,
                    ["-I" + str(d), "-I" + str(emb / "support"),
                     "-DGLOBAL_SCALE_FACTOR=1", "-DCPU_MHZ=1", "-DWARMUP_HEAT=1"])
        if r:
            rows.append(r)

    out = ROOT / "dataset" / "features.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote %d rows -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
