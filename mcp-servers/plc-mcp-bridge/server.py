#!/usr/bin/env python3
"""
PLC MCP Bridge — 让 AI 直接调用 TIA Portal / PLCSIM Advanced / Factory I/O

架构:
  AI(Claude Code) <-> stdio MCP <-> 本服务器 <-> subprocess <-> 现有工具链
                                      |-- plcsim_api.py (PLCSIM 管理)
                                      |-- TiaWorker.exe (编译/下载)
                                      |-- download_to_plcsim.py (下载)
                                      +-- p3_flow.py (端到端)

模块结构:
  _helpers.py        — 共享: MCP 实例、辅助函数、路径、配置
  tools_plcsim.py    — PLCSIM Advanced 管理 (7 工具)
  tools_blocks.py    — 块管理 (11 工具)
  tools_tags.py      — 标签表管理 (7 工具)
  tools_types.py     — UDT + Watch 表 (6 工具)
  tools_project.py   — 项目管理 + 硬件 + 交叉引用 + 诊断 (13 工具)
  tools_pipeline.py  — 下载 + Factory I/O + 流水线 (6 工具)

用法:
  # stdio 模式（给 Claude Code 用）
  python server.py

  # 调试模式（直接调用）
  python server.py --debug list-instances
"""
import sys

# 导入 MCP 实例
from _helpers import mcp

# 导入所有工具模块（触发 @mcp.tool 注册）
import tools_plcsim      # noqa: F401
import tools_blocks      # noqa: F401
import tools_tags        # noqa: F401
import tools_types       # noqa: F401
import tools_project     # noqa: F401
import tools_pipeline    # noqa: F401
import tools_s7          # noqa: F401


if __name__ == "__main__":
    if "--debug" in sys.argv:
        import asyncio
        cmd = sys.argv[sys.argv.index("--debug") + 1]
        tool_map = {
            "list-instances": tools_plcsim.list_instances,
            "get-state": tools_plcsim.get_instance_state,
            "restore": tools_plcsim.restore_from_golden,
            "archive": tools_plcsim.archive_to_golden,
            "compile": tools_project.compile_project,
            "download": tools_pipeline.download_project,
            "config": tools_pipeline.get_config,
        }
        fn = tool_map.get(cmd)
        if fn:
            result = asyncio.run(fn())
            print(result)
        else:
            print(f"未知调试命令: {cmd}")
            print(f"可用: {list(tool_map.keys())}")
    else:
        mcp.run(transport="stdio")
