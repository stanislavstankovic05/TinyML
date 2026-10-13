/* synthetic corpus program synth_0123
 * loops=2 nest=3 trip=dyn rec=none calls=1 branch=8 mem=none mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
static u32 chain1(u32 x) { return x ^ (x >> 3) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < n; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
        if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
        if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
        if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
        if ((x & 16u) == 0u) acc += 53u; else acc ^= (x >> 5);
        if ((x & 32u) == 0u) acc += 66u; else acc ^= (x >> 1);
        if ((x & 64u) == 0u) acc += 79u; else acc ^= (x >> 2);
        if ((x & 128u) == 0u) acc += 92u; else acc ^= (x >> 3);
        acc += chain1(x);
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < n; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
        if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
        if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
        if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
        if ((x & 16u) == 0u) acc += 53u; else acc ^= (x >> 5);
        if ((x & 32u) == 0u) acc += 66u; else acc ^= (x >> 1);
        if ((x & 64u) == 0u) acc += 79u; else acc ^= (x >> 2);
        if ((x & 128u) == 0u) acc += 92u; else acc ^= (x >> 3);
        acc += chain1(x);
      }
    }
  }
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = ((u32)argc * 512u) + 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
