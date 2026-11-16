# 分形地形生成

骨架能出高度图 PNG，但结果不可复现，层与层之间的振幅关系也不对。

## 已知缺口

- `value_noise_1d` 忽略 `seed`，每次调用都取新的随机数，同一 seed 跑两次得到两张完全不同的图。
- 一维噪声用 `x + y*0.37` 压成一维，水平与垂直方向频率不一致，图上有明显的斜条纹。
- `fbm` 幅值累加不归一，`octaves` 越大整体越亮，水位阈值失去意义。
- 没有做接缝处理，图不能平铺。
- `normalize` 每次按当前图的最小最大值拉伸，两张图的相对高度不可比。
- 水位线只是参数，没有参与生成，也没有输出水体掩码。

## 运行

```
python gen_samples.py
python -m terrain.cli --width 256 --height 256 --octaves 5 --seed 1001 --out island.png
python -m pytest tests -q
```

`specs.json` 给了三种地貌：海岛、山地、沙丘，层数从 3 到 7，海岛和山地带水位。
