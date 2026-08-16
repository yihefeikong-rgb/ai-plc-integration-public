"""desktop-mcp 危险键黑名单与输入上限的离线安全测试。

只测纯校验逻辑（黑名单/上限/路径白名单），不触发任何真实鼠标键盘动作：
pyautogui 调用点全部被 mock 或走 ToolRejectedError/ValueError 提前返回路径。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


def _load_desktop_server():
    spec = importlib.util.spec_from_file_location(
        "desktop_mcp_safety_server", PROJECT_ROOT / "mcp-servers" / "desktop-mcp" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["desktop_mcp_safety_server"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def desktop():
    return _load_desktop_server()


# ── win 键序列绕过封堵 ──────────────────────────────────────────


class TestWinKeyBlacklisted:
    """win 单键（及别名）必须被拦，阻断 win→type_text("cmd")→enter 序列。"""

    @pytest.mark.parametrize("key", ["win", "winleft", "winright", "lwin", "rwin", "cmd", "super"])
    def test_press_key_win_aliases_rejected(self, desktop, key):
        assert desktop._is_blacklisted_press_key(key) is True

    def test_hotkey_win_single_key_rejected(self, desktop):
        assert desktop._is_blacklisted_hotkey(["win"]) is True

    def test_press_key_win_raises_tool_rejected(self, desktop):
        with pytest.raises(desktop.ToolRejectedError, match="黑名单"):
            desktop.tool_press_key({"key": "winleft", "presses": 1})

    def test_existing_blacklisted_keys_still_rejected(self, desktop):
        for key in ("delete", "del", "f2"):
            assert desktop._is_blacklisted_press_key(key) is True

    def test_normal_key_not_rejected(self, desktop):
        assert desktop._is_blacklisted_press_key("enter") is False
        assert desktop._is_blacklisted_press_key("a") is False

    def test_ctrl_shift_enter_hotkey_rejected(self, desktop):
        assert desktop._is_blacklisted_hotkey(["ctrl", "shift", "enter"]) is True


# ── 输入资源上限 ────────────────────────────────────────────────


class TestInputLimits:
    def test_click_clicks_over_limit_rejected(self, desktop):
        with pytest.raises(ValueError, match="clicks"):
            desktop.tool_click({"clicks": 101})

    def test_click_interval_over_limit_rejected(self, desktop):
        with pytest.raises(ValueError, match="interval"):
            desktop.tool_click({"x": 1, "y": 1, "interval": 5.1})

    def test_type_text_over_length_rejected(self, desktop):
        with pytest.raises(ValueError, match="10000"):
            desktop.tool_type_text({"text": "a" * 10001})

    def test_type_text_interval_over_limit_rejected(self, desktop):
        with pytest.raises(ValueError, match="interval"):
            desktop.tool_type_text({"text": "hi", "interval": 6})

    def test_press_key_presses_over_limit_rejected(self, desktop):
        with pytest.raises(ValueError, match="presses"):
            desktop.tool_press_key({"key": "a", "presses": 101})


# ── locate_on_screen 模板目录白名单 ─────────────────────────────


class TestLocateOnScreenPathWhitelist:
    def test_template_dir_exists(self, desktop):
        assert desktop.TEMPLATE_DIR.is_dir()

    def test_relative_path_inside_templates_accepted(self, desktop):
        resolved = desktop._validate_image_path("button.png")
        assert resolved == (desktop.TEMPLATE_DIR / "button.png").resolve()

    def test_dotdot_escape_rejected(self, desktop):
        with pytest.raises(ValueError, match="templates"):
            desktop._validate_image_path("../server.py")

    def test_absolute_path_outside_rejected(self, desktop):
        with pytest.raises(ValueError, match="templates"):
            desktop._validate_image_path(str(PROJECT_ROOT / "README.md"))

    def test_null_byte_rejected(self, desktop):
        with pytest.raises(ValueError, match="非法"):
            desktop._validate_image_path("a\x00.png")
