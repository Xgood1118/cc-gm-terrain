# -*- coding: utf-8 -*-
"""生成地形参数清单：三种地貌，各自层数与水位不同。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

SPECS = [
    {"name": "island", "width": 256, "height": 256, "octaves": 5, "seed": 1001, "water": 0.35},
    {"name": "mountain", "width": 256, "height": 256, "octaves": 7, "seed": 2002, "water": 0.05},
    {"name": "dunes", "width": 320, "height": 192, "octaves": 3, "seed": 3003, "water": 0.0},
]

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "specs.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(SPECS, f, ensure_ascii=False, indent=2)
    print("已生成", path)
