"""
TIA MCP Server — 阶段3：西门子工程态
提供 AI 生成 SCL 代码 + 导入/编译/下载到 PLCSIM 的完整工具链

架构: Claude/Cursor -> TiaMcpHost(FastMCP) -> TiaWorker(C#) -> TIA Openness DLL
工作流: AI生成SCL -> 写入.scl文件 -> TiaWorker导入 -> 生成块 -> 编译 -> 下载
"""

import json
import re
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from fastmcp import FastMCP

# SVG 渲染器（可选，渲染失败不影响主流程）
try:
    from ladder_renderer import render_svg_preview
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

mcp = FastMCP("tia-portal")

TIA_WORKER = Path(__file__).parent / "bin" / "TiaWorker.exe"
LAD_CREATOR = Path(__file__).parent / "lad_creator.py"
SCL_TEMPLATES = Path(__file__).parent.parent.parent / "plc-code-templates" / "siemens-scl"

DEFAULT_PROJECT = ""
DEEPSEEK_API_KEY = ""


def _load_env():
    global DEFAULT_PROJECT, DEEPSEEK_API_KEY
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TIA_PROJECT_PATH="):
                DEFAULT_PROJECT = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DEEPSEEK_API_KEY="):
                DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()


def _run_worker(command: str, payload: dict) -> dict:
    """调用 TiaWorker.exe"""
    if not TIA_WORKER.exists():
        return {"status": "error", "error": f"TiaWorker.exe not found at {TIA_WORKER}"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [str(TIA_WORKER), command, tmp_path],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout.strip()
        if output:
            return json.loads(output)
        return {"status": "error", "error": result.stderr or "No output"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "TiaWorker timeout (120s)"}
    except json.JSONDecodeError:
        return {"status": "error", "error": f"Invalid JSON: {output[:500]}"}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _resolve_path(project_path: str) -> str:
    p = project_path or DEFAULT_PROJECT
    if not p:
        raise ValueError("未指定项目路径，请在 .env 中设置 TIA_PROJECT_PATH")
    return p


def _gen_scl_via_deepseek(description: str, template: str) -> dict:
    """调用 DeepSeek 生成 SCL 代码"""
    template_text = ""
    template_file = SCL_TEMPLATES / f"{template}.md"
    if template_file.exists():
        template_text = template_file.read_text(encoding="utf-8")

    prompt = f"""你是西门子 SCL (Structured Control Language) 编程专家。

请根据以下描述生成符合 IEC 61131-3 标准的 SCL 代码。

## 要求
- 使用西门子 S7-1200/1500 SCL 语法
- 必须包含: 急停互锁、故障处理、输出限幅
- 变量命名: 匈牙利命名法 (bEmergencyStop, rMotorSpeed, iState 等)
- 每个 FB 包含状态机 (INIT/RUN/FAULT/STOP)
- 代码必须有中文注释
- FUNCTION_BLOCK 名称使用英文，如 "MotorControl"

{template_text}

## 功能描述
{description}

## 输出格式
返回 JSON，含 scl_code 和 block_name 字段:
```json
{{"scl_code": "...", "block_name": "..."}}
```
只返回 JSON，不要其他内容。"""

    import requests

    if not DEEPSEEK_API_KEY:
        return {"status": "error", "error": "未找到 DEEPSEEK_API_KEY"}

    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    result = json.loads(content.strip())
    return {"status": "ok", "data": result}


# ─── MCP 工具 ───────────────────────────────────────────


@mcp.tool()
def list_devices(project_path: str = "") -> dict:
    """列出 TIA Portal 项目中的 PLC 设备。

    Args:
        project_path: TIA 项目路径 (.ap19 文件)，留空使用默认值
    """
    try:
        path = _resolve_path(project_path)
        return _run_worker("list-devices", {"ProjectPath": path})
    except ValueError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def import_scl_file(
    scl_code: str,
    block_name: str,
    project_path: str = "",
) -> dict:
    """将 SCL 源代码导入 TIA Portal 项目并生成程序块。

    工作流: 写入 .scl 文件 -> TIA 外部源导入 -> 生成 FB/FC/DB

    Args:
        scl_code: SCL 源代码 (FUNCTION_BLOCK ... END_FUNCTION_BLOCK)
        block_name: 程序块名称 (如 "MotorControl"，与 SCL 代码中的名称一致)
        project_path: TIA 项目路径，留空使用默认值
    """
    try:
        path = _resolve_path(project_path)
    except ValueError as e:
        return {"status": "error", "error": str(e)}

    # 写入临时 .scl 文件
    scl_dir = Path(tempfile.gettempdir()) / "tia-scl"
    scl_dir.mkdir(exist_ok=True)
    scl_file = scl_dir / f"{block_name}.scl"
    scl_file.write_text(scl_code, encoding="utf-8")

    return _run_worker("import-scl", {
        "ProjectPath": path,
        "SclFilePath": str(scl_file),
    })


@mcp.tool()
def compile_project(project_path: str = "") -> dict:
    """编译 TIA Portal 项目。

    Args:
        project_path: TIA 项目路径，留空使用默认值
    """
    try:
        path = _resolve_path(project_path)
        return _run_worker("compile", {"ProjectPath": path})
    except ValueError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def download_to_plcsim(project_path: str = "", device_name: str = "") -> dict:
    """将项目下载到 PLCSIM 仿真 PLC。

    注意: 需要先在 TIA Portal 中配置 PLCSIM 连接。

    Args:
        project_path: TIA 项目路径
        device_name: 目标设备名称，留空使用第一个设备
    """
    try:
        path = _resolve_path(project_path)
        return _run_worker("download", {
            "ProjectPath": path,
            "DeviceName": device_name,
        })
    except ValueError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def generate_scl_code(
    description: str,
    template: str = "general",
) -> dict:
    """使用 AI 根据自然语言描述生成 SCL 代码。

    Args:
        description: 功能描述，如 "三相异步电机正反转控制，含急停和过载保护"
        template: 模板 — motor(电机), conveyor(传送带), pid(PID), general(通用)

    Returns:
        {"status": "ok", "data": {"scl_code": "...", "block_name": "..."}}
    """
    try:
        return _gen_scl_via_deepseek(description, template)
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def generate_and_import(
    description: str,
    block_name: str = "",
    template: str = "general",
    project_path: str = "",
) -> dict:
    """一站式：AI 生成 SCL 代码 + 导入到 TIA Portal 项目。

    Args:
        description: 功能描述
        block_name: 块名称，留空由 AI 自动命名
        template: 代码模板 (motor/conveyor/pid/general)
        project_path: TIA 项目路径
    """
    result = generate_scl_code(description, template)
    if result.get("status") != "ok":
        return result

    data = result["data"]
    name = block_name or data.get("block_name", "AutoGen")
    scl = data.get("scl_code", "")

    if not scl:
        return {"status": "error", "error": "AI 未生成有效 SCL 代码"}

    return import_scl_file(scl, name, project_path)


# ─── 梯形图 LAD 工具 ─────────────────────────────


@mcp.tool()
def create_ladder_block(
    description: str = "cart3cycle",
    block_name: str = "AutoCart3Cycle",
    project_path: str = "",
) -> dict:
    """在 TIA Portal 中创建梯形图 (LAD) 功能块。

    description 说明:
      - "cart3cycle" → 材料小车往复3次（硬编码模板）
      - 其他描述 → 调 DeepSeek 生成 LadderSpec JSON → CartGen → TIA Portal

    Args:
        description: 功能描述，如 "电机正反转，带急停和过载"
        block_name: 块名称
        project_path: TIA 项目路径
    """
    # 快速命令：直接走硬编码模板
    if description == "cart3cycle":
        result = subprocess.run(
            [sys.executable, str(LAD_CREATOR), "cart3cycle"],
            capture_output=True, text=True, timeout=180,
        )
        lines = [l for l in result.stdout.split("\n") if l.strip()]
        return {"status": "ok" if result.returncode == 0 else "error",
                "output": lines, "returncode": result.returncode}

    # ── AI 生成 LadderSpec JSON ──
    try:
        # 1. 调 DeepSeek 生成 JSON
        prompt = _LAD_PROMPT_TEMPLATE.format(description=description)
        ai_result = _call_deepseek(prompt)

        # 2. 解析 JSON（两次尝试：代码块 → 全文）
        content = ai_result["choices"][0]["message"]["content"]
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            raw = json_match.group(1).strip()
        else:
            raw = content.strip()
        spec = json.loads(raw)

        # 2b. 轻量校验
        if not isinstance(spec, dict):
            return {"status": "error", "error": "DeepSeek 返回的不是 JSON 对象"}
        if "networks" not in spec or not isinstance(spec["networks"], list):
            return {"status": "error", "error": "JSON 缺少 networks 数组"}
        spec.setdefault("blockName", block_name or "AutoGen")
        spec.setdefault("blockNumber", 100)
        if block_name:
            spec["blockName"] = block_name

        # 3. 保存到临时 JSON 文件
        tmp_json = os.path.join(tempfile.gettempdir(), f"lad_{spec['blockName']}.json")
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)

        # 4. 调 CartGen 生成 XML
        TIA_XML_DIR = r"D:\TIA FANG ZHEN"
        os.makedirs(TIA_XML_DIR, exist_ok=True)
        xml_path = os.path.join(TIA_XML_DIR, f"{spec['blockName']}.xml")
        dll_path = os.path.join(os.path.dirname(__file__), "CartGen", "bin", "Release", "net8.0", "CartGen.dll")
        r = subprocess.run(["dotnet", "exec", dll_path, tmp_json, xml_path], capture_output=True, timeout=60)
        if r.returncode != 0:
            err_text = r.stderr.decode('utf-8', 'ignore') or r.stdout.decode('utf-8', 'ignore')
            return {"status": "error", "error": f"CartGen 失败: {err_text[:500]}"}

        # 5. 清洗 XML（去空 MultilingualTextItem）
        with open(xml_path, "r", encoding="utf-8") as f:
            xml = f.read()
        xml = re.sub(
            r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
            "", xml)
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml)

        # 6. 导入 TIA Portal
        _import_xml_into_tia(xml_path, project_path)

        # 7. SVG 预览
        svg_preview = ""
        if _HAS_SVG:
            try:
                svg_preview = render_svg_preview(spec)
            except Exception:
                pass

        return {"status": "ok", "blockName": spec.get("blockName"),
                "networks": len(spec.get("networks", [])),
                "xmlPath": xml_path,
                "svg_preview": svg_preview}

    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"DeepSeek 返回的不是合法 JSON: {e}. 原始内容前200字: {content[:200] if 'content' in dir() else 'N/A'}"}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def _call_deepseek(prompt: str) -> dict:
    """调用 DeepSeek API"""
    import requests
    if not DEEPSEEK_API_KEY:
        raise ValueError("未配置 DEEPSEEK_API_KEY")
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.3, "max_tokens": 4000},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _import_xml_into_tia(xml_path: str, project_path: str = ""):
    """将 SimaticML XML 导入 TIA Portal"""
    p = project_path or DEFAULT_PROJECT
    if not p:
        raise ValueError("未指定项目路径，请在 .env 中设置 TIA_PROJECT_PATH")

    import clr, System, subprocess, os
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
    clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
    from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from System.IO import FileInfo
    tia = TiaPortal(TiaPortalMode.WithoutUserInterface)
    try:
        project = tia.Projects.Open(FileInfo(p))
        device = project.Devices[0]
        asm = System.Reflection.Assembly.LoadFrom(
            r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
        sc = asm.GetType('Siemens.Engineering.HW.Features.SoftwareContainer')

        for item in device.DeviceItems:
            for m in item.GetType().GetMethods():
                if m.Name == 'GetService' and m.IsGenericMethodDefinition:
                    c = m.MakeGenericMethod(sc).Invoke(item, None)
                    if c:
                        sw = c.GetType().GetProperty('Software').GetValue(c, None)
                        if sw and 'PlcSoftware' in sw.GetType().FullName:
                            sw.BlockGroup.Blocks.Import(
                                FileInfo(xml_path), ImportOptions.Override, SWImportOptions(2))
                            # 编译
                            comp = asm.GetType('Siemens.Engineering.Compiler.ICompilable')
                            for gm in sw.GetType().GetMethods():
                                if gm.Name == 'GetService' and gm.IsGenericMethodDefinition:
                                    compiler = gm.MakeGenericMethod(comp).Invoke(sw, None)
                                    if compiler:
                                        compiler.Compile()
                                        project.Save()
                                        return
    finally:
        tia.Dispose()


# DeepSeek Prompt 模板
_LAD_PROMPT_TEMPLATE = """你是一个西门子 PLC 梯形图 (LAD) 专家。请根据以下描述生成 LadderSpec JSON。

## 输出格式
```json
{{
  "blockName": "英文驼峰命名",
  "blockNumber": 100,
  "interface": {{
    "inputs": [{{"name": "iXxx", "type": "Bool", "comment": "中文注释"}}],
    "outputs": [{{"name": "oXxx", "type": "Bool", "comment": "中文注释"}}],
    "local": [{{"name": "mXxx", "type": "Bool", "comment": "中文注释"}}]
  }},
  "networks": [
    {{
      "title": "网络标题",
      "comment": "逻辑说明",
      "elements": [
        {{"type": "normally_open|normally_closed|coil|coil_set|coil_reset", "operand": "变量名"}}
      ]
    }},
    {{
      "title": "Set/Reset 模式（代替自保持）",
      "comment": "注意：串联逻辑即可，不要用 parallelElements",
      "elements": [
        {{"type": "normally_open", "operand": "oRunFwd"}},
        {{"type": "normally_closed", "operand": "iStop"}},
        {{"type": "coil_set", "operand": "oRunFwd"}}
      ]
    }}
  ]
}}
```

## 安全规则（必须遵守）
- 【不要用自保持并联电路】CartGen 暂不支持并联分支
- 改用 Set/Reset 模式实现自保持：启动时 Set 线圈，停止时 Reset 线圈
- 所有电机类输出必须有急停互锁（串联 normally_closed iStop）
- 正转/反转必须互锁（正转网络包含 normally_closed oRunRev）
- 过载保护必须串联 normally_closed iOverload

## 变量命名规范
- 输入: iXxx（iStart, iStop, iOverload 等）
- 输出: oXxx（oRunFwd, oRunRev, oFault 等）
- 本地: mXxx（mSafetyOK, mState1 等）

## 用户描述
{description}"""

if __name__ == "__main__":
    _load_env()
    print(f"[TiaMCP] TIA Worker: {TIA_WORKER}")
    print(f"[TiaMCP] 默认项目: {DEFAULT_PROJECT or '(未设置)'}")
    print(f"[TiaMCP] DeepSeek: {'OK' if DEEPSEEK_API_KEY else '(未配置)'}")
    mcp.run()
