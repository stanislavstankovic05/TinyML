/* synthetic corpus program synth_0001
 * loops=4 nest=4 trip=l rec=mutual calls=0 branch=4 mem=chase mix=muldiv */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
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
  u32 nxt = s & (ASIZE-1);
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        for (u32 i0_3 = 0; i0_3 < 8u; i0_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
        }
      }
    }
  }
  for (u32 i1_0 = 0; i1_0 < 4096u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      for (u32 i1_2 = 0; i1_2 < 8u; i1_2++) {
        for (u32 i1_3 = 0; i1_3 < 8u; i1_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
        }
      }
    }
  }
  for (u32 i2_0 = 0; i2_0 < 4096u; i2_0++) {
    for (u32 i2_1 = 0; i2_1 < 8u; i2_1++) {
      for (u32 i2_2 = 0; i2_2 < 8u; i2_2++) {
        for (u32 i2_3 = 0; i2_3 < 8u; i2_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
        }
      }
    }
  }
  for (u32 i3_0 = 0; i3_0 < 4096u; i3_0++) {
    for (u32 i3_1 = 0; i3_1 < 8u; i3_1++) {
      for (u32 i3_2 = 0; i3_2 < 8u; i3_2++) {
        for (u32 i3_3 = 0; i3_3 < 8u; i3_3++) {
          u32 x = lcg(&s);
          acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
          if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
          if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
          if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
          if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
          nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
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
