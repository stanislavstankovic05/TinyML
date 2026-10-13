/* synthetic corpus program synth_0224
 * loops=4 nest=1 trip=dyn rec=mutual calls=0 branch=0 mem=none mix=int */
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
  for (u32 i0_0 = 0; i0_0 < n; i0_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
  }
  for (u32 i1_0 = 0; i1_0 < n; i1_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
  }
  for (u32 i2_0 = 0; i2_0 < n; i2_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
  }
  for (u32 i3_0 = 0; i3_0 < n; i3_0++) {
    u32 x = lcg(&s);
    acc += (x ^ (acc << 3)) + (x >> 2);
  }
  acc = rec_a((s & 31u) + 8u, acc);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = ((u32)argc * 512u) + 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
