"""
create_plc_tags.py 单元测试

覆盖 TS002 需求中 create_plc_tags.py 的核心函数。
测试 _generate_tag_xml 和 create_tags 函数（mock TIA Openness API）。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock, ANY

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "tia-mcp"))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Windows 特有模块（这些是跨平台兼容所需，不影响其他测试）
sys.modules["clr"] = MagicMock()
sys.modules["Siemens"] = MagicMock()
sys.modules["Siemens.Engineering"] = MagicMock()
sys.modules["System"] = MagicMock()
sys.modules["System.IO"] = MagicMock()

# 不 mock config_loader 和 tia_session，使用真实模块
# create_plc_tags.py 导入 config_loader 是安全的（只读 cfg）

from create_plc_tags import _generate_tag_xml, create_tags


# ═══════════════════════════════════════════════════════════════
# 测试数据
# ═══════════════════════════════════════════════════════════════

SAMPLE_TAGS = [
    {"name": "I0_0", "dataType": "Bool", "address": "%I0.0", "comment": "急停信号"},
    {"name": "I0_1", "dataType": "Bool", "address": "%I0.1", "comment": "启动按钮"},
    {"name": "Q0_0", "dataType": "Bool", "address": "%Q0.0", "comment": "电机运行"},
]

SAMPLE_TAGS_NO_COMMENT = [
    {"name": "I0_0", "dataType": "Bool", "address": "%I0.0"},
    {"name": "Q0_0", "dataType": "Bool", "address": "%Q0.0"},
]

SAMPLE_TAGS_MIXED_TYPES = [
    {"name": "rSpeed", "dataType": "Real", "address": "%MD100", "comment": "速度"},
    {"name": "iCounter", "dataType": "Int", "address": "%MW200", "comment": "计数器"},
    {"name": "bEnable", "dataType": "Bool", "address": "%M0.0", "comment": "使能"},
]


# ═══════════════════════════════════════════════════════════════
# 测试: _generate_tag_xml
# ═══════════════════════════════════════════════════════════════

class TestGenerateTagXml:
    """测试 _generate_tag_xml 函数"""

    def test_generates_valid_xml_structure(self):
        """生成包含正确 XML 结构的输出"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert xml.startswith('<?xml version="1.0"')
        assert "<Document>" in xml
        assert "</Document>" in xml

    def test_includes_table_name(self):
        """包含标签表名称"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "PickAndPlace_IO")
        assert "<Name>PickAndPlace_IO</Name>" in xml

    def test_includes_all_tags(self):
        """包含所有标签"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert "I0_0" in xml
        assert "I0_1" in xml
        assert "Q0_0" in xml

    def test_includes_data_types(self):
        """包含正确的数据类型"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert "<DataTypeName>Bool</DataTypeName>" in xml

    def test_includes_addresses(self):
        """包含逻辑地址"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert "<LogicalAddress>%I0.0</LogicalAddress>" in xml
        assert "<LogicalAddress>%I0.1</LogicalAddress>" in xml
        assert "<LogicalAddress>%Q0.0</LogicalAddress>" in xml

    def test_includes_comments_when_present(self):
        """包含中文注释"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert "急停信号" in xml
        assert "启动按钮" in xml
        assert "电机运行" in xml
        assert "zh-CN" in xml

    def test_no_comments_for_tags_without_comment(self):
        """无 comment 的标签不生成注释 XML"""
        xml = _generate_tag_xml(SAMPLE_TAGS_NO_COMMENT, "TestTable")
        assert "MultilingualText" not in xml

    def test_handles_mixed_data_types(self):
        """处理混合数据类型"""
        xml = _generate_tag_xml(SAMPLE_TAGS_MIXED_TYPES, "MixedTable")
        assert "<DataTypeName>Real</DataTypeName>" in xml
        assert "<DataTypeName>Int</DataTypeName>" in xml
        assert "<DataTypeName>Bool</DataTypeName>" in xml
        assert "<LogicalAddress>%MD100</LogicalAddress>" in xml
        assert "<LogicalAddress>%MW200</LogicalAddress>" in xml

    def test_handles_empty_tag_list(self):
        """处理空标签列表"""
        xml = _generate_tag_xml([], "EmptyTable")
        assert "<Name>EmptyTable</Name>" in xml
        # 空列表时不应包含 PlcTag ID 元素（父元素 PlcTagTable 除外）
        tag_count = xml.count('CompositionName="Tags"')
        assert tag_count == 0, f"预期 0 个 PlcTag 元素，实际 {tag_count}"

    def test_escapes_xml_special_chars(self):
        """转义 XML 特殊字符"""
        tags = [
            {"name": "Test<>&Tag", "dataType": "Bool", "address": "%I0.0", "comment": None},
        ]
        xml = _generate_tag_xml(tags, "SpecialTable")
        assert "Test&lt;&gt;&amp;Tag" in xml

    def test_returns_string(self):
        """返回字符串类型"""
        xml = _generate_tag_xml(SAMPLE_TAGS, "TestTable")
        assert isinstance(xml, str)
        assert len(xml) > 0


# ═══════════════════════════════════════════════════════════════
# 测试: create_tags (mock API)
# ═══════════════════════════════════════════════════════════════

class TestCreateTags:
    """测试 create_tags 函数（mock 内部 API 调用）"""

    def test_creates_tags_via_api_success(self):
        """API 方式成功创建标签"""
        with patch("create_plc_tags.create_tags_via_api") as mock_api:
            mock_api.return_value = {
                "status": "ok", "created": 3, "skipped": 0, "errors": []
            }
            result = create_tags("C:\\test\\project.ap21", SAMPLE_TAGS, "TestTable")

        assert result["status"] == "ok"
        assert result["created"] == 3
        mock_api.assert_called_once()

    def test_fallback_to_xml_on_api_failure(self):
        """API 完全失败时降级到 XML Import"""
        with patch("create_plc_tags.create_tags_via_api") as mock_api, \
             patch("create_plc_tags.create_tags_via_xml") as mock_xml:
            mock_api.return_value = {
                "status": "ok", "created": 0, "skipped": 0, "errors": ["All tags failed"]
            }
            mock_xml.return_value = {
                "status": "ok", "created": 3, "skipped": 0, "errors": []
            }
            result = create_tags("C:\\test\\project.ap21", SAMPLE_TAGS, "TestTable")

        assert result["status"] == "ok"
        assert result["created"] == 3
        mock_xml.assert_called_once()

    def test_returns_api_error(self):
        """API 返回 error 状态时原样返回"""
        with patch("create_plc_tags.create_tags_via_api") as mock_api:
            mock_api.return_value = {
                "status": "error", "error": "Connection failed"
            }
            result = create_tags("C:\\test\\project.ap21", SAMPLE_TAGS, "TestTable")

        assert result["status"] == "error"
        assert "Connection failed" in result["error"]


# ═══════════════════════════════════════════════════════════════
# 测试: create_tags_from_json
# ═══════════════════════════════════════════════════════════════

class TestCreateTagsFromJson:
    """测试 create_tags_from_json 函数"""

    def test_reads_json_and_creates_tags(self):
        """从 JSON 文件读取并创建标签"""
        # 需要 mock ctypes 管理员检查，避免实际 UAC 提权
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=True):
            from create_plc_tags import create_tags_from_json

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({
            "tagTableName": "TestIO",
            "tags": SAMPLE_TAGS,
        }, tmp)
        tmp.close()

        try:
            with patch("create_plc_tags.create_tags") as mock_create:
                mock_create.return_value = {
                    "status": "ok", "created": 3, "skipped": 0, "errors": []
                }
                result = create_tags_from_json(tmp.name, "C:\\test\\project.ap21")
        finally:
            os.unlink(tmp.name)

        assert result["status"] == "ok"
        assert result["created"] == 3

    def test_uses_default_tag_table_name(self):
        """使用默认标签表名"""
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=True):
            from create_plc_tags import create_tags_from_json

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"tags": SAMPLE_TAGS}, tmp)  # 无 tagTableName
        tmp.close()

        try:
            with patch("create_plc_tags.create_tags") as mock_create:
                mock_create.return_value = {
                    "status": "ok", "created": 3, "skipped": 0, "errors": []
                }
                result = create_tags_from_json(tmp.name, "C:\\test\\project.ap21")
                call_args = mock_create.call_args
                assert call_args is not None
                assert call_args[0][2] == "PickAndPlace_IO"  # 默认表名
        finally:
            os.unlink(tmp.name)

        assert result["status"] == "ok"

    def test_no_project_path_uses_default(self):
        """无 project_path 时使用配置默认值"""
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=True):
            from create_plc_tags import create_tags_from_json

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"tags": SAMPLE_TAGS}, tmp)
        tmp.close()

        try:
            with patch("create_plc_tags.create_tags") as mock_create:
                mock_create.return_value = {
                    "status": "ok", "created": 3, "skipped": 0, "errors": []
                }
                result = create_tags_from_json(tmp.name)  # 无 project_path
        finally:
            os.unlink(tmp.name)

        assert result["status"] == "ok"