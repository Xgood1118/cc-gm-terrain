# 分形地形生成

可复现、可平铺的二维分形地形生成器，**仅使用 Python 标准库**（`math`/`struct`/`zlib` 等），
无第三方依赖。保留了骨架中 `value_noise_1d`、`fbm`、`generate`、`normalize`、`save_png`
的名字与位置参数签名。

## 实现要点

### 1. 可复现（确定性哈希）

噪声格点值不再来自全局 `random`，而是纯整数哈希函数 `_hash2(ix, iy, seed)`
（32 位掩码运算，跨平台一致），输出只依赖坐标与 seed。PNG 写入也不含时间戳等
元数据，因此同一 seed 任意两次运行产出的文件**逐字节相同**。

**不同 seed 的差异判据**（同时满足，见 `tests/test_terrain.py::test_different_seeds_differ_visibly`）：

- 同尺寸、同层数、仅 seed 不同的两张归一化图，平均像素差（MAD）**≥ 20 灰度级**；
- 至少 **40%** 的像素取值发生变化。

实测 seed 111 vs 222（128×128, octaves=5）：MAD = 56.6，99.5% 像素变化。

### 2. 各向同性

骨架把二维坐标压成一维（`x + y*0.37`），两个轴频率不一致且产生斜条纹。现在
`_value_noise_2d` 对 x、y 两轴做完全对称的 smoothstep 双线性插值，采样坐标为
归一化的 `u = x/(W-1)`、`v = y/(H-1)`，两个方向每个像素的频率严格相等。

判据（`test_isotropic_horizontal_vertical_variation`）：正方形图上水平相邻像素
平均变化率与垂直相邻像素平均变化率之比在 **0.8 ~ 1.25** 内（理想值 1.0）。
实测 5 个 seed 比值在 0.94 ~ 1.01。

### 3. 层叠加（振幅归一）

`fbm` 中每层振幅按全部振幅之和归一：`value = Σ(aᵢ·nᵢ) / Σaᵢ`，其中 `aᵢ = gain^i`。

- 输出恒在 [0, 1]，无论 octaves 取多少，均值稳定在 0.5 附近；
- 第一层（最低频）振幅占总振幅 50% 以上（gain=0.5 时），高频细节不可能
  盖过低频地貌骨架；
- 实测 octaves 3→7（同 seed 128×128）：原始均值 0.5136~0.5146（极差 0.001），
  归一化灰度均值极差仅 3 个灰度级。

基频由 `base_frequency`（默认 4）控制：基频层含 4×4 个大尺度地貌单元，
避免单格常数化；取整数保证与平铺周期兼容。

### 4. 可平铺（边缘严格闭合）

噪声格点按包裹周期取模（`_value_noise_2d` 的 `wrap_x/wrap_y`）。采样在
归一化坐标上进行、包裹周期为 1.0：首列 `u=0` 与末列 `u=1` 在每一层都落在
**同一个整数格点**（frac 恰为 0，取模后格点哈希相同），因此：

- 左右、上下对应边缘像素**逐位相等**，边缘最大高差严格为 **0.0**；
- smoothstep 在格点处导数为 0，接缝同时满足 C1 连续，平铺无折痕；
- lacunarity=2 且基频为整数时，每层周期都是整数且整除上一层，所有高频层同样闭合。

判据（`test_edges_seamless_raw` / `test_edges_seamless_normalized`）：
原始高度图边缘高差 == 0；归一化取整后边缘高差 ≤ 1 灰度级。

### 5. 水位与水体掩码

`specs.json` 中的 `water` 是 **0~1 的高度分位阈值**：归一化后灰度值
`v < 255 × water` 的像素判为水体。`water_mask(heights, water)` 返回
`(mask, water_ratio)`，掩码为同形二维数组（水下 1、陆地 0），
`save_mask_png` 导出深蓝/透明掩码 PNG。

- `water = 0` 时阈值为 0，没有任何像素满足 `v < 0`，**保证零水位无水体**
  （`test_water_zero_has_no_water`）；
- 水域占比随水位单调不减（`test_water_ratio_monotonic`）。

## 生成结果（按 data/specs.json 依次生成）

`python gen_samples.py` 读取 `data/specs.json`（只读，不修改），向 `output/`
输出高度图 PNG、水体掩码 PNG 与 `report.txt`：

| 地貌 | seed | octaves | 原始高度范围 | 水位 | 水域占比 | 左右边缘最大高差 | 上下边缘最大高差 |
|---|---|---|---|---|---|---|---|
| island | 1001 | 5 | 0.167314 ~ 0.823521 | 0.35 | 0.2950 | 0.000000 | 0.000000 |
| mountain | 2002 | 7 | 0.141257 ~ 0.714814 | 0.05 | 0.0016 | 0.000000 | 0.000000 |
| dunes | 3003 | 3 | 0.218898 ~ 0.861661 | 0.00 | 0.0000 | 0.000000 | 0.000000 |

（高度范围为 `generate` 输出的原始 [0,1] 高度；高差为原始高度层面的值，
归一化取整后仍 ≤ 1 灰度级。dunes 水位为 0，不产出水体且水域占比为 0。）

## 运行

```
python gen_samples.py                              # 按 specs.json 生成三张地形
python -m terrain.cli --width 256 --height 256 --octaves 5 --seed 1001 \
       --water 0.35 --out island.png --mask-out island_water.png
python -m pytest tests -q                          # 全部测试
```

## 测试覆盖（20 个用例，全部通过）

| 需求 | 测试 |
|---|---|
| 同 seed 一致（含 PNG 逐字节） | `test_value_noise_deterministic`、`test_same_seed_identical_heights`、`test_same_seed_png_byte_identical` |
| 不同 seed 有明显差异 | `test_value_noise_seed_changes_values`、`test_different_seeds_differ_visibly` |
| 层数变化亮度稳定、高频不盖低频 | `test_octave_brightness_stable`、`test_octave_raw_mean_near_half`、`test_high_frequency_does_not_override_skeleton`、`test_first_octave_dominates_amplitude` |
| 边缘接缝 | `test_edges_seamless_raw`、`test_edges_seamless_normalized`、`test_noise_is_periodic` |
| 水位掩码 | `test_water_zero_has_no_water`、`test_water_mask_matches_threshold`、`test_water_ratio_monotonic` |
| 各向同性 | `test_isotropic_horizontal_vertical_variation`、`test_isotropic_square_periods_equal` |

## 模块说明

- `value_noise_1d(x, seed=None)`：一维确定性值噪声，保留自骨架；
  实际地形使用内部的二维 `_value_noise_2d`（带周期包裹）。
- `fbm(x, y, octaves, lacunarity, gain, seed=, wrap_x=, wrap_y=, base_frequency=)`：
  振幅归一的二维分形叠加，输出 [0, 1]。
- `generate(width, height, octaves, seed)`：返回原始高度图（二维 list）。
- `normalize(heights, lo=0.0, hi=255.0)`：返回 `(整数高度图, 最小值, 最大值)`。
- `save_png(heights, path)`：纯标准库写 8 位 RGBA PNG，确定性输出。
- `water_mask(heights, water)` / `save_mask_png(mask, path)` / `edge_gaps(heights)`：
  水位掩码与接缝度量。
