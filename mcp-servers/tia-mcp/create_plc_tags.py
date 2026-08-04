"""
TIA Portal PLC 标签创建脚本
支持从 JSON 文件批量创建 PLC 标签，幂等（已存在则跳过）。

用法:
    D:/Python3/python.exe mcp-servers/tia-mcp/create_plc_tags.py --tags mcp-servers/robot-mcp/pnp_tags.json
    D:/Python3/python.exe mcp-servers/tia-mcp/create_plc_tags.py --tags tags.json --project "D:\\path\\project.ap21"

JSON 格式:
{
    "tagTableName": "PickAndPlace_IO",
    "tags": [
        {"name": "I0_8", "dataType": "Bool", "address": "%I0.8", "comment": "急停信号"},
        ...
    ]
}
"""
import sys
import os
import json
import argparse
import ctypes
import tempfile
from pathlib import Path

# ── 确保 stdout 支持 UTF-8，输出即时可见 ──
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ═══════════════════════════════════════════════════════════════
# 自提权：TIA Portal Openness API 需要管理员权限
# 仅在作为脚本直接运行且处于 Windows 时执行；作为模块 import（例如
# 测试收集）时不得触发 UAC 弹窗或 sys.exit。
# ═══════════════════════════════════════════════════════════════
def _is_admin() -> bool:
    """是否具备管理员权限（非 Windows 平台无 UAC 概念，按有权限处理）。"""
    if sys.platform != "win32":
        return True
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def _self_elevate_if_needed() -> None:
    if sys.platform != "win32":
        return
    if _is_admin():
        return
    # 用 ShellExecuteW runas 弹出 UAC 提权
    args = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
    sys.exit(0)


if __name__ == "__main__":
    _self_elevate_if_needed()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import cfg


# ─── 核心函数（PythonNET API 方式） ───────────────────────────

def _validate_tag_defs(tags):
    """校验标签定义列表。

    返回 (valid_tags, errors)。非法项不进入 API/XML 生成流程，
    逐条记录原因（fail-closed）：保证 Create() 与 XML 插值
    只接收已校验的字符串数据。
    """
    valid = []
    errors = []
    if not isinstance(tags, list):
        return [], ["标签定义必须是数组"]

    def _has_control_chars(s: str) -> bool:
        return any(ord(c) < 32 for c in s)

    for i, tag in enumerate(tags):
        if not isinstance(tag, dict):
            errors.append(f"标签[{i}] 不是对象，已跳过")
            continue

        problems = []
        name = tag.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append("name 缺失或为空")
        elif len(name.strip()) > 128:
            problems.append("name 超过 128 字符")
        elif _has_control_chars(name):
            problems.append("name 含控制字符")

        address = tag.get("address")
        if not isinstance(address, str) or not address.strip():
            problems.append("address 缺失或为空")
        elif _has_control_chars(address):
            problems.append("address 含控制字符")

        if "dataType" not in tag or tag["dataType"] is None:
            data_type = "Bool"  # 保持原有默认行为
        elif not isinstance(tag["dataType"], str):
            problems.append("dataType 必须是字符串")
            data_type = ""
        else:
            data_type = tag["dataType"].strip()
            if not data_type:
                problems.append("dataType 为空")
            elif _has_control_chars(data_type):
                problems.append("dataType 含控制字符")

        if problems:
            errors.append(f"标签 '{name}' 无效: {'; '.join(problems)}，已跳过")
            continue

        comment = tag.get("comment", "")
        if not comment:
            comment = ""
        elif not isinstance(comment, str):
            comment = str(comment)

        valid.append({
            "name": name.strip(),
            "dataType": data_type,
            "address": address.strip(),
            "comment": comment,
        })
    return valid, errors


def create_tags_via_api(project_path: str, tags: list, tag_table_name: str = "PickAndPlace_IO") -> dict:
    """
    通过 TIA Openness API（PythonNET）创建 PLC 标签。

    Returns:
        {"status": "ok", "created": N, "skipped": N, "errors": [...]}
    """
    import clr
    from tia_session import tia_session

    result = {"status": "ok", "created": 0, "skipped": 0, "errors": []}

    # 校验标签定义：非法项不进入 Create()，逐条记录错误（fail-closed）
    tags, tag_errors = _validate_tag_defs(tags)
    result["errors"].extend(tag_errors)

    try:
        with tia_session(project_path, mode="gui") as (project, plc_sw):
            if plc_sw is None:
                return {"status": "error", "error": "未找到 PLC 设备"}

            grp = plc_sw.TagTableGroup

            # 查找或创建标签表
            table = None
            for t in grp.TagTables:
                try:
                    if str(t.Name) == tag_table_name:
                        table = t
                        break
                except Exception as e:
                    print(f"   警告: 读取标签表名称失败: {e}", file=sys.stderr)
                    sys.stderr.flush()

            if table is None:
                table = grp.TagTables.Create(tag_table_name)
                print(f"   创建标签表: {tag_table_name}")
                sys.stdout.flush()

            tags_coll = table.Tags

            # 收集已存在的标签名
            existing = set()
            for t in table.Tags:
                try:
                    existing.add(str(t.Name))
                except Exception as e:
                    print(f"   警告: 读取已有标签名失败: {e}", file=sys.stderr)
                    sys.stderr.flush()

            if existing:
                print(f"   已存在 {len(existing)} 个标签")
                sys.stdout.flush()

            # 创建标签
            for tag_def in tags:
                name = tag_def["name"]
                data_type = tag_def.get("dataType", "Bool")
                address = tag_def["address"]
                comment = tag_def.get("comment", "")

                if name in existing:
                    result["skipped"] += 1
                    continue

                try:
                    entry = tags_coll.Create(name, data_type, address)
                    if comment:
                        try:
                            entry.Comment = comment
                        except Exception as e:
                            err_msg = f"设置标签 '{name}' 注释失败: {e}"
                            result["errors"].append(err_msg)
                            print(f"   ⚠ {err_msg}", file=sys.stderr)
                            sys.stderr.flush()
                    result["created"] += 1
                    print(f"   ✅ {name:20s} {data_type:8s} {address:10s} {comment}")
                    sys.stdout.flush()
                except Exception as e:
                    err_msg = f"创建标签 '{name}' 失败: {e}"
                    result["errors"].append(err_msg)
                    print(f"   ❌ {err_msg}")
                    sys.stdout.flush()

            project.Save()
            print(f"   项目已保存")
            sys.stdout.flush()

    except Exception as e:
        # 完整堆栈仅输出到本地 stderr（供 CLI 调试），不放入返回 dict——
        # server.py 会原样透传给 MCP 客户端，泄露本地路径与内部调用链。
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

    return result


# ─── XML Import 方式（备用，更可靠） ──────────────────────────

def _generate_tag_xml(tags: list, table_name: str) -> str:
    """生成 TIA Portal 标签表 XML（含中文注释）"""
    import datetime
    from xml.sax.saxutils import escape as xml_escape

    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.0000000Z')
    lines = []
    lines.append('<?xml version="1.0" encoding="utf-8"?>')
    lines.append('<Document>')
    lines.append('  <Engineering version="V18" />')
    lines.append('  <DocumentInfo>')
    lines.append(f'    <Created>{now}</Created>')
    lines.append('    <ExportSetting>None</ExportSetting>')
    lines.append('  </DocumentInfo>')
    lines.append(f'  <SW.Tags.PlcTagTable ID="0">')
    lines.append('    <AttributeList>')
    lines.append(f'      <Name>{xml_escape(table_name)}</Name>')
    lines.append('    </AttributeList>')
    lines.append('    <ObjectList>')

    for i, tag in enumerate(tags, start=1):
        tag_id = i * 10
        lines.append(f'      <SW.Tags.PlcTag ID="{tag_id}" CompositionName="Tags">')
        lines.append('        <AttributeList>')
        lines.append(f'          <DataTypeName>{xml_escape(str(tag["dataType"]))}</DataTypeName>')
        lines.append(f'          <LogicalAddress>{xml_escape(tag["address"])}</LogicalAddress>')
        lines.append(f'          <Name>{xml_escape(tag["name"])}</Name>')
        lines.append('        </AttributeList>')
        if tag.get('comment'):
            c = xml_escape(tag['comment'])
            lines.append('        <ObjectList>')
            lines.append(f'          <MultilingualText ID="{tag_id+1}" CompositionName="Comment">')
            lines.append('            <ObjectList>')
            lines.append(f'              <MultilingualTextItem ID="{tag_id+2}" CompositionName="Items">')
            lines.append('                <AttributeList>')
            lines.append('                  <Culture>zh-CN</Culture>')
            lines.append(f'                  <Text>{c}</Text>')
            lines.append('                </AttributeList>')
            lines.append('              </MultilingualTextItem>')
            lines.append('            </ObjectList>')
            lines.append('          </MultilingualText>')
            lines.append('        </ObjectList>')
        lines.append('      </SW.Tags.PlcTag>')

    lines.append('    </ObjectList>')
    lines.append('  </SW.Tags.PlcTagTable>')
    lines.append('</Document>')
    return '\n'.join(lines)


def create_tags_via_xml(project_path: str, tags: list, tag_table_name: str = "PickAndPlace_IO") -> dict:
    """
    通过 XML Import（覆盖模式）创建 PLC 标签，更可靠。
    使用 API Create() 失败的降级方案。
    """
    import clr
    from tia_session import tia_session

    result = {"status": "ok", "created": 0, "skipped": 0, "errors": []}

    # 校验标签定义：非法项不进入 XML 生成，逐条记录错误（fail-closed）
    tags, tag_errors = _validate_tag_defs(tags)
    result["errors"].extend(tag_errors)

    # 无有效标签时不执行覆盖式导入（避免把现有标签表替换成空表）
    if not tags:
        return {"status": "error", "error": "没有有效的标签可导入，已跳过覆盖式 XML 导入", "errors": result["errors"]}

    # 生成 XML
    xml = _generate_tag_xml(tags, tag_table_name)
    xml_path = os.path.join(tempfile.gettempdir(), f"{tag_table_name}.xml")
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml)
    print(f"   生成 XML: {len(xml)} bytes → {xml_path}")
    sys.stdout.flush()

    try:
        from Siemens.Engineering import ImportOptions
        from System.IO import FileInfo

        with tia_session(project_path, mode="gui") as (project, plc_sw):
            if plc_sw is None:
                return {"status": "error", "error": "未找到 PLC 设备"}

            # 先删旧表（如果有），避免残留标签
            for t in list(plc_sw.TagTableGroup.TagTables):
                try:
                    if str(t.Name) == tag_table_name:
                        plc_sw.TagTableGroup.TagTables.Delete(t)
                        print(f"   已删除旧表: {tag_table_name}")
                        sys.stdout.flush()
                        break
                except Exception as e:
                    print(f"   警告: 删除旧表失败: {e}", file=sys.stderr)
                    sys.stderr.flush()

            # Import XML（覆盖模式）
            imported = plc_sw.TagTableGroup.TagTables.Import(
                FileInfo(xml_path),
                getattr(ImportOptions, 'Override')
            )
            count = len(list(imported))
            print(f"   ✅ 导入成功: {count} 个标签")
            sys.stdout.flush()

            # 验证
            for t in plc_sw.TagTableGroup.TagTables:
                try:
                    if str(t.Name) == tag_table_name:
                        tag_count = len(list(t.Tags))
                        result["created"] = tag_count
                        print(f"   表中标签数: {tag_count}")
                        sys.stdout.flush()
                        break
                except Exception as e:
                    print(f"   警告: 校验标签表失败: {e}", file=sys.stderr)
                    sys.stderr.flush()

            project.Save()
            result["status"] = "ok"

    except Exception as e:
        # 完整堆栈仅输出到本地 stderr（供 CLI 调试），不放入返回 dict——
        # server.py 会原样透传给 MCP 客户端，泄露本地路径与内部调用链。
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

    return result


# ─── 统一入口 ────────────────────────────────────────────────

def create_tags(project_path: str, tags: list, tag_table_name: str = "PickAndPlace_IO") -> dict:
    """
    创建 PLC 标签——先尝试 API Create()，失败后自动降级到 XML Import。
    """
    result = create_tags_via_api(project_path, tags, tag_table_name)

    # API 方式成功（可能部分失败）→ 返回
    if result["status"] == "ok":
        # 检查是否有严重的错误（半数以上失败）
        total_attempted = result["created"] + result["skipped"] + len(result["errors"])
        if total_attempted > 0 and len(result["errors"]) / total_attempted < 0.5:
            return result
        # 半数以上失败 → 需要 XML Import 降级
        if result["created"] == 0 and len(result["errors"]) > 0:
            # fail-closed：XML 覆盖导入会先删除同名表再导入本次标签，
            # 表中已有的其他标签会被静默清空（数据丢失）。自动降级有覆盖风险，
            # 改为中止并要求人工确认，绝不静默覆盖已有标签表。
            print("\n   ⚠ API 创建标签全部失败，XML 覆盖导入会清空同名表中已有标签，已中止自动降级", file=sys.stderr)
            sys.stderr.flush()
            return {
                "status": "error",
                "error": "API 创建标签全部失败；XML 覆盖导入会清空同名表中已有标签（数据丢失风险），"
                         "已中止自动降级。请修复 API 失败原因，或人工确认后显式调用 create_tags_via_xml。",
                "errors": result["errors"],
            }

    return result


def create_tags_from_json(json_path: str, project_path: str = None) -> dict:
    """从 JSON 文件读取标签定义并创建"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tags = data.get("tags", [])
    tag_table_name = data.get("tagTableName", "PickAndPlace_IO")

    if not project_path:
        project_path = cfg.tia.project_path

    if not project_path:
        return {"status": "error", "error": "未指定项目路径"}

    print(f"\n{'=' * 55}")
    print(f"  TIA Portal PLC 标签创建工具")
    print(f"{'=' * 55}")
    print(f"  Python:     {sys.executable}")
    print(f"  管理员:     {'✅ 是' if _is_admin() else '❌ 否'}")
    print(f"  标签文件:   {json_path}")
    print(f"  项目路径:   {project_path}")
    print(f"  标签表:     {tag_table_name}")
    print(f"  标签数量:   {len(tags)}")
    print()
    sys.stdout.flush()

    return create_tags(project_path, tags, tag_table_name)


# ─── 命令行入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TIA Portal PLC 标签创建工具")
    parser.add_argument("--tags", required=True, help="标签 JSON 文件路径")
    parser.add_argument("--project", default=None, help="TIA 项目路径（可选，默认使用 config.yaml）")
    args = parser.parse_args()

    tags_path = args.tags
    if not os.path.exists(tags_path):
        alt_path = Path(__file__).parent.parent / "robot-mcp" / os.path.basename(tags_path)
        if alt_path.exists():
            tags_path = str(alt_path)
        else:
            print(f"❌ 标签文件不存在: {args.tags}")
            sys.stdout.flush()
            return 1

    result = create_tags_from_json(tags_path, args.project)

    print()
    if result["status"] == "ok":
        print(f"✅ 完成: 创建 {result['created']} 个, 跳过 {result['skipped']} 个")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"   ⚠ {e}")
    else:
        print(f"❌ 失败: {result.get('error', '未知错误')}")
    sys.stdout.flush()

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
