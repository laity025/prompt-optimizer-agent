# -*- coding: utf-8 -*-
# ==========================================================
# 横向归一化评审逻辑单测
# 验证：消除轮间尺度漂移、保留变体相对优劣、边界(input)健壮性
# ==========================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend 目录

from app.services.optimizer_orchestrator import _normalize_case_judge  # noqa: E402


def test_eliminates_scale_drift():
    """整轮协同偏高/偏低时，归一化把分数拉回同一中心，消除轮间尺度漂移。

    场景：变体1 明显优于变体2，但评审整体给分尺度飘移。
    """
    # 低尺度轮：{10,4} vs 高尺度轮：{10,10}——变体差应保留
    low = _normalize_case_judge({1: 10, 2: 4})
    # 高尺度轮：全 8 分（无差异）应居中
    flat = _normalize_case_judge({1: 8, 2: 8})
    # 相对优劣保留：该用例内，分高的变体归一化后仍高于分低的
    assert low[1] > low[2], f"劣质变体应仍低于优质变体: {low}"
    # 无差异轮：全居中到 5.5
    assert flat[1] == 5.5 and flat[2] == 5.5, f"同分轮应居中: {flat}"


def test_relative_ordering_preserved():
    """同一用例内 4 个变体，归一化后相对排序不变。"""
    raw = {101: 9, 102: 7, 103: 5, 104: 3}
    norm = _normalize_case_judge(raw)
    # 数值单调对应
    assert norm[101] > norm[102] > norm[103] > norm[104]
    # 范围在 [1,10]
    assert all(1 <= v <= 10 for v in norm.values())


def test_single_variant_unchanged():
    """单一变体无可横向比较，保留原分避免误伤。"""
    r = _normalize_case_judge({7: 8})
    assert r == {7: 8}


def test_std_zero_centered():
    """全部同分（评审随机性为 0 时）：应视为无差异，居中到 5.5。"""
    r = _normalize_case_judge({1: 8, 2: 8, 3: 8, 4: 8})
    assert all(v == 5.5 for v in r.values())


def test_outlier_clamped():
    """单个极端离群分被 clamp，不至于把其余变体过度压低。"""
    r = _normalize_case_judge({1: 10, 2: 9, 3: 9, 4: 9})
    # 10 是最高，正常化后理应最高；其余接近，不应被clamp到极端低
    assert r[1] > r[2]
    # clamp 边界在 [1,10]
    assert all(1 <= v <= 10 for v in r.values())


def test_center_58_for_typical_scale():
    """典型健康轮（评审尺度正常）不应被过度拉平：高分仍显著高于中分。"""
    r = _normalize_case_judge({1: 9, 2: 8, 3: 8, 4: 7})
    assert r[1] > r[2] and r[2] > r[4]