# -*- coding: utf-8 -*-
"""可复现、可平铺的分形地形生成器（仅依赖 Python 标准库）。

设计要点
--------
1. 可复现：噪声格点值由整数哈希 ``_hash2`` 产生，只依赖坐标与 seed，
   不再使用全局 ``random`` 状态，同一 seed 任意两次运行逐位一致。
2. 各向同性：``_value_noise_2d`` 对 x/y 两个轴做完全对称的 smoothstep
   双线性插值，两个方向的频率与插值方式一致，不会出现单一方向条纹。
3. 可平铺：噪声格点按周期 ``wrap_x``/``wrap_y`` 取模，基频周期取图像
   宽高，lacunarity=2 时每层周期均为整数且整除上一层，噪声严格周期，
   左右、上下边缘天然闭合。
4. 振幅归一：``fbm`` 把各层振幅除以振幅之和，输出恒在 [0, 1]，
   octaves 从 3 变到 7 时均值与对比度保持稳定，低频层始终占主导。
5. 水位：``water_mask`` 按归一化高度与水位阈值生成水体掩码并可导出 PNG。
"""

import math
import struct
import zlib


# ---------------------------------------------------------------------------
# 确定性哈希与值噪声
# ---------------------------------------------------------------------------

def _hash1(i, seed=0):
    """一维整数格点 -> [0, 1) 的确定性哈希。

    纯整数运算（32 位掩码），结果只依赖 ``i`` 与 ``seed``，跨平台一致。
    """
    h = (int(seed) * 0x9E3779B1 + int(i) * 0x85EBCA77 + 0x165667B1) & 0xFFFFFFFF
    h = (h ^ (h >> 15)) * 0x2C1B3C6D & 0xFFFFFFFF
    h ^= h >> 13
    return (h & 0xFFFFFFFF) / 4294967296.0


def _hash2(ix, iy, seed=0):
    """二维整数格点 -> [0, 1) 的确定性哈希。"""
    h = (int(seed) * 0x9E3779B1 + int(ix) * 0x85EBCA77
         + int(iy) * 0xC2B2AE3D + 0x165667B1) & 0xFFFFFFFF
    h = (h ^ (h >> 15)) * 0x2C1B3C6D & 0xFFFFFFFF
    h ^= h >> 13
    return (h & 0xFFFFFFFF) / 4294967296.0


def _smoothstep(t):
    """Hermite smoothstep：一阶导数在格点处为 0，层间衔接无折痕。"""
    return t * t * (3.0 - 2.0 * t)


def value_noise_1d(x, seed=None):
    """一维值噪声，输出 [0, 1]，仅由 ``x`` 与 ``seed`` 决定。

    保留骨架中的名字与位置参数；``seed`` 缺省（None）时按固定种子 0
    处理，因此同样可复现。相邻整数格点间用 smoothstep 插值。
    """
    if seed is None:
        seed = 0
    xi = int(math.floor(x))
    frac = x - xi
    a = _hash1(xi, seed)
    b = _hash1(xi + 1, seed)
    s = _smoothstep(frac)
    return a + (b - a) * s


def _value_noise_2d(x, y, seed=0, wrap_x=0, wrap_y=0):
    """二维周期值噪声，输出 [0, 1]。

    ``wrap_x``/``wrap_y`` 为 0 表示该方向不做周期包裹，否则格点坐标按
    该周期取模——这是可平铺的基础：周期为图像尺寸时，边缘两侧的格点
    值完全相同，插值结果严格闭合。
    """
    xi = int(math.floor(x))
    yi = int(math.floor(y))
    fx = _smoothstep(x - xi)
    fy = _smoothstep(y - yi)

    x0 = xi % wrap_x if wrap_x else xi
    x1 = (xi + 1) % wrap_x if wrap_x else xi + 1
    y0 = yi % wrap_y if wrap_y else yi
    y1 = (yi + 1) % wrap_y if wrap_y else yi + 1

    v00 = _hash2(x0, y0, seed)
    v10 = _hash2(x1, y0, seed)
    v01 = _hash2(x0, y1, seed)
    v11 = _hash2(x1, y1, seed)

    top = v00 + (v10 - v00) * fx
    bottom = v01 + (v11 - v01) * fx
    return top + (bottom - top) * fy


# ---------------------------------------------------------------------------
# 分形叠加
# ---------------------------------------------------------------------------

def fbm(x, y, octaves=4, lacunarity=2.0, gain=0.5, seed=0,
        wrap_x=0, wrap_y=0, base_frequency=4.0):
    """分形布朗运动（二维），输出归一化到 [0, 1]。

    保留骨架的位置参数 ``x, y, octaves, lacunarity, gain``；新增的
    ``seed``/``wrap_x``/``wrap_y``/``base_frequency`` 均为带默认值的
    关键字参数。

    ``base_frequency`` 是基频层在整个采样区间内的噪声格数（默认 4）：
    保证最低频层承载 4×4 个大尺度地貌单元而不是一个常数格；取整数时
    配合单位包裹周期，``u=0`` 与 ``u=1`` 仍落在同周期格点上，平铺
    精确闭合。

    每层振幅除以全部振幅之和（振幅归一），因此无论 octaves 取多少，
    输出范围恒为 [0, 1]、均值稳定在 0.5 附近，且第一层（最低频）
    振幅最大，高频细节不会盖过低频地貌骨架。
    """
    octaves = max(1, int(octaves))
    total = 0.0
    amp_sum = 0.0
    amp = 1.0
    freq = float(base_frequency)
    for layer in range(octaves):
        # 每层独立换盐，避免不同频率采样到同一组格点值。
        layer_seed = (int(seed) * 1000003 + layer * 0x9E3779B1) & 0x7FFFFFFF
        wx = int(round(wrap_x * freq)) if wrap_x else 0
        wy = int(round(wrap_y * freq)) if wrap_y else 0
        total += amp * _value_noise_2d(x * freq, y * freq,
                                       layer_seed, wx, wy)
        amp_sum += amp
        freq *= lacunarity
        amp *= gain
    return total / amp_sum


# ---------------------------------------------------------------------------
# 地形生成 / 归一化 / 输出
# ---------------------------------------------------------------------------

def generate(width, height, octaves=4, seed=12345):
    """生成原始高度图（二维 list，每个值在 [0, 1]）。

    在归一化坐标 ``u = x/(width-1)``、``v = y/(height-1)`` 上采样，
    噪声包裹周期取 1.0：

    * **可平铺（精确闭合）**：首列 ``u=0`` 与末列 ``u=1`` 在每一层都
      落在同一个整数格点上（frac 恰为 0，取模后格点哈希相同），因此
      左右、上下对应边缘像素逐位相等，拼接高差严格为 0；smoothstep
      在格点处导数为 0，接缝处同时 C1 连续。
    * **各向同性**：一个完整噪声周期在物理像素上的波长就是图像的
      宽/高，x、y 方向每像素的频率完全一致。
    """
    width = int(width)
    height = int(height)
    heights = [[0.0] * width for _ in range(height)]
    for y in range(height):
        v = y / (height - 1)
        for x in range(width):
            u = x / (width - 1)
            heights[y][x] = fbm(u, v, octaves=octaves, seed=seed,
                                wrap_x=1.0, wrap_y=1.0)
    return heights


def normalize(heights, lo=0.0, hi=255.0):
    """线性映射到 0..255，返回 (整数高度图, 原图最小值, 原图最大值)。

    名字、位置参数与返回三元组的结构与骨架保持一致。
    """
    mn = min(min(r) for r in heights)
    mx = max(max(r) for r in heights)
    span = (mx - mn) or 1.0
    out = [[int(round((v - mn) / span * (hi - lo) + lo)) for v in row]
           for row in heights]
    return out, mn, mx


def save_png(heights, path):
    """把 0..255 的高度图存为 8 位灰度 RGBA PNG（纯标准库）。

    写入内容只取决于像素数据：没有时间戳等元数据，同样的高度图
    逐字节产出同样的文件。
    """
    h = len(heights)
    w = len(heights[0])
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        for x in range(w):
            v = heights[y][x]
            raw.extend((v, v, v, 255))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# 水位与报告
# ---------------------------------------------------------------------------

def water_mask(heights, water):
    """按水位（0..1 的高度分位阈值）生成水体掩码。

    掩码与高度图同形，水下为 1、陆地为 0。阈值按 *归一化后* 的高度
    判定：``water=0.35`` 表示归一化高度低于 35% 量程的像素为水体；
    ``water=0`` 时严格没有任何像素入选，保证零水位地貌不出现水体。
    返回 (mask, water_ratio)。
    """
    water = float(water)
    norm, _mn, _mx = normalize(heights)
    threshold = water * 255.0
    total = len(norm) * len(norm[0])
    mask = [[0] * len(norm[0]) for _ in norm]
    wet = 0
    for y, row in enumerate(norm):
        for x, v in enumerate(row):
            if v < threshold:
                mask[y][x] = 1
                wet += 1
    return mask, wet / total


def save_mask_png(mask, path):
    """把水体掩码存成 PNG：水体深蓝，陆地透明，便于叠加检查。"""
    h = len(mask)
    w = len(mask[0])
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            if mask[y][x]:
                raw.extend((20, 60, 160, 255))
            else:
                raw.extend((0, 0, 0, 0))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def edge_gaps(heights):
    """返回 (左右边缘最大高差, 上下边缘最大高差)。

    可平铺地形这两个值都应为 0（原始高度层面严格闭合；归一化取整后
    最多相差 1 个灰度级）。
    """
    h = len(heights)
    w = len(heights[0])
    horizontal = max(abs(heights[y][0] - heights[y][w - 1]) for y in range(h))
    vertical = max(abs(heights[0][x] - heights[h - 1][x]) for x in range(w))
    return horizontal, vertical


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="terrain")
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--octaves", type=int, default=4)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--water", type=float, default=0.0,
                    help="水位阈值（0..1 高度分位），0 表示不生成水体")
    ap.add_argument("--out", default="terrain.png")
    ap.add_argument("--mask-out", default=None,
                    help="可选：水体掩码 PNG 输出路径")
    args = ap.parse_args(argv)

    heights = generate(args.width, args.height, args.octaves, args.seed)
    norm, mn, mx = normalize(heights)
    save_png(norm, args.out)

    gap_h, gap_v = edge_gaps(heights)
    print("生成 %dx%d octaves=%d seed=%d" %
          (args.width, args.height, args.octaves, args.seed))
    print("原始高度范围 %.6f..%.6f" % (mn, mx))
    print("边缘最大高差: 左右 %.6f / 上下 %.6f" % (gap_h, gap_v))

    if args.water > 0.0:
        mask, ratio = water_mask(heights, args.water)
        mask_path = args.mask_out or (args.out.rsplit(".", 1)[0] + "_water.png")
        save_mask_png(mask, mask_path)
        print("水位 %.2f，水域占比 %.4f，掩码 -> %s" %
              (args.water, ratio, mask_path))
    return 0
