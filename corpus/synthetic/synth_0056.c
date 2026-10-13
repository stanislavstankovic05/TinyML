/* synthetic corpus program synth_0056
 * loops=4 nest=4 trip=l rec=none calls=0 branch=0 mem=none mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        for (u32 i0_3 = 0; i0_3 < 8u; i0_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
        }
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < 4096u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        for (u32 i1_3 = 0; i1_3 < 8u; i1_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
        }
      }
    }
  }
  for (u32 i2_0 = 0; i2_0 < 4096u; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      for (u32 i2_2 = 0; i2_2 < 8u; i2_2++) {
        for (u32 i2_3 = 0; i2_3 < 8u; i2_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
        }
      }
    }
  }
  for (u32 i3_0 = 0; i3_0 < 4096u; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      for (u32 i3_2 = 0; i3_2 < 8u; i3_2++) {
        for (u32 i3_3 = 0; i3_3 < 8u; i3_3++) {
          u32 x = lcg(&s);
          acc += (x ^ (acc << 3)) + (x >> 2);
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
