#!/usr/bin/env python3
"""
PLC MCP Bridge — 让 AI 直接调用 TIA Portal / PLCSIM Advanced / Factory I/O

架构:
  AI(Claude Code) ←→ stdio MCP ←→ 本服务器 ←→ subprocess ←→ 现有工具链
                                      ├── plcsim_api.py (PLCSIM 管理)
                                      ├── TiaWorker.exe (编译/下载)
                                      ├── download_to_plcsim.py (下载)
                                      └── p3_flow.py (端到端)

设计原则:
  - 不直接导入 clr / uiautomation，避免 COM STA/MTA 冲突
  - 所有操作通过子进程调用现有脚本
  - 输出统一为 JSON

用法:
  # stdio 模式（给 Claude Code 用）
  python server.py

  # 调试模式（直接调用）
  python server.py --debug list-instances
"""
import sys
import os
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP

# ── 路径 ──
PROJECT_ROOT = Path(__file__).parent.parent.parent
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

PLCSIM_API = TIA_MCP_DIR / "plcsim_api.py"
TIAWORKER_EXE = TIA_MCP_DIR / "bin" / "TiaWorker.exe"
DOWNLOAD_SCRIPT = TIA_MCP_DIR / "download_to_plcsim.py"
P3_SCRIPT = PROJECT_ROOT / "p3_flow.py"
FIO_EXE = "Factory IO.exe"

sys.path.insert(0, str(TIA_MCP_DIR))
try:
    from config_loader import cfg
    PROJECT_PATH = cfg.tia.project_path
    PLC_IP = cfg.simulation.advanced.plc_ip
    PLCSIM_INSTANCE = cfg.factory_io.plcsim_instance
    GOLDEN_ZIP = os.path.join(os.path.dirname(PROJECT_PATH), 'factory_io1_golden.zip')
    STORAGE_PATH = os.path.join(os.path.dirname(PROJECT_PATH), 'plcsim_storage')
except Exception:
    cfg = None
    PROJECT_PATH = ""
    PLC_IP = "192.168.0.1"
    PLCSIM_INSTANCE = "factoryio"
    GOLDEN_ZIP = ""
    STORAGE_PATH = ""

mcp = FastMCP("plc_mcp")


# ═══════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════

def _run_python(script: Path, args: list[str], timeout: int = 60) -> dict:
    """运行 Python 脚本子进程，返回解析后的 JSON"""
    cmd = [sys.executable, str(script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        out = r.stdout.strip()
        err = r.stderr.strip()
        # 尝试解析 stdout 为 JSON
        if out:
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                pass
        # 非 JSON 输出，包装返回
        return {
            "success": r.returncode == 0,
            "output": out,
            "stderr": err,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_tiaworker(command: str, data: dict, timeout: int = 180) -> dict:
    """运行 TiaWorker.exe 子进程"""
    if not TIAWORKER_EXE.exists():
        return {"success": False, "error": f"TiaWorker 未编译: {TIAWORKER_EXE}"}

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, tmp)
    tmp_path = tmp.name
    tmp.close()

    try:
        r = subprocess.run(
            [str(TIAWORKER_EXE), command, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        out = r.stdout.strip()
        if out:
            try:
                result = json.loads(out)
                if result.get('status') == 'ok':
                    return {"success": True, "data": result.get('data', {}), "raw": out}
                else:
                    return {"success": False, "error": result.get('error', '未知错误'), "raw": out}
            except json.JSONDecodeError:
                return {"success": r.returncode == 0, "output": out, "raw": out}
        return {"success": False, "error": "TiaWorker 无输出"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"TiaWorker 超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _format_result(success: bool, data=None, error: str = "") -> str:
    """统一格式化返回消息"""
    if success:
        if data:
            return f"✅ 成功\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
        return "✅ 成功"
    return f"❌ 失败: {error}"


# ═══════════════════════════════════════
#  PLCSIM Advanced 管理工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_list_instances",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
)
async def list_instances() -> str:
    """列出所有已注册的 PLCSIM Advanced 仿真实例"""
    result = _run_python(PLCSIM_API, ["list"])
    if result.get("success") or result.get("output"):
        out = result.get("output", "")
        return f"当前 PLCSIM 实例:\n{out}" if out else "无运行实例"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_create_instance",
    annotations={"destructiveHint": False},
)
async def create_instance(
    name: str = "factoryio",
    ip: str = "192.168.0.1",
    cpu_type: str = "1511",
) -> str:
    """创建并启动一个新的 PLCSIM Advanced 空壳实例"""
    result = _run_python(PLCSIM_API, ["create", name, ip, cpu_type], timeout=120)
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_stop_instance",
    annotations={"destructiveHint": True},
)
async def stop_instance(name: str = "factoryio") -> str:
    """停止并删除指定 PLCSIM Advanced 实例"""
    result = _run_python(PLCSIM_API, ["stop", name], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_get_state",
    annotations={"readOnlyHint": True},
)
async def get_instance_state(name: str = "factoryio") -> str:
    """获取 PLCSIM 实例的运行状态（RUN/STOP/Off 等）"""
    instances = _run_python(PLCSIM_API, ["list"]).get("output", "")
    for line in instances.split("\n"):
        if name in line:
            return f"实例 `{name}` 状态:\n{line.strip()}"
    return f"实例 `{name}` 未找到或未运行"


@mcp.tool(
    name="plc_restore_from_golden",
    annotations={"destructiveHint": True},
)
async def restore_from_golden(
    name: str = "",
    golden_zip: str = "",
    storage_path: str = "",
    ip: str = "",
    auto_run: bool = True,
) -> str:
    """从 golden backup 恢复 PLCSIM 实例（绕过 TIA Portal 下载）

    Args:
        name: 实例名（默认 config.yaml 中的值）
        golden_zip: golden zip 文件路径
        storage_path: 存储目录路径
        ip: PLC 的 IP 地址
        auto_run: 恢复后自动切换到 RUN 模式
    """
    n = name or PLCSIM_INSTANCE
    gz = golden_zip or GOLDEN_ZIP
    sp = storage_path or STORAGE_PATH
    p = ip or PLC_IP

    if not gz or not sp:
        return "❌ 配置缺失: 请提供 golden_zip 和 storage_path 参数"

    if not os.path.exists(gz):
        return f"❌ Golden backup 文件不存在: {gz}"

    result = _run_python(PLCSIM_API, ["restore", n, gz, sp, p], timeout=120)
    return _format_result(result.get("success"), error=result.get("error", "恢复失败"))


@mcp.tool(
    name="plc_archive_to_golden",
    annotations={"destructiveHint": False},
)
async def archive_to_golden(
    name: str = "",
    golden_zip: str = "",
) -> str:
    """将当前 PLCSIM 实例状态保存为 golden backup

    下载到 PLCSIM 成功后调用此工具，更新 golden backup。
    下次 restore_from_golden 就能恢复到最新状态。
    """
    n = name or PLCSIM_INSTANCE
    gz = golden_zip or GOLDEN_ZIP
    if not gz:
        return "❌ 请提供 golden_zip 参数"

    result = _run_python(PLCSIM_API, ["archive", n, gz], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", "归档失败"))


@mcp.tool(
    name="plc_switch_to_tcpip",
    annotations={"destructiveHint": True},
)
async def switch_to_tcpip(name: str = "", ip: str = "") -> str:
    """将 PLCSIM 实例切换到 TCP/IP 通信模式（Factory I/O 需要）"""
    n = name or PLCSIM_INSTANCE
    p = ip or PLC_IP
    result = _run_python(PLCSIM_API, ["tcpip", n, p], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", "切换失败"))


# ═══════════════════════════════════════
#  TIA Portal 编译工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_compile_project",
    annotations={"destructiveHint": False},
)
async def compile_project() -> str:
    """编译 TIA Portal 项目（通过 TiaWorker.exe）

    前置条件:
      1. TIA Portal V21 已安装
      2. 项目路径已配置在 config.yaml 中
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("compile", {"ProjectPath": project})
    if result.get("success"):
        data = result.get("data", {})
        return _format_result(True, data={
            "project": os.path.basename(project),
            "errors": data.get("errors", 0),
            "warnings": data.get("warnings", 0),
        })
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(
    name="plc_list_devices",
    annotations={"readOnlyHint": True},
)
async def list_devices() -> str:
    """列出 TIA Portal 项目中的 PLC 设备"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-devices", {"ProjectPath": project})
    if result.get("success"):
        data = result.get("data", {})
        devices = data.get("devices", [])
        if devices:
            lines = [f"- {d['name']} ({d['type']})" for d in devices]
            return f"TIA 项目设备:\n" + "\n".join(lines)
        return "项目中未找到设备"
    return _format_result(False, error=result.get("error", "查询失败"))


# ═══════════════════════════════════════
#  项目管理工具（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_save_project",
    annotations={"destructiveHint": False},
)
async def save_project() -> str:
    """保存 TIA Portal 项目"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("save-project", {"ProjectPath": project})
    if result.get("success"):
        return f"✅ 项目已保存: {result.get('data', {}).get('saved', '')}"
    return _format_result(False, error=result.get("error", "保存失败"))


@mcp.tool(
    name="plc_get_project_info",
    annotations={"readOnlyHint": True},
)
async def get_project_info() -> str:
    """获取当前 TIA 项目的名称、路径和设备数量"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("get-project-info", {"ProjectPath": project})
    if result.get("success"):
        d = result.get("data", {})
        return f"项目: {d.get('name', '?')}\n路径: {d.get('path', '?')}\n设备数: {d.get('deviceCount', '?')}"
    return _format_result(False, error=result.get("error", "查询失败"))


# ═══════════════════════════════════════
#  块管理工具（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_list_blocks",
    annotations={"readOnlyHint": True},
)
async def list_blocks() -> str:
    """列出 TIA 项目中所有 PLC 块（FB/FC/OB/DB）及其编号和语言"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-blocks", {"ProjectPath": project}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        blocks = data.get("blocks", [])
        if blocks:
            lines = [f"  {b['type']:10s} {b['number']:>5d}  {b['name']:<30s} {b['language']}" for b in blocks]
            return f"PLC 块 ({data.get('count', len(blocks))}):\n" + "\n".join(lines)
        return "项目中无 PLC 块"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_list_dbs",
    annotations={"readOnlyHint": True},
)
async def list_dbs() -> str:
    """列出 TIA 项目中所有数据块（GlobalDB/InstanceDB）"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-dbs", {"ProjectPath": project}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        dbs = data.get("dbs", [])
        if dbs:
            lines = [f"  DB{d['number']:<5d} {d['name']:<30s} ({d['type']})" for d in dbs]
            return f"数据块 ({data.get('count', len(dbs))}):\n" + "\n".join(lines)
        return "项目中无数据块"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_create_block",
    annotations={"destructiveHint": False},
)
async def create_block(
    block_name: str,
    block_type: str = "FB",
    language: str = "SCL",
    block_number: int = 0,
) -> str:
    """在 TIA 项目中创建 PLC 块

    Args:
        block_name: 块名称
        block_type: 块类型 (FB/FC/OB/DB)
        language: 编程语言 (SCL/LAD/FBD/STL)
        block_number: 块编号（0=自动分配）
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("create-block", {
        "ProjectPath": project,
        "BlockName": block_name,
        "BlockType": block_type,
        "Language": language,
        "BlockNumber": block_number,
    })
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已创建 {block_type} `{data.get('blockName', block_name)}` (编号: {data.get('number', '?')})"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(
    name="plc_export_block",
    annotations={"readOnlyHint": True},
)
async def export_block(
    block_name: str,
    output_path: str,
) -> str:
    """从 TIA 项目导出块为 XML 文件

    Args:
        block_name: 要导出的块名称
        output_path: 输出 XML 文件路径
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("export-block", {
        "ProjectPath": project,
        "BlockName": block_name,
        "OutputPath": output_path,
    })
    if result.get("success"):
        return f"✅ 已导出 `{block_name}` → {output_path}"
    return _format_result(False, error=result.get("error", "导出失败"))


@mcp.tool(
    name="plc_import_block",
    annotations={"destructiveHint": True},
)
async def import_block(
    file_path: str,
    override: bool = False,
) -> str:
    """从 XML 文件导入块到 TIA 项目

    Args:
        file_path: XML 块文件路径
        override: 是否覆盖已存在的同名块
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    if not os.path.exists(file_path):
        return f"❌ XML 文件不存在: {file_path}"

    result = _run_tiaworker("import-block", {
        "ProjectPath": project,
        "FilePath": file_path,
        "Override": override,
    })
    if result.get("success"):
        data = result.get("data", {})
        blocks = data.get("blocks", [])
        return f"✅ 已导入: {', '.join(blocks)}"
    return _format_result(False, error=result.get("error", "导入失败"))


# ═══════════════════════════════════════
#  标签表管理工具（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_get_block_details",
    annotations={"readOnlyHint": True},
)
async def get_block_details(block_name: str) -> str:
    """获取指定块的详细信息（类型、编号、语言、一致性状态）

    Args:
        block_name: 块名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("get-block-details", {"ProjectPath": project, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        consistent = "✅" if d.get("isConsistent") else "⚠"
        return f"块 `{d.get('name')}` (#{d.get('number')})\n  类型: {d.get('type')}\n  语言: {d.get('language')}\n  一致性: {consistent}"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_delete_block",
    annotations={"destructiveHint": True},
)
async def delete_block(block_name: str) -> str:
    """删除 PLC 块（FB/FC/OB/DB）

    Args:
        block_name: 要删除的块名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("delete-block", {"ProjectPath": project, "BlockName": block_name})
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 已删除 `{d.get('deleted')}` (#{d.get('number')})"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(
    name="plc_compile_block",
    annotations={"destructiveHint": False},
)
async def compile_block(block_name: str) -> str:
    """编译单个 PLC 块

    Args:
        block_name: 要编译的块名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("compile-block", {"ProjectPath": project, "BlockName": block_name}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        status = "✅ 通过" if d.get("success") else "❌ 失败"
        return f"{status} | 错误: {d.get('errors', 0)} | 警告: {d.get('warnings', 0)}"
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(
    name="plc_delete_db",
    annotations={"destructiveHint": True},
)
async def delete_db(db_name: str) -> str:
    """删除数据块（仅限 GlobalDB/InstanceDB）

    Args:
        db_name: 要删除的数据块名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("delete-db", {"ProjectPath": project, "BlockName": db_name})
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 已删除 DB `{d.get('deleted')}` (#{d.get('number')})"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(
    name="plc_list_tag_tables",
    annotations={"readOnlyHint": True},
)
async def list_tag_tables() -> str:
    """列出 TIA 项目中所有标签表及标签数量"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-tags", {"ProjectPath": project})
    if result.get("success"):
        data = result.get("data", {})
        tables = data.get("tables", [])
        if tables:
            lines = [f"- {t['name']} ({t['tagCount']} 个标签)" for t in tables]
            return "标签表:\n" + "\n".join(lines)
        return "项目中无标签表"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_get_tags",
    annotations={"readOnlyHint": True},
)
async def get_tags(tag_table_name: str) -> str:
    """获取指定标签表中的所有标签

    Args:
        tag_table_name: 标签表名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("get-tags", {
        "ProjectPath": project,
        "TagTableName": tag_table_name,
    })
    if result.get("success"):
        data = result.get("data", {})
        tags = data.get("tags", [])
        if tags:
            lines = [f"- {t['name']} : {t['dataType']} @ {t['address']}" for t in tags]
            return f"标签表 `{tag_table_name}` ({len(tags)} 个标签):\n" + "\n".join(lines)
        return f"标签表 `{tag_table_name}` 为空"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_add_tag",
    annotations={"destructiveHint": False},
)
async def add_tag(
    tag_table_name: str,
    tag_name: str,
    data_type: str,
    logical_address: str = "",
) -> str:
    """向标签表添加标签

    Args:
        tag_table_name: 标签表名称
        tag_name: 标签名称
        data_type: 数据类型 (Bool/Int/Real/Word 等)
        logical_address: 逻辑地址 (如 %M0.0, %MW100)
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("add-tag", {
        "ProjectPath": project,
        "TagTableName": tag_table_name,
        "TagName": tag_name,
        "DataType": data_type,
        "LogicalAddress": logical_address,
    })
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已添加标签 `{data.get('tagName', tag_name)}` : {data.get('dataType', data_type)} @ {data.get('address', logical_address)}"
    return _format_result(False, error=result.get("error", "添加失败"))


@mcp.tool(
    name="plc_delete_tag_table",
    annotations={"destructiveHint": True},
)
async def delete_tag_table(tag_table_name: str) -> str:
    """删除标签表

    Args:
        tag_table_name: 要删除的标签表名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("delete-tag-table", {
        "ProjectPath": project,
        "TagTableName": tag_table_name,
    })
    if result.get("success"):
        return f"✅ 已删除标签表 `{tag_table_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))


@mcp.tool(
    name="plc_get_block_interface",
    annotations={"readOnlyHint": True},
)
async def get_block_interface(block_name: str) -> str:
    """读取 PLC 块的接口定义（Input/Output/Static/Temp 各部分的变量）

    Args:
        block_name: 块名称（如 Main, MotorControl 等）
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("get-block-interface", {
        "ProjectPath": project,
        "BlockName": block_name,
    }, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        sections = data.get("sections", [])
        if sections:
            lines = [f"块 `{data.get('blockName', block_name)}` 接口:"]
            for s in sections:
                lines.append(f"\n  [{s['section']}]")
                for m in s.get("members", []):
                    lines.append(f"    {m['name']} : {m['dataType']}")
            return "\n".join(lines)
        return f"块 `{block_name}` 无接口定义"
    return _format_result(False, error=result.get("error", "读取失败"))


@mcp.tool(
    name="plc_create_db",
    annotations={"destructiveHint": False},
)
async def create_db(db_name: str, db_number: int = 0) -> str:
    """创建全局数据块 (GlobalDB)

    Args:
        db_name: 数据块名称
        db_number: 数据块编号（0=自动分配）
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("create-db", {
        "ProjectPath": project,
        "DbName": db_name,
        "DbNumber": db_number,
    })
    if result.get("success"):
        data = result.get("data", {})
        return f"✅ 已创建 DB `{data.get('dbName', db_name)}` (编号: {data.get('number', '?')})"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(
    name="plc_create_tag_table",
    annotations={"destructiveHint": False},
)
async def create_tag_table(tag_table_name: str) -> str:
    """创建新的标签表

    Args:
        tag_table_name: 标签表名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("create-tag-table", {
        "ProjectPath": project,
        "TagTableName": tag_table_name,
    })
    if result.get("success"):
        return f"✅ 已创建标签表 `{result.get('data', {}).get('tableName', tag_table_name)}`"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(
    name="plc_search_tags",
    annotations={"readOnlyHint": True},
)
async def search_tags(query: str) -> str:
    """跨所有标签表搜索标签（按名称模糊匹配）

    Args:
        query: 搜索关键词
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("search-tag", {
        "ProjectPath": project,
        "Query": query,
    })
    if result.get("success"):
        data = result.get("data", {})
        results = data.get("results", [])
        if results:
            lines = [f"  [{r['table']}] {r['name']} : {r['dataType']} @ {r['address']}" for r in results]
            return f"搜索 '{data.get('query', query)}' ({len(results)} 个结果):\n" + "\n".join(lines)
        return f"未找到匹配 '{query}' 的标签"
    return _format_result(False, error=result.get("error", "搜索失败"))


@mcp.tool(
    name="plc_delete_tag",
    annotations={"destructiveHint": True},
)
async def delete_tag(
    tag_table_name: str,
    tag_name: str,
) -> str:
    """从标签表中删除标签

    Args:
        tag_table_name: 标签表名称
        tag_name: 要删除的标签名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("delete-tag", {
        "ProjectPath": project,
        "TagTableName": tag_table_name,
        "TagName": tag_name,
    })
    if result.get("success"):
        return f"✅ 已删除标签 `{tag_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))


# ═══════════════════════════════════════
#  UDT 管理工具（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_list_udts",
    annotations={"readOnlyHint": True},
)
async def list_udts() -> str:
    """列出 TIA 项目中所有用户自定义类型（UDT）"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-udts", {"ProjectPath": project}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        udts = data.get("udts", [])
        if udts:
            lines = [f"- {u['name']}" for u in udts]
            return f"UDT 列表 ({data.get('count', len(udts))}):\n" + "\n".join(lines)
        return "项目中无 UDT"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_create_udt",
    annotations={"destructiveHint": False},
)
async def create_udt(udt_name: str) -> str:
    """创建空的用户自定义类型（UDT）

    Args:
        udt_name: UDT 名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("create-udt", {
        "ProjectPath": project,
        "UdtName": udt_name,
    })
    if result.get("success"):
        return f"✅ 已创建 UDT `{udt_name}`"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(
    name="plc_delete_udt",
    annotations={"destructiveHint": True},
)
async def delete_udt(udt_name: str) -> str:
    """删除用户自定义类型（UDT）

    Args:
        udt_name: 要删除的 UDT 名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("delete-udt", {
        "ProjectPath": project,
        "UdtName": udt_name,
    })
    if result.get("success"):
        return f"✅ 已删除 UDT `{udt_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))


# ═══════════════════════════════════════
#  Watch 表管理工具（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_list_watch_tables",
    annotations={"readOnlyHint": True},
)
async def list_watch_tables() -> str:
    """列出 TIA 项目中所有监控表（Watch Table）"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("list-watch-tables", {"ProjectPath": project}, timeout=120)
    if result.get("success"):
        data = result.get("data", {})
        tables = data.get("watchTables", [])
        if tables:
            lines = [f"- {t['name']}" for t in tables]
            return f"监控表 ({data.get('count', len(tables))}):\n" + "\n".join(lines)
        return "项目中无监控表"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(
    name="plc_create_watch_table",
    annotations={"destructiveHint": False},
)
async def create_watch_table(watch_table_name: str) -> str:
    """创建新的监控表（Watch Table）

    Args:
        watch_table_name: 监控表名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("create-watch-table", {
        "ProjectPath": project,
        "WatchTableName": watch_table_name,
    })
    if result.get("success"):
        return f"✅ 已创建监控表 `{watch_table_name}`"
    return _format_result(False, error=result.get("error", "创建失败"))


@mcp.tool(
    name="plc_delete_watch_table",
    annotations={"destructiveHint": True},
)
async def delete_watch_table(watch_table_name: str) -> str:
    """删除监控表（Watch Table）

    Args:
        watch_table_name: 要删除的监控表名称
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    result = _run_tiaworker("delete-watch-table", {
        "ProjectPath": project,
        "WatchTableName": watch_table_name,
    })
    if result.get("success"):
        return f"✅ 已删除监控表 `{watch_table_name}`"
    return _format_result(False, error=result.get("error", "删除失败"))


# ═══════════════════════════════════════
#  编译诊断 & 项目管理（TiaWorker）
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_get_compiler_errors",
    annotations={"readOnlyHint": True},
)
async def get_compiler_errors() -> str:
    """编译项目并返回详细的错误/警告信息"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("get-compiler-errors", {"ProjectPath": project}, timeout=180)
    if result.get("success"):
        d = result.get("data", {})
        status = "✅ 通过" if d.get("success") else "❌ 有错误"
        lines = [f"{status} | 错误: {d.get('errors', 0)} | 警告: {d.get('warnings', 0)}"]
        for msg in d.get("messages", []):
            icon = "❌" if msg.get("state") == "Error" else "⚠"
            lines.append(f"  {icon} [{msg.get('path', '')}] {msg.get('description', '')}")
        return "\n".join(lines)
    return _format_result(False, error=result.get("error", "编译失败"))


@mcp.tool(
    name="plc_check_consistency",
    annotations={"readOnlyHint": True},
)
async def check_consistency() -> str:
    """检查所有块的一致性状态"""
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("check-consistency", {"ProjectPath": project}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        lines = [f"一致性检查: {d.get('consistent', 0)}/{d.get('total', 0)} 通过"]
        inconsistent = [b for b in d.get("blocks", []) if not b.get("isConsistent")]
        if inconsistent:
            lines.append("不一致的块:")
            for b in inconsistent:
                lines.append(f"  ⚠ {b['name']} (#{b['number']})")
        return "\n".join(lines)
    return _format_result(False, error=result.get("error", "检查失败"))


@mcp.tool(
    name="plc_export_all_xml",
    annotations={"readOnlyHint": True},
)
async def export_all_xml(output_dir: str = "") -> str:
    """将所有 PLC 块导出为 XML 文件到指定目录

    Args:
        output_dir: 输出目录（默认使用配置的 output_dir）
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    out = output_dir
    if not out:
        out = os.path.join(os.path.dirname(project), "xml_export")

    result = _run_tiaworker("export-all-xml", {
        "ProjectPath": project,
        "OutputDir": out,
    }, timeout=300)
    if result.get("success"):
        d = result.get("data", {})
        msg = f"✅ 已导出 {d.get('exported', 0)} 个块 → {d.get('outputDir', out)}"
        if d.get("failed", 0) > 0:
            msg += f"\n⚠ {d['failed']} 个块导出失败: {', '.join(d.get('failedBlocks', []))}"
        return msg
    return _format_result(False, error=result.get("error", "导出失败"))


@mcp.tool(
    name="plc_close_project",
    annotations={"destructiveHint": True},
)
async def close_project(save: bool = True) -> str:
    """关闭当前 TIA Portal 项目

    Args:
        save: 关闭前是否保存（默认 True）
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"
    result = _run_tiaworker("close-project", {"ProjectPath": project, "Save": save})
    if result.get("success"):
        d = result.get("data", {})
        return f"✅ 项目已关闭" + (" (已保存)" if d.get("saved") else "")
    return _format_result(False, error=result.get("error", "关闭失败"))


# ═══════════════════════════════════════
#  下载工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_download_project",
    annotations={"destructiveHint": True},
)
async def download_project(
    method: str = "auto",
    compile_first: bool = True,
) -> str:
    """将 TIA Portal 项目下载到 PLCSIM（自动选择最优方式）

    Args:
        method: 下载方式 (auto/tiaworker/tiaworker-gui/python/ui/golden-restore)
        compile_first: 下载前是否先编译
    """
    project = PROJECT_PATH
    if not project or not os.path.exists(project):
        return f"❌ 项目文件不存在: {project}"

    dl_script = DOWNLOAD_SCRIPT

    # 特定下载方式
    method_map = {
        "auto": [],
        "tiaworker": ["--tiaworker"],
        "tiaworker-gui": ["--tiaworker-gui"],
        "python": ["--python"],
        "ui": ["--ui"],
        "golden-restore": ["--golden-restore"],
    }
    extra_args = method_map.get(method, [])
    if compile_first and method == "auto":
        extra_args = ["--compile-first"]

    if method == "golden-restore":
        result = _run_python(dl_script, ["--golden-restore"], timeout=120)
        return _format_result(result.get("success"), error=result.get("error", "恢复失败"))

    result = _run_python(dl_script, extra_args, timeout=300)
    return _format_result(result.get("success"), data={
        "method": method,
        "output": result.get("output", "")[:500],
    }, error=result.get("error", "下载失败"))


# ═══════════════════════════════════════
#  Factory I/O 工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_fio_write_config",
    annotations={"destructiveHint": False},
)
async def fio_write_config(
    instance_name: str = "",
    auto_connect: bool = True,
    run_mode: bool = True,
) -> str:
    """写入 Factory I/O 的 auto.cfg 配置文件

    Args:
        instance_name: PLCSIM 实例名
        auto_connect: 是否自动连接
        run_mode: 场景启动时是否直接运行
    """
    name = instance_name or PLCSIM_INSTANCE

    cfg_text = f"""# Factory I/O auto config — generated by plc_mcp_bridge
ui.show_welcome_window = False
scene.start_in_run_mode = {str(run_mode).lower()}
drivers.siemens_s7plcsim.auto_connect = {str(auto_connect).lower()}
drivers.siemens_s7plcsim.instance_name = '{name}'
drivers.siemens_s7plcsim.connection_timeout = 60
"""
    written = []
    for p in [
        r'C:\ProgramData\Real Games\Factory IO\auto.cfg',
        os.path.join(os.path.expanduser('~'), 'Documents', 'Factory IO', 'auto.cfg'),
    ]:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8-sig') as f:
                f.write(cfg_text)
            written.append(p)
        except Exception as e:
            pass

    if written:
        return f"✅ auto.cfg 已写入 ({len(written)} 个位置)"
    return "⚠ 无法写入 auto.cfg（权限不足？）"


@mcp.tool(
    name="plc_fio_launch",
    annotations={"destructiveHint": False},
)
async def fio_launch(
    fio_path: str = "",
    scene_path: str = "",
) -> str:
    """启动 Factory I/O（需要先通过 fio_write_config 配置连接）"""
    exe = fio_path or str(cfg.factory_io.exe_path) if cfg else ""
    if not exe:
        return "❌ 未配置 Factory I/O 路径"

    if not os.path.exists(exe):
        return f"❌ Factory I/O 未找到: {exe}"

    try:
        subprocess.Popen([exe, scene_path] if scene_path else [exe], shell=True)
        return "✅ Factory I/O 已启动"
    except Exception as e:
        return f"❌ 启动失败: {e}"


# ═══════════════════════════════════════
#  流水线工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_run_pipeline",
    annotations={"destructiveHint": True},
)
async def run_pipeline(
    skip_compile: bool = False,
    launch_fio: bool = True,
) -> str:
    """运行完整的 P3 端到端流水线

    流程:
      1. PLCSIM golden 恢复 → STOP 待下载
      2. 编译 TIA 项目
      3. 下载到 PLCSIM（5 级降级自动选择最佳方式）
      4. 更新 golden backup
      5. 启动 Factory I/O

    Args:
        skip_compile: 跳过编译步骤
        launch_fio: 完成后启动 Factory I/O
    """
    result = _run_python(
        P3_SCRIPT,
        ["--skip-compile"] if skip_compile else [],
        timeout=600,
    )
    out = result.get("output", "")
    if result.get("success") is False and not out:
        return _format_result(False, error=result.get("error", "流水线执行失败"))
    return f"流水线结果:\n{out[:1000]}" if out else "✅ 流水线完成"


@mcp.tool(
    name="plc_golden_restore",
    annotations={"destructiveHint": True},
)
async def golden_restore() -> str:
    """快速恢复模式：直接从 golden backup 恢复 PLCSIM，跳过编译/下载

    适用于:
      - 已知 golden backup 已包含最新程序
      - 只需重置 PLCSIM 到已知状态
      - TIA Portal 不需要打开
    """
    result = _run_python(P3_SCRIPT, ["--golden-restore"], timeout=120)
    out = result.get("output", "")
    return out if out else _format_result(result.get("success"), error=result.get("error", "恢复失败"))


# ═══════════════════════════════════════
#  信息工具
# ═══════════════════════════════════════

@mcp.tool(
    name="plc_get_config",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_config() -> str:
    """获取当前项目的配置信息"""
    if not cfg:
        return "⚠ config_loader 未加载（检查 config.yaml 是否存在）"

    return f"""当前配置:
  项目: {os.path.basename(PROJECT_PATH)}
  PLCSIM 实例: {PLCSIM_INSTANCE}
  IP 地址: {PLC_IP}
  Golden zip: {os.path.basename(GOLDEN_ZIP)}
  Storage 路径: {STORAGE_PATH}
  TiaWorker: {'可用' if TIAWORKER_EXE.exists() else '未编译'}
  项目文件: {'存在' if os.path.exists(PROJECT_PATH) else '不存在'}
  Golden 文件: {'存在' if os.path.exists(GOLDEN_ZIP) else '不存在'}
"""


# ═══════════════════════════════════════
#  CLI 调试入口
# ═══════════════════════════════════════

if __name__ == "__main__":
    if "--debug" in sys.argv:
        # 调试模式：直接调工具
        cmd = sys.argv[sys.argv.index("--debug") + 1]
        args = sys.argv[sys.argv.index("--debug") + 2:]
        tool_map = {
            "list-instances": list_instances,
            "get-state": get_instance_state,
            "restore": restore_from_golden,
            "archive": archive_to_golden,
            "compile": compile_project,
            "download": download_project,
            "config": get_config,
        }
        fn = tool_map.get(cmd)
        if fn:
            import asyncio
            result = asyncio.run(fn())
            print(result)
        else:
            print(f"未知调试命令: {cmd}")
            print(f"可用: {list(tool_map.keys())}")
    else:
        # 正常 stdio 模式启动 MCP
        mcp.run(transport="stdio")
