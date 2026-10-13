/* synthetic corpus program synth_0026
 * loops=1 nest=4 trip=l rec=none calls=3 branch=2 mem=none mix=mixed */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
static u32 chain3(u32 x) { return x ^ (x >> 3) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        for (u32 i0_3 = 0; i0_3 < 8u; i0_3++) {
          u32 x = lcg(&s);
          acc += (x * 31u) ^ (acc / ((x & 0x3fu) + 1u)) + (x >> 1);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          acc += chain1(x);
        }
      }
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
