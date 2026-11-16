"""可复现、可平铺的分形地形生成器（纯标准库）。"""

from .core import (edge_gaps, fbm, generate, normalize, save_mask_png,
                   save_png, value_noise_1d, water_mask)

__all__ = [
    "value_noise_1d",
    "fbm",
    "generate",
    "normalize",
    "save_png",
    "save_mask_png",
    "water_mask",
    "edge_gaps",
]
