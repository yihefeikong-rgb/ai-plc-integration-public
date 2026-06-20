"""
变化检测和阈值判定 — 从 app.py 提取的纯函数，便于独立测试。
"""
from typing import Any


def has_significant_change(tag: str, value: Any, prev_values: dict,
                           tag_config: list[dict]) -> bool:
    """值有显著变化？超过 delta 或从 None 变有值"""
    if value is None:
        return False
    prev = prev_values.get(tag)
    if prev is None:
        return True
    cfg = next((t for t in tag_config if t["tag"] == tag), {})
    delta = cfg.get("threshold", {}).get("delta", 0)
    if delta and abs(value - prev) >= delta:
        return True
    return bool(value != prev)


def is_out_of_bounds(tag: str, value: Any, tag_config: list[dict]) -> bool:
    """值超出阈值范围？"""
    if value is None:
        return False
    cfg = next((t for t in tag_config if t["tag"] == tag), {})
    limits = cfg.get("threshold", {})
    if not limits:
        return False
    return value < limits["min"] or value > limits["max"]
