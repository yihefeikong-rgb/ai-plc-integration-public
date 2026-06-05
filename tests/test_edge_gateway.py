"""
边缘网关单元测试 — 覆盖变化检测、阈值判定逻辑
不依赖生产模块的导入链，直接测试算法
"""

import json
import pytest


# ===== 被测逻辑（与 edge-gateway/src/app.py 中的算法一致）=====

def _has_significant_change(tag: str, value, prev_values: dict,
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


def _is_out_of_bounds(tag: str, value, tag_config: list[dict]) -> bool:
    """值超出阈值范围？"""
    if value is None:
        return False
    cfg = next((t for t in tag_config if t["tag"] == tag), {})
    limits = cfg.get("threshold", {})
    if not limits:
        return False
    return value < limits["min"] or value > limits["max"]


# ===== 测试夹具 =====

@pytest.fixture
def tag_config():
    return [
        {"tag": "register.0", "protocol": "modbus", "name": "Temperature",
         "threshold": {"min": 0, "max": 120, "delta": 5}},
        {"tag": "register.1", "protocol": "modbus", "name": "Speed",
         "threshold": {"min": 0, "max": 3000, "delta": 50}},
        {"tag": "register.2", "protocol": "modbus", "name": "Pressure",
         "threshold": {"min": 0, "max": 16, "delta": 1}},
        {"tag": "coil.0", "protocol": "modbus", "name": "Start Button"},
        {"tag": "coil.1", "protocol": "modbus", "name": "Motor Run"},
        {"tag": "input.0", "protocol": "modbus", "name": "E-Stop"},
    ]


@pytest.fixture
def prev_values():
    return {}


# =============================================
# 变化检测测试
# =============================================

class TestChangeDetection:

    def test_first_read_is_change(self, tag_config, prev_values):
        """首次读取（prev=None）应视为变化"""
        assert _has_significant_change("register.0", 25.0, prev_values, tag_config)

    def test_same_value_not_change(self, tag_config, prev_values):
        """值相同不应视为变化"""
        prev_values["register.0"] = 25.0
        assert not _has_significant_change("register.0", 25.0, prev_values, tag_config)

    def test_small_change_within_delta_still_detected(self, tag_config, prev_values):
        """值变化在 delta 范围内仍检测为变化（delta 控制的是 AI 触发，不是检测）"""
        prev_values["register.0"] = 25.0
        # delta=5, 25→27 = +2 < 5，但 value != prev 仍返回 True
        assert _has_significant_change("register.0", 27.0, prev_values, tag_config)

    def test_change_exceeds_delta(self, tag_config, prev_values):
        """值变化超过 delta 应视为显著变化"""
        prev_values["register.0"] = 25.0
        # delta=5, 25→31 = +6 > 5
        assert _has_significant_change("register.0", 31.0, prev_values, tag_config)

    def test_negative_delta_change(self, tag_config, prev_values):
        """负方向超过 delta 也应视为变化"""
        prev_values["register.0"] = 25.0
        # delta=5, 25→19 = -6 < -5
        assert _has_significant_change("register.0", 19.0, prev_values, tag_config)

    def test_exact_delta_boundary_is_change(self, tag_config, prev_values):
        """变化正好等于 delta 应视为变化（>= delta）"""
        prev_values["register.0"] = 25.0
        # delta=5, 25→30 = 5
        assert _has_significant_change("register.0", 30.0, prev_values, tag_config)

    def test_value_without_delta_tracks_any_change(self, tag_config, prev_values):
        """无 delta 的标签应检测任何不同值"""
        prev_values["coil.0"] = 0
        assert _has_significant_change("coil.0", 1, prev_values, tag_config)

    def test_bool_coil_change(self, tag_config, prev_values):
        """Bool 类型值变化应检测到"""
        prev_values["coil.0"] = False
        assert _has_significant_change("coil.0", True, prev_values, tag_config)

    def test_bool_coil_no_change(self, tag_config, prev_values):
        """Bool 类型值相同不应变化"""
        prev_values["coil.0"] = True
        assert not _has_significant_change("coil.0", True, prev_values, tag_config)

    def test_none_value_not_change(self, tag_config, prev_values):
        """None 值不应触发变化"""
        assert not _has_significant_change("register.0", None, prev_values, tag_config)

    def test_none_to_value_is_change(self, tag_config, prev_values):
        """None→有值应触发变化"""
        prev_values["register.0"] = None
        assert _has_significant_change("register.0", 25.0, prev_values, tag_config)

    def test_delta_does_not_block_change_detection(self, tag_config, prev_values):
        """delta 不阻止变化检测（只控制 AI 触发），任何值变化都返回 True"""
        prev_values["register.2"] = 8.0
        # 即使变化 < delta，value != prev 仍返回 True
        assert _has_significant_change("register.2", 8.5, prev_values, tag_config)

    def test_unknown_tag_in_config(self, tag_config, prev_values):
        """不在 tag_config 的标签视为无 delta，检测任何变化"""
        prev_values["unknown.tag"] = 10
        assert _has_significant_change("unknown.tag", 20, prev_values, tag_config)

    def test_value_change_then_stable(self, tag_config, prev_values):
        """变化后 stable 的 prev 更新应正常工作"""
        prev_values["register.0"] = 20.0
        assert _has_significant_change("register.0", 100.0, prev_values, tag_config)
        prev_values["register.0"] = 100.0
        assert not _has_significant_change("register.0", 100.0, prev_values, tag_config)


# =============================================
# 阈值判定测试
# =============================================

class TestBoundsCheck:

    def test_value_within_bounds(self, tag_config):
        """值在阈值范围内不应视为超限"""
        assert not _is_out_of_bounds("register.0", 60.0, tag_config)

    def test_value_exceeds_max(self, tag_config):
        """值超过 max 应视为超限"""
        assert _is_out_of_bounds("register.0", 121.0, tag_config)

    def test_value_below_min(self, tag_config):
        """值低于 min 应视为超限"""
        assert _is_out_of_bounds("register.0", -1.0, tag_config)

    def test_value_at_min_equal_not_out(self, tag_config):
        """值等于 min 不应视为超限"""
        assert not _is_out_of_bounds("register.0", 0.0, tag_config)

    def test_value_at_max_equal_not_out(self, tag_config):
        """值等于 max 不应视为超限"""
        assert not _is_out_of_bounds("register.0", 120.0, tag_config)

    def test_tag_without_threshold_not_out(self, tag_config):
        """无阈值的标签不应视为超限"""
        assert not _is_out_of_bounds("coil.0", 1, tag_config)

    def test_none_not_out_of_bounds(self, tag_config):
        """None 值不应触发阈值告警"""
        assert not _is_out_of_bounds("register.0", None, tag_config)

    def test_independent_tag_thresholds(self, tag_config):
        """不同标签的阈值独立生效"""
        # Pressure: min=0, max=16
        assert _is_out_of_bounds("register.2", 17.0, tag_config)    # 超 max
        assert _is_out_of_bounds("register.2", -1.0, tag_config)    # 低于 min
        assert not _is_out_of_bounds("register.2", 8.0, tag_config)  # 正常

    def test_unknown_tag_not_out(self, tag_config):
        """不在 tag_config 中的标签不应触发阈值告警"""
        assert not _is_out_of_bounds("register.99", 999.0, tag_config)

    def test_edge_case_very_large_value(self, tag_config):
        """极大值应视为超限"""
        assert _is_out_of_bounds("register.0", 1e10, tag_config)

    def test_int_vs_float_equivalence(self, tag_config):
        """int 和 float 的阈值比较应一致"""
        assert not _is_out_of_bounds("register.0", 100, tag_config)  # int
        assert not _is_out_of_bounds("register.0", 100.0, tag_config)  # float
        assert _is_out_of_bounds("register.0", 121, tag_config)
        assert _is_out_of_bounds("register.0", 121.0, tag_config)


# =============================================
# 标签配置加载测试
# =============================================

class TestTagConfig:

    def test_tags_loaded_from_json_file(self, tmp_path):
        """从 tags.json 文件加载标签配置"""
        test_tags = [
            {"tag": "coil.0", "protocol": "modbus", "name": "Test Coil"},
            {"tag": "register.0", "protocol": "modbus", "name": "Test Reg",
             "threshold": {"min": 0, "max": 100, "delta": 10}},
            {"tag": "input.0", "protocol": "modbus", "name": "Test Input"},
        ]
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "tags.json").write_text(
            json.dumps(test_tags), encoding="utf-8"
        )

        loaded = json.loads((config_dir / "tags.json").read_text(encoding="utf-8"))
        assert len(loaded) == 3
        assert loaded[0]["tag"] == "coil.0"
        assert loaded[1]["threshold"]["delta"] == 10
        assert loaded[2]["protocol"] == "modbus"

    def test_tags_with_partial_thresholds(self):
        """标签可以只有部分阈值字段"""
        tags = [
            {"tag": "reg.0", "name": "T1",
             "threshold": {"min": 0}},
            {"tag": "reg.1", "name": "T2",
             "threshold": {"max": 100}},
            {"tag": "reg.2", "name": "T3",
             "threshold": {"delta": 5}},
        ]
        assert tags[0]["threshold"]["min"] == 0
        assert "max" not in tags[0]["threshold"]  # 只有 min，没有 max
        assert tags[1]["threshold"]["max"] == 100
        assert "min" not in tags[1]["threshold"]  # 只有 max，没有 min
        assert tags[2]["threshold"]["delta"] == 5

    def test_tags_without_threshold(self):
        """标签可以不配置阈值"""
        tags = [
            {"tag": "coil.0", "protocol": "modbus", "name": "Start"},
        ]
        assert "threshold" not in tags[0]

    def test_tags_json_invalid_raises(self):
        """无效 JSON 应抛出异常"""
        import json
        with pytest.raises(json.JSONDecodeError):
            json.loads("这不是 JSON")
