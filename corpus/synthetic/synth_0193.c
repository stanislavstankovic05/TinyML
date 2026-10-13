/* synthetic corpus program synth_0193
 * loops=4 nest=4 trip=s rec=mutual calls=3 branch=2 mem=none mix=muldiv */
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
static u32 chain3(u32 x) { return x ^ (x >> 3) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
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
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < 64u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        for (u32 i1_3 = 0; i1_3 < 8u; i1_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i2_0 = 0; i2_0 < 64u; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      for (u32 i2_2 = 0; i2_2 < 8u; i2_2++) {
        for (u32 i2_3 = 0; i2_3 < 8u; i2_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          acc += chain1(x);
        }
      }
    }
  }
  for (u32 i3_0 = 0; i3_0 < 64u; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      for (u32 i3_2 = 0; i3_2 < 8u; i3_2++) {
        for (u32 i3_3 = 0; i3_3 < 8u; i3_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          acc += chain1(x);
        }
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
