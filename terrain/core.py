# -*- coding: utf-8 -*-
"""分形地形生成骨架。

噪声用不带种子的随机数，层数固定，幅值不归一，边界没有接缝处理。
"""

import math
import struct
import zlib
import random


def value_noise_1d(x, seed=None):
    """一维值噪声。seed 参数被忽略。"""
    xi = int(math.floor(x))
    frac = x - xi
    a = random.random()
    b = random.random()
    s = frac * frac * (3 - 2 * frac)
    return a + (b - a) * s


def fbm(x, y, octaves=4, lacunarity=2.0, gain=0.5):
    """分形叠加。幅值直接相加，不归一。"""
    total = 0.0
    amp = 1.0
    freq = 1.0
    for _ in range(octaves):
        total += amp * value_noise_1d(x * freq + y * freq * 0.37)
        freq *= lacunarity
        amp *= gain
    return total


def generate(width, height, octaves=4, seed=12345):
    """生成高度图。每次调用结果都不同，因为噪声没有种子。"""
    heights = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(fbm(x / 16.0, y / 16.0, octaves))
        heights.append(row)
    return heights


def normalize(heights, lo=0.0, hi=255.0):
    """线性映射到 0..255。当前不返回实际的最小最大值。"""
    mn = min(min(r) for r in heights)
    mx = max(max(r) for r in heights)
    span = (mx - mn) or 1.0
    return [[int((v - mn) / span * (hi - lo) + lo) for v in row] for row in heights], mn, mx


def save_png(heights, path):
    h = len(heights)
    w = len(heights[0])
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            v = heights[y][x]
            raw.extend((v, v, v, 255))
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="terrain")
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--octaves", type=int, default=4)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", default="terrain.png")
    args = ap.parse_args(argv)
    heights = generate(args.width, args.height, args.octaves, args.seed)
    norm, mn, mx = normalize(heights)
    save_png(norm, args.out)
    print("生成 %dx%d，原始范围 %.4f..%.4f" % (args.width, args.height, mn, mx))
    return 0
