/* synthetic corpus program synth_0275
 * loops=4 nest=2 trip=l rec=none calls=6 branch=2 mem=none mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
static u32 chain6(u32 x) { return x ^ (x >> 3) + 42u; }
static u32 chain5(u32 x) { return chain6(x + 5u) + 35u; }
static u32 chain4(u32 x) { return chain5(x + 4u) + 28u; }
static u32 chain3(u32 x) { return chain4(x + 3u) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      u32 x = lcg(&s);
      acc += (x ^ (acc << 3)) + (x >> 2);
      if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
      if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      acc += chain1(x);
    }
  }
  for (u32 i1_0 = 0; i1_0 < 4096u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      u32 x = lcg(&s);
      acc += (x ^ (acc << 3)) + (x >> 2);
      if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
      if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      acc += chain1(x);
    }
  }
  for (u32 i2_0 = 0; i2_0 < 4096u; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      u32 x = lcg(&s);
      acc += (x ^ (acc << 3)) + (x >> 2);
      if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
      if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      acc += chain1(x);
    }
  }
  for (u32 i3_0 = 0; i3_0 < 4096u; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      u32 x = lcg(&s);
      acc += (x ^ (acc << 3)) + (x >> 2);
      if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
      if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
      acc += chain1(x);
    }
  }
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
