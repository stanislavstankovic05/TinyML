#!/usr/bin/env python3
"""Synthetic C corpus generator for the burst-prediction dataset.

Emits self-contained C programs across a controlled feature-space grid.
Every program is compilable with no includes and no external dependencies.
The knob values for each program are recorded in manifest.csv (ground truth).

Knobs:
  loops        number of independent top-level loops        0..4
  nest         max loop nesting depth                       1..4
  trip         loop trip count: static small/large, or input-dependent
  recursion    none | direct | mutual | tree
  call_depth   length of the plain function call chain      0..6
  branchiness  if/else chains inside loop bodies            0..8
  mem          none | seq | stride | chase   (array access pattern)
  mix          int | muldiv | mixed          (operator mix)

An LCG-based "input" (seeded from argc so the compiler can't constant-fold)
feeds all computation; a volatile sink prevents dead-code elimination.
"""

import csv
import itertools
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "corpus" / "synthetic"

TRIP = {"s": 64, "l": 4096, "dyn": None}  # dyn -> trip count comes from input


def emit_program(pid, loops, nest, trip, recursion, call_depth, branchiness, mem, mix):
    """Return C source text for one parameter combination."""
    parts = []
    parts.append("/* synthetic corpus program %s" % pid)
    parts.append(" * loops=%d nest=%d trip=%s rec=%s calls=%d branch=%d mem=%s mix=%s */"
                 % (loops, nest, trip, recursion, call_depth, branchiness, mem, mix))
    parts.append("typedef unsigned int u32;")
    parts.append("static volatile u32 sink;")
    # LCG so values are input-dependent and unfoldable
    parts.append("static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }")

    # ---- operator-mix expression helpers -------------------------------
    if mix == "int":
        expr = "acc += (x ^ (acc << 3)) + (x >> 2);"
    elif mix == "muldiv":
        expr = "acc += (x * 2654435761u) / ((x & 0xffu) + 1u);"
    else:  # mixed
        expr = "acc += (x * 31u) ^ (acc / ((x & 0x3fu) + 1u)) + (x >> 1);"

    # ---- memory pattern -------------------------------------------------
    mem_decl, mem_stmt = "", ""
    if mem != "none":
        parts.append("#define ASIZE 1024")
        parts.append("static u32 arr[ASIZE];")
        if mem == "seq":
            mem_stmt = "arr[i & (ASIZE-1)] = acc; acc += arr[(i + 1) & (ASIZE-1)];"
        elif mem == "stride":
            mem_stmt = "arr[(i * 17u) & (ASIZE-1)] = acc; acc += arr[(i * 31u) & (ASIZE-1)];"
        else:  # chase: index depends on previous load
            mem_stmt = "nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;"
            mem_decl = "u32 nxt = s & (ASIZE-1);"

    # ---- recursion ------------------------------------------------------
    if recursion == "direct":
        parts.append("static u32 rec_f(u32 n, u32 acc) {")
        parts.append("  if (n == 0u) return acc;")
        parts.append("  return rec_f(n - 1u, acc + (n ^ (acc << 1)));")
        parts.append("}")
    elif recursion == "mutual":
        parts.append("static u32 rec_b(u32 n, u32 acc);")
        parts.append("static u32 rec_a(u32 n, u32 acc) {")
        parts.append("  if (n == 0u) return acc;")
        parts.append("  return rec_b(n - 1u, acc + n);")
        parts.append("}")
        parts.append("static u32 rec_b(u32 n, u32 acc) {")
        parts.append("  if (n == 0u) return acc ^ 0x5aa5u;")
        parts.append("  return rec_a(n - 1u, acc + (acc << 2));")
        parts.append("}")
    elif recursion == "tree":
        parts.append("static u32 rec_t(u32 n) {")
        parts.append("  if (n < 2u) return n + 1u;")
        parts.append("  return rec_t(n - 1u) + rec_t(n - 2u);")
        parts.append("}")

    # ---- call chain -----------------------------------------------------
    for k in range(call_depth, 0, -1):
        callee = ("chain%d(x + %du)" % (k + 1, k)) if k < call_depth else "x ^ (x >> 3)"
        parts.append("static u32 chain%d(u32 x) { return %s + %du; }" % (k, callee, k * 7))

    # ---- branch helper --------------------------------------------------
    branch_stmts = []
    for b in range(branchiness):
        branch_stmts.append(
            "if ((x & %du) == 0u) acc += %du; else acc ^= (x >> %d);"
            % (1 << (b % 8), b * 13 + 1, (b % 5) + 1))

    # ---- the loop nest --------------------------------------------------
    body = []
    body.append("u32 work(u32 s, u32 n) {")
    body.append("  u32 acc = s;")
    if mem_decl:
        body.append("  " + mem_decl)
    tc = TRIP[trip]
    bound = str(tc) + "u" if tc else "n"
    inner_lines = ["u32 x = lcg(&s);", expr] + branch_stmts
    if mem_stmt:
        inner_lines.append(mem_stmt)
    if call_depth:
        inner_lines.append("acc += chain1(x);")

    for li in range(max(loops, 1)):
        # each top-level loop gets `nest` levels; inner bounds kept small
        indent = "  "
        for d in range(nest):
            v = "i%d_%d" % (li, d)
            b = bound if d == 0 else "8u"
            body.append("%sfor (u32 %s = 0; %s < %s; %s++) {" % (indent, v, v, b, v))
            indent += "  "
        iv = "i%d_0" % li
        for st in inner_lines:
            body.append(indent + st.replace("i &", "%s &" % iv).replace("(i ", "(%s " % iv))
        for d in range(nest):
            indent = indent[:-2]
            body.append(indent + "}")
    if recursion == "direct":
        body.append("  acc = rec_f((s & 63u) + 8u, acc);")
    elif recursion == "mutual":
        body.append("  acc = rec_a((s & 31u) + 8u, acc);")
    elif recursion == "tree":
        body.append("  acc += rec_t((s & 7u) + 10u);")
    body.append("  return acc;")
    body.append("}")
    parts.extend(body)

    parts.append("int main(int argc, char **argv) {")
    parts.append("  (void)argv;")
    parts.append("  u32 seed = 0x1234u + (u32)argc;")
    parts.append("  u32 n = %s;" % ("((u32)argc * 512u) + 64u" if trip == "dyn" else "64u"))
    parts.append("  sink = work(seed, n);")
    parts.append("  return (int)(sink & 0x7f);")
    parts.append("}")
    return "\n".join(parts) + "\n"


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 320
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    space = list(itertools.product(
        [0, 1, 2, 4],                       # loops
        [1, 2, 3, 4],                       # nest
        ["s", "l", "dyn"],                  # trip
        ["none", "direct", "mutual", "tree"],  # recursion
        [0, 1, 3, 6],                       # call_depth
        [0, 2, 4, 8],                       # branchiness
        ["none", "seq", "stride", "chase"],  # mem
        ["int", "muldiv", "mixed"],         # mix
    ))
    # drop degenerate combos: no loops AND no recursion = near-empty program
    space = [c for c in space if not (c[0] == 0 and c[3] == "none")]
    rng.shuffle(space)
    chosen = space[:target]

    manifest = []
    for i, combo in enumerate(chosen):
        pid = "synth_%04d" % i
        src = emit_program(pid, *combo)
        (OUT / (pid + ".c")).write_text(src)
        manifest.append([pid, *combo])

    with open(OUT / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "loops", "nest", "trip", "recursion",
                    "call_depth", "branchiness", "mem", "mix"])
        w.writerows(manifest)
    print("wrote %d programs to %s" % (len(chosen), OUT))


if __name__ == "__main__":
    main()
