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
    if delta:
        # 配置了 delta：只有变化 >= delta 才算显著变化，否则视为未变化
        try:
            return abs(value - prev) >= delta
        except TypeError:
            # 非数值读值无法做差值比较，退化按“值是否不同”判定（宁可触发也不漏检）
            return bool(value != prev)
    return bool(value != prev)


def is_out_of_bounds(tag: str, value: Any, tag_config: list[dict]) -> bool:
    """值超出阈值范围？"""
    if value is None:
        return False
    cfg = next((t for t in tag_config if t["tag"] == tag), {})
    limits = cfg.get("threshold", {})
    if not limits:
        return False
    try:
        min_limit = limits.get("min")
        if min_limit is not None and value < min_limit:
            return True
        max_limit = limits.get("max")
        if max_limit is not None and value > max_limit:
            return True
    except TypeError:
        # 配置了阈值但读值非数值/阈值类型异常：无法确认在界内，fail-closed 视为超限上报
        return True
    return False
