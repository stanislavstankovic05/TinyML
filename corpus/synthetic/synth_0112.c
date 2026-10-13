/* synthetic corpus program synth_0112
 * loops=2 nest=3 trip=l rec=mutual calls=0 branch=2 mem=none mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
static u32 rec_b(u32 n, u32 acc);
static u32 rec_a(u32 n, u32 acc) {
  if (n == 0u) return acc;
  return rec_b(n - 1u, acc + n);
}
static u32 rec_b(u32 n, u32 acc) {
  if (n == 0u) return acc ^ 0x5aa5u;
  return rec_a(n - 1u, acc + (acc << 2));
}
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
        if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < 4096u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
        if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      }
    }
  }
  acc = rec_a((s & 31u) + 8u, acc);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
