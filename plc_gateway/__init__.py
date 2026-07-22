"""PLC Gateway 的稳定 Python 包入口。

实现仍位于 ``mcp-servers/plc-gateway``，此包只提供不受目录连字符影响的
导入名称，供仓库根目录的测试和 ``python -m plc_gateway.server`` 使用。
"""
from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "mcp-servers" / "plc-gateway"
__path__ = [str(_SOURCE_DIR)]
