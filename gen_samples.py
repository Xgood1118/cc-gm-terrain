# -*- coding: utf-8 -*-
"""按 data/specs.json 依次生成三种地貌的高度图 PNG 与水体掩码。

只读取 specs.json，不修改它。每张地形输出：
  output/<name>.png        归一化灰度高度图
  output/<name>_water.png  水体掩码（仅当 water > 0）
并在 stdout 打印高度范围、水域占比、左右/上下边缘拼接最大高差，
同时把同一份报告写到 output/report.txt。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from terrain.core import (edge_gaps, generate, normalize, save_mask_png,
                          save_png, water_mask)

SPEC_PATH = os.path.join(HERE, "data", "specs.json")
OUT_DIR = os.path.join(HERE, "output")


def run():
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        specs = json.load(f)

    os.makedirs(OUT_DIR, exist_ok=True)
    lines = []
    for spec in specs:
        name = spec["name"]
        heights = generate(spec["width"], spec["height"],
                           spec["octaves"], spec["seed"])
        norm, mn, mx = normalize(heights)

        png_path = os.path.join(OUT_DIR, name + ".png")
        save_png(norm, png_path)

        mask, ratio = water_mask(heights, spec["water"])
        if spec["water"] > 0:
            save_mask_png(mask, os.path.join(OUT_DIR, name + "_water.png"))

        gap_h, gap_v = edge_gaps(heights)
        line = (
            "%-9s seed=%-5d octaves=%d  高度范围 %.6f..%.6f  "
            "水域占比 %.4f (水位 %.2f)  边缘最大高差 左右=%.6f 上下=%.6f"
            % (name, spec["seed"], spec["octaves"], mn, mx,
               ratio, spec["water"], gap_h, gap_v)
        )
        lines.append(line)
        print(line)

    report_path = os.path.join(OUT_DIR, "report.txt")
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("报告已写入", report_path)


if __name__ == "__main__":
    run()
