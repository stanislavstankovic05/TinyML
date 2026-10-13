/* synthetic corpus program synth_0291
 * loops=4 nest=1 trip=dyn rec=direct calls=3 branch=0 mem=none mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
static u32 rec_f(u32 n, u32 acc) {
  if (n == 0u) return acc;
  return rec_f(n - 1u, acc + (n ^ (acc << 1)));
}
static u32 chain3(u32 x) { return x ^ (x >> 3) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < n; i0_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
    acc += chain1(x);
  }
  for (u32 i1_0 = 0; i1_0 < n; i1_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
    acc += chain1(x);
  }
  for (u32 i2_0 = 0; i2_0 < n; i2_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
    acc += chain1(x);
  }
  for (u32 i3_0 = 0; i3_0 < n; i3_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
    acc += chain1(x);
  }
  acc = rec_f((s & 63u) + 8u, acc);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = ((u32)argc * 512u) + 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
