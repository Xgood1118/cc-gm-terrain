# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain.core import fbm, generate, normalize  # noqa: E402


def test_fbm_range():
    v = fbm(1.5, 2.5, 4)
    assert 0 <= v <= 2.0


def test_generate_shape():
    heights = generate(8, 6, 3)
    assert len(heights) == 6
    assert len(heights[0]) == 8


def test_normalize_range():
    heights = [[0.1, 0.5], [0.9, 0.3]]
    norm, mn, mx = normalize(heights)
    assert min(min(r) for r in norm) == 0
    assert max(max(r) for r in norm) == 255
    assert abs(mn - 0.1) < 1e-9
    assert abs(mx - 0.9) < 1e-9
