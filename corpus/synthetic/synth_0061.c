/* synthetic corpus program synth_0061
 * loops=1 nest=4 trip=s rec=none calls=0 branch=4 mem=none mix=muldiv */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 64u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        for (u32 i0_3 = 0; i0_3 < 8u; i0_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
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
