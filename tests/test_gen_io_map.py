"""
gen_io_map.py 单元测试

覆盖 TS002 需求中 gen_io_map.py 的 generate_io_map 函数。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "tia-mcp"))

from gen_io_map import generate_io_map


# ═══════════════════════════════════════════════════════════════
# 测试数据
# ═══════════════════════════════════════════════════════════════

MINIMAL_SPEC = {
    "blockName": "MotorControl",
    "blockNumber": 100,
    "description": "电机控制功能块",
    "interface": {
        "inputs": [
            {"name": "iStart", "type": "Bool", "address": "%I0.0", "comment": "启动信号"},
            {"name": "iStop", "type": "Bool", "address": "%I0.1", "comment": "停止信号"},
            {"name": "iOverload", "type": "Bool", "address": "%I0.2", "comment": "过载保护"},
        ],
        "outputs": [
            {"name": "oRunFwd", "type": "Bool", "address": "%Q0.0", "comment": "正转运行"},
            {"name": "oRunRev", "type": "Bool", "address": "%Q0.1", "comment": "反转运行"},
        ],
    },
    "networks": [],
}

NO_ADDRESS_SPEC = {
    "blockName": "LogicOnly",
    "blockNumber": 200,
    "interface": {
        "inputs": [
            {"name": "iEnable", "type": "Bool", "comment": "使能"},
        ],
        "outputs": [
            {"name": "oStatus", "type": "Bool", "comment": "状态"},
        ],
    },
    "networks": [],
}

NO_INTERFACE_SPEC = {
    "blockName": "Empty",
    "blockNumber": 300,
    "networks": [],
}


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _write_spec(spec: dict) -> str:
    """将 spec 写入临时 JSON 文件，返回路径"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(spec, tmp)
    tmp.close()
    return tmp.name


# ═══════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════

class TestGenerateIoMap:
    """测试 generate_io_map 核心函数"""

    def test_generates_fb_block(self):
        """生成正确的 FUNCTION_BLOCK 声明"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert 'FUNCTION_BLOCK "IO_Map_MotorControl"' in result
        assert "TITLE = IO Mapping - MotorControl" in result
        assert "END_FUNCTION_BLOCK" in result

    def test_includes_instance_declaration(self):
        """包含原 FB 的实例声明"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert 'MotorControl : "MotorControl";' in result

    def test_includes_input_mapping(self):
        """包含输入映射（标签符号名赋值）"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        # 输入映射将标签符号值赋给实例变量
        assert 'MotorControl.iStart := "MotorControl_iStart"' in result
        assert "启动信号" in result
        assert 'MotorControl.iStop := "MotorControl_iStop"' in result
        assert "停止信号" in result

    def test_includes_output_mapping(self):
        """包含输出映射（实例变量赋给标签符号）"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert '"MotorControl_oRunFwd" := MotorControl.oRunFwd' in result
        assert "正转运行" in result
        assert '"MotorControl_oRunRev" := MotorControl.oRunRev' in result
        assert "反转运行" in result

    def test_includes_fb_call(self):
        """包含原 FB 的调用"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert "MotorControl();" in result

    def test_optimized_access_enabled(self):
        """S7_Optimized_Access 设置为 TRUE"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert "S7_Optimized_Access := 'TRUE'" in result

    def test_no_address_skips_io_mapping(self):
        """无 address 字段时跳过 IO 映射"""
        path = _write_spec(NO_ADDRESS_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert "无物理地址" in result
        assert "LogicOnly();" in result  # 仍然调用 FB

    def test_no_interface_handles_gracefully(self):
        """无 interface 字段时生成最小代码"""
        path = _write_spec(NO_INTERFACE_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert 'FUNCTION_BLOCK "IO_Map_Empty"' in result
        assert "END_FUNCTION_BLOCK" in result

    def test_comment_omitted_when_empty(self):
        """comment 为空时省略注释"""
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["interface"]["inputs"][0]["comment"] = ""
        path = _write_spec(spec)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        # 启动信号注释不应出现
        assert "启动信号" not in result

    def test_returns_string(self):
        """返回值为字符串"""
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = generate_io_map(path)
        finally:
            os.unlink(path)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_missing_file_raises_error(self):
        """文件不存在时抛出异常"""
        with pytest.raises(FileNotFoundError):
            generate_io_map("nonexistent_file.json")


# ═══════════════════════════════════════════════════════════════
# 测试: 命令行入口
# ═══════════════════════════════════════════════════════════════

class TestGenIoMapCli:
    """测试命令行入口（通过 subprocess 调用）"""

    def test_cli_prints_to_stdout(self):
        """无 --output 时打印到 stdout"""
        import subprocess
        path = _write_spec(MINIMAL_SPEC)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "gen_io_map", path],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path(__file__).parent.parent / "mcp-servers" / "tia-mcp"),
            )
            assert "FUNCTION_BLOCK" in result.stdout
        finally:
            os.unlink(path)

    def test_cli_output_to_file(self):
        """--output 指定输出文件"""
        import subprocess
        path = _write_spec(MINIMAL_SPEC)
        out = tempfile.NamedTemporaryFile(suffix=".scl", delete=False)
        out.close()
        try:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(
                [sys.executable, "-m", "gen_io_map", path, "--output", out.name],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path(__file__).parent.parent / "mcp-servers" / "tia-mcp"),
                env=env,
            )
            assert result.returncode == 0
            with open(out.name, encoding="utf-8-sig") as f:
                content = f.read()
            assert "FUNCTION_BLOCK" in content
        finally:
            os.unlink(path)
            try:
                os.unlink(out.name)
            except OSError:
                pass

    def test_cli_no_args_prints_help(self):
        """无参数时打印帮助信息"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "gen_io_map"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent.parent / "mcp-servers" / "tia-mcp"),
        )
        assert result.returncode == 1
        assert "用法" in result.stdout or "generate_io_map" in result.stdout