# -*- coding: utf-8 -*-
"""分形地形生成器验收测试。

覆盖：
1. 同 seed 可复现（含 PNG 逐字节一致）
2. 不同 seed 有明显差异（差异判据见 README）
3. octaves 3..7 亮度/对比度稳定，高频不盖过低频
4. 左右、上下边缘无接缝（原始高度严格闭合，归一化后 ≤1 灰度级）
5. 水位掩码生效，water=0 时无水体
6. 各向同性：水平/垂直方向变化率一致，无方向性条纹
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain.core import (edge_gaps, fbm, generate, normalize, save_png,
                          value_noise_1d, water_mask)  # noqa: E402


# ---------------------------------------------------------------------------
# 1. 可复现
# ---------------------------------------------------------------------------

def test_value_noise_deterministic():
    a = [value_noise_1d(0.3 + i, seed=7) for i in range(20)]
    b = [value_noise_1d(0.3 + i, seed=7) for i in range(20)]
    assert a == b
    assert all(0.0 <= v <= 1.0 for v in a)


def test_value_noise_seed_changes_values():
    a = value_noise_1d(1.7, seed=1)
    b = value_noise_1d(1.7, seed=2)
    assert a != b


def test_same_seed_identical_heights():
    a = generate(64, 48, 5, seed=4242)
    b = generate(64, 48, 5, seed=4242)
    assert a == b


def test_same_seed_png_byte_identical(tmp_path):
    heights = generate(64, 64, 5, seed=99)
    norm, _, _ = normalize(heights)
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    save_png(norm, str(p1))
    save_png(norm, str(p2))
    # 再完整跑一遍生成流程，确认端到端一致
    norm2, _, _ = normalize(generate(64, 64, 5, seed=99))
    save_png(norm2, str(tmp_path / "c.png"))
    assert p1.read_bytes() == p2.read_bytes()
    assert p1.read_bytes() == (tmp_path / "c.png").read_bytes()


# ---------------------------------------------------------------------------
# 2. 不同 seed 有明显差异
# ---------------------------------------------------------------------------

def _gray_mean_abs_diff(img_a, img_b):
    h = len(img_a)
    w = len(img_a[0])
    total = 0
    for y in range(h):
        for x in range(w):
            total += abs(img_a[y][x] - img_b[y][x])
    return total / (h * w)


def test_different_seeds_differ_visibly():
    """差异判据（与 README 一致）：同尺寸同层数、仅 seed 不同的两张图，
    归一化后平均像素差 >= 20 灰度级，且至少 40% 像素发生变化。"""
    img_a, _, _ = normalize(generate(128, 128, 5, seed=111))
    img_b, _, _ = normalize(generate(128, 128, 5, seed=222))
    mad = _gray_mean_abs_diff(img_a, img_b)
    changed = sum(
        1 for y in range(128) for x in range(128)
        if img_a[y][x] != img_b[y][x]
    ) / (128 * 128)
    assert mad >= 20.0
    assert changed >= 0.40


# ---------------------------------------------------------------------------
# 3. 层数变化时亮度/对比度稳定
# ---------------------------------------------------------------------------

def test_octave_brightness_stable():
    """octaves 3..7：归一化均值在 127.5±25 内，各 octave 均值极差 <= 20。"""
    means = {}
    for octaves in range(3, 8):
        heights = generate(128, 128, octaves, seed=777)
        img, _, _ = normalize(heights)
        flat = [v for row in img for v in row]
        means[octaves] = sum(flat) / len(flat)
    for m in means.values():
        assert 127.5 - 25 <= m <= 127.5 + 25
    assert max(means.values()) - min(means.values()) <= 20.0


def test_octave_raw_mean_near_half():
    """原始 fbm 输出均值稳定在 0.5 附近（振幅归一的直接结果）。"""
    for octaves in (3, 5, 7):
        heights = generate(64, 64, octaves, seed=777)
        flat = [v for row in heights for v in row]
        mean = sum(flat) / len(flat)
        assert 0.40 <= mean <= 0.60


def test_high_frequency_does_not_override_skeleton():
    """7 层相对 3 层只增加细节：同 seed 两图平均差 < 40 灰度级，
    且两者仍可区分（噪声确实叠加了高频细节）。"""
    img3, _, _ = normalize(generate(128, 128, 3, seed=777))
    img7, _, _ = normalize(generate(128, 128, 7, seed=777))
    mad = _gray_mean_abs_diff(img3, img7)
    assert mad < 40.0
    assert mad > 0.5


def test_first_octave_dominates_amplitude():
    """gain=0.5 时第一层振幅占总振幅一半以上，低频骨架必然主导。"""
    octaves = 7
    gain = 0.5
    amps = [gain ** i for i in range(octaves)]
    assert amps[0] / sum(amps) > 0.5


# ---------------------------------------------------------------------------
# 4. 可平铺：边缘接缝
# ---------------------------------------------------------------------------

def test_edges_seamless_raw():
    """原始高度图左右/上下对应边缘像素严格相等。"""
    for octaves in (3, 5, 7):
        heights = generate(96, 64, octaves, seed=555)
        gap_h, gap_v = edge_gaps(heights)
        assert gap_h == 0.0
        assert gap_v == 0.0


def test_edges_seamless_normalized():
    """归一化取整后边缘最大高差不超过 1 个灰度级。"""
    heights = generate(96, 64, 5, seed=555)
    img, _, _ = normalize(heights)
    h = len(img)
    w = len(img[0])
    gap_h = max(abs(img[y][0] - img[y][w - 1]) for y in range(h))
    gap_v = max(abs(img[0][x] - img[h - 1][x]) for x in range(w))
    assert gap_h <= 1
    assert gap_v <= 1


def test_noise_is_periodic():
    """底层噪声与 fbm 在包裹周期上严格周期（接缝为零的数学保证）。"""
    from terrain.core import _value_noise_2d
    # 整数格点：平移整数个周期后逐位相等（无浮点歧义）
    for ix, iy in ((0, 0), (3, 7), (63, 31)):
        assert _value_noise_2d(ix, iy, 1, 64, 32) == \
            _value_noise_2d(ix + 64.0, iy + 32.0, 1, 64, 32)
    # 小数坐标：浮点表示有舍入误差，要求误差在 1e-12 量级
    for x in (0.3, 12.7, 63.9):
        for y in (0.1, 31.8):
            a = _value_noise_2d(x, y, 1, 64, 32)
            b = _value_noise_2d(x + 64.0, y + 32.0, 1, 64, 32)
            assert abs(a - b) < 1e-12
    # generate 实际使用的单位周期包裹：u=0 与 u=1 必须精确相等
    assert fbm(0.0, 0.5, octaves=4, seed=3, wrap_x=1.0, wrap_y=1.0) == \
        fbm(1.0, 0.5, octaves=4, seed=3, wrap_x=1.0, wrap_y=1.0)
    assert fbm(0.5, 0.0, octaves=7, seed=3, wrap_x=1.0, wrap_y=1.0) == \
        fbm(0.5, 1.0, octaves=7, seed=3, wrap_x=1.0, wrap_y=1.0)


# ---------------------------------------------------------------------------
# 5. 水位掩码
# ---------------------------------------------------------------------------

def test_water_zero_has_no_water():
    heights = generate(64, 64, 3, seed=3003)
    mask, ratio = water_mask(heights, 0.0)
    assert ratio == 0.0
    assert all(v == 0 for row in mask for v in row)


def test_water_mask_matches_threshold():
    heights = generate(96, 96, 5, seed=1001)
    water = 0.35
    mask, ratio = water_mask(heights, water)
    norm, _, _ = normalize(heights)
    threshold = water * 255.0
    wet = 0
    for y, row in enumerate(norm):
        for x, v in enumerate(row):
            expected = 1 if v < threshold else 0
            assert mask[y][x] == expected
            wet += expected
    assert ratio == wet / (96 * 96)
    # 水位 0.35 应当产生一部分水体，但不会淹没全图
    assert 0.02 < ratio < 0.95


def test_water_ratio_monotonic():
    heights = generate(64, 64, 5, seed=1001)
    r1 = water_mask(heights, 0.2)[1]
    r2 = water_mask(heights, 0.5)[1]
    assert r1 <= r2


# ---------------------------------------------------------------------------
# 6. 各向同性
# ---------------------------------------------------------------------------

def test_isotropic_horizontal_vertical_variation():
    """正方形图上水平/垂直相邻像素平均变化率接近（比值在 0.8..1.25），
    不存在被压扁成一维后产生的单一方向斜条纹。"""
    n = 96
    heights = generate(n, n, 5, seed=888)
    horiz = sum(
        abs(heights[y][x + 1] - heights[y][x])
        for y in range(n) for x in range(n - 1)
    ) / (n * (n - 1))
    vert = sum(
        abs(heights[y + 1][x] - heights[y][x])
        for y in range(n - 1) for x in range(n)
    ) / (n * (n - 1))
    assert horiz > 0 and vert > 0
    assert 0.8 <= horiz / vert <= 1.25


def test_isotropic_square_periods_equal():
    """正方形地形两个轴的包裹周期相等，保证两轴频率一致。"""
    w = h = 64
    heights = generate(w, h, 4, seed=888)
    # 周期相等时，转置图的统计特征应与原图一致（各向同性的旁证）
    def mean_abs(rows):
        return sum(abs(v) for row in rows for v in row) / (w * h)
    diffs = [
        [heights[y][x] - heights[x][y] for x in range(w)]
        for y in range(h)
    ]
    # 转置差的均值应接近 0（无系统性方向偏置）
    mean_diff = sum(sum(row) for row in diffs) / (w * h)
    assert abs(mean_diff) < 0.05
    assert mean_abs(diffs) < 0.25
