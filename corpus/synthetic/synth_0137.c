/* synthetic corpus program synth_0137
 * loops=4 nest=3 trip=l rec=direct calls=6 branch=0 mem=seq mix=int */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
static u32 rec_f(u32 n, u32 acc) {
  if (n == 0u) return acc;
  return rec_f(n - 1u, acc + (n ^ (acc << 1)));
}
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
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        arr[i0_0 & (ASIZE-1)] = acc; acc += arr[(i0_0 + 1) & (ASIZE-1)];
        acc += chain1(x);
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < 4096u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        arr[i1_0 & (ASIZE-1)] = acc; acc += arr[(i1_0 + 1) & (ASIZE-1)];
        acc += chain1(x);
      }
    }
  }
  for (u32 i2_0 = 0; i2_0 < 4096u; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      for (u32 i2_2 = 0; i2_2 < 8u; i2_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        arr[i2_0 & (ASIZE-1)] = acc; acc += arr[(i2_0 + 1) & (ASIZE-1)];
        acc += chain1(x);
      }
    }
  }
  for (u32 i3_0 = 0; i3_0 < 4096u; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      for (u32 i3_2 = 0; i3_2 < 8u; i3_2++) {
        u32 x = lcg(&s);
        acc += (x ^ (acc << 3)) + (x >> 2);
        arr[i3_0 & (ASIZE-1)] = acc; acc += arr[(i3_0 + 1) & (ASIZE-1)];
        acc += chain1(x);
      }
    }
  }
  acc = rec_f((s & 63u) + 8u, acc);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
