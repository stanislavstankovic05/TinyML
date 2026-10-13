/* synthetic corpus program synth_0166
 * loops=4 nest=4 trip=dyn rec=direct calls=3 branch=4 mem=none mix=int */
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
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        for (u32 i0_3 = 0; i0_3 < 8u; i0_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < n; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        for (u32 i1_3 = 0; i1_3 < 8u; i1_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i2_0 = 0; i2_0 < n; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      for (u32 i2_2 = 0; i2_2 < 8u; i2_2++) {
        for (u32 i2_3 = 0; i2_3 < 8u; i2_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i3_0 = 0; i3_0 < n; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      for (u32 i3_2 = 0; i3_2 < 8u; i3_2++) {
        for (u32 i3_3 = 0; i3_3 < 8u; i3_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          acc += chain1(x);
        }
      }
    }
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
