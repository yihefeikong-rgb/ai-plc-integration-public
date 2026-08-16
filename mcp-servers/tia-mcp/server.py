"""
TIA MCP Server — 阶段3：西门子工程态
提供 AI 生成 SCL 代码 + 导入/编译/下载到 PLCSIM 的完整工具链

架构: Claude/Cursor -> TiaMcpHost(FastMCP) -> TiaWorker(C#) -> TIA Openness DLL
工作流: AI生成SCL -> 写入.scl文件 -> TiaWorker导入 -> 生成块 -> 编译 -> 下载
"""

import json
import os
import hmac
import logging
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# 追加项目根到 sys.path（安全模块依赖）
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

from fastmcp import FastMCP
from config_loader import (
    cfg,
    safety_validate_ladder,
    validate_control_target,
    validate_ladder_spec,
)
from audit import audit_log
from mcp_common.tiaworker_client import TiaWorkerClient
from safety.validator import validator as safety_validator


# 工程态危险操作（写工程 / 下载到设备 / 在线连接变更）集合。_eng.* 标签
# 不命中运行态 write_rules，require_bits 互锁不适用；除认证外还必须消费
# 一次性人工确认令牌（fail-closed），不得静默放行。
# create_block / create_plc_tags / call_fb_in_ob1 直接改写工程内容；
# go_online / go_offline 变更与 PLC 的在线连接状态，同样必须确认。
_CONFIRMATION_REQUIRED_OPS = frozenset({
    "download_to_plcsim",
    "import_scl_file",
    "compile_project",
    "full_pipeline",
    "create_block",
    "create_plc_tags",
    "call_fb_in_ob1",
    "go_online",
    "go_offline",
})


def _consume_confirmation_token(
    operation: str,
    confirmation_token: str,
    auth_token: str,
    block_name: str,
) -> dict | None:
    """消费一次性人工确认令牌；失败返回阻断结果，成功返回 None（fail-closed）。

    令牌绑定约定（与 ai-plc-assistant/backend 签发端 issue_confirmation 对齐）:
      - operator : authenticated_actor(auth_token, "tia")，由共享认证密钥派生
      - target   : f"_eng.{operation}"
      - value    : "confirm"
      - device_id: f"tia:{plcsim_instance}:{plc_ip}"，由唯一控制目标派生
    确认服务未配置 / 令牌缺失 / 绑定不匹配一律拒绝，绝不降级为跳过。
    """
    try:
        from safety.confirmation import ConfirmationService
        from mcp_common.audit import authenticated_actor
    except Exception as exc:
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail=f"人工确认模块不可用: {exc}")
        return _make_result(ok=False, operation=operation,
                            error=f"人工确认机制不可用，拒绝工程态操作: {operation}")

    if not isinstance(confirmation_token, str) or not confirmation_token.strip():
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail="危险工程操作缺少一次性人工确认令牌")
        return _make_result(ok=False, operation=operation,
                            error=f"危险工程操作需要一次性人工确认令牌 confirmation_token: {operation}")

    operator = authenticated_actor(auth_token, "tia")
    if not operator:
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail="无法从认证令牌派生操作者身份")
        return _make_result(ok=False, operation=operation,
                            error="无法从认证令牌派生操作者身份，拒绝工程态操作")

    try:
        target = _control_target()
        device_id = f"tia:{target.plcsim_instance}:{target.plc_ip}"
    except Exception as exc:
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail=f"控制目标无效，无法派生设备身份: {exc}")
        return _make_result(ok=False, operation=operation,
                            error=f"控制目标无效，无法派生设备身份，拒绝工程态操作: {exc}")

    try:
        ConfirmationService().consume(
            confirmation_token,
            operator=operator,
            target=f"_eng.{operation}",
            value="confirm",
            device_id=device_id,
        )
    except Exception as exc:
        # 任何消费失败（含令牌失效/已使用/存储不可写）一律 fail-closed，
        # 不允许未捕获异常绕过审计链。
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail=f"人工确认失败: {exc}")
        return _make_result(ok=False, operation=operation,
                            error=f"人工确认失败（fail-closed）: {exc}")
    return None


def _safety_gate(
    operation: str,
    block_name: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict | None:
    """工程态安全闸：通过 validator 检查熔断状态和安全前置条件。

    注: 工程态操作（导入代码/下载到PLC）不同于运行态标签写入，
    shadow_sim 数值仿真不适用。安全链通过 validator 熔断机制保护。

    危险工程操作（download_to_plcsim/import_scl_file/compile_project/
    full_pipeline/create_block/create_plc_tags/call_fb_in_ob1/go_online/
    go_offline）默认必须携带一次性人工确认令牌（fail-closed）：
    未提供令牌时拒绝执行，绝不静默放行。
    仅当显式设置环境变量 TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING=1 时
    才允许未确认的工程操作（有意的 opt-in 降级，供自动化流程使用）。
    """
    result = safety_validator.validate(f"_eng.{operation}", 0)
    if not result.allowed:
        audit_log(operation, user_input=block_name, block_name=block_name,
                  success=False, detail=f"安全链拒绝: {result.reason}")
        return _make_result(ok=False, operation=operation,
                            error=f"安全链拒绝工程态操作: {result.reason}")
    is_confirmable = result.needs_confirmation is True or operation in _CONFIRMATION_REQUIRED_OPS
    if is_confirmable:
        unconfirmed = os.environ.get("TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING", "")
        if unconfirmed.strip().lower() in {"1", "true", "yes", "on"}:
            return None  # 显式 opt-in 降级：自动化流程经配置允许未确认工程操作
        return _consume_confirmation_token(operation, confirmation_token, auth_token, block_name)
    return None

# SVG 渲染器（可选，渲染失败不影响主流程）
try:
    from ladder_renderer import render_svg_preview
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

mcp = FastMCP("tia-portal")

# ── 认证 ───────────────────────────────────────────────
# TIA Openness 可修改工程和执行下载；未配置认证时不能暴露任何工具。
_AUTH_TOKEN = os.environ.get("TIA_MCP_AUTH_TOKEN", os.environ.get("MCP_AUTH_TOKEN", ""))


def _check_auth(token: str = "") -> bool:
    """验证认证令牌；缺少服务器端令牌必须失败关闭。

    hmac.compare_digest 对非 ASCII str 会抛 TypeError（未捕获将导致进程崩溃），
    统一转 UTF-8 字节再比较，保持恒定时间语义（与 desktop-mcp 一致）。
    """
    if not isinstance(token, str):
        return False
    return bool(_AUTH_TOKEN) and bool(token) and hmac.compare_digest(
        token.encode("utf-8"), _AUTH_TOKEN.encode("utf-8")
    )


def _require_auth(token: str = "") -> None:
    """如果认证未配置或未通过则拒绝调用。"""
    if not _AUTH_TOKEN:
        raise PermissionError("MCP_AUTH_TOKEN 未配置，TIA MCP 服务不可用")
    if not _check_auth(token):
        raise PermissionError("认证失败：无效的 auth token")


TIA_WORKER = Path(__file__).parent / "bin" / "TiaWorker.exe"
LAD_CREATOR = Path(__file__).parent / "lad_creator.py"
SCL_TEMPLATES = Path(__file__).parent.parent.parent / "plc-code-templates" / "siemens-scl"


def _control_target():
    """读取并验证唯一的 V21 控制目标。"""
    try:
        target = validate_control_target()
    except Exception as exc:
        raise ValueError(f"控制目标配置无效: {exc}") from exc
    if str(target.tia_version).upper() != "V21":
        raise ValueError("控制目标必须使用 V21")
    return target


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _worker_error(
    command: str,
    message: str,
    *,
    operation_id: str = "",
    outcome_unknown: bool = False,
) -> dict:
    result = {"status": "error", "ok": False, "result": None, "error": message}
    if operation_id:
        result["operation_id"] = operation_id
    if outcome_unknown:
        result["error_code"] = "OUTCOME_UNKNOWN"
        result["reconcile_required"] = True
        result["error"] = f"{message}；操作结果未知，必须先只读对账，禁止重试 {command}"
    return result


def _make_result(
    ok: bool = True,
    *,
    operation: str = "",
    result: any = None,
    warnings: list | None = None,
    error: str | None = None,
    reconcile_required: bool = False,
    operation_id: str = "",
    extra: dict | None = None,
) -> dict:
    """统一返回格式（计划 1 阶段 1.3）

    所有 MCP 工具应使用此函数构造返回，确保前端和 Orchestrator 可统一解析。
    """
    if not operation_id:
        operation_id = uuid.uuid4().hex
    ret = {
        "ok": ok,
        "status": "success" if ok else "error",
        "operation": operation,
        "operation_id": operation_id,
        "result": result if result is not None else {},
        "warnings": warnings or [],
        "error": error if not ok else None,
        "reconcile_required": reconcile_required,
    }
    if extra:
        ret.update(extra)
    return ret


def _run_worker(command: str, payload: dict) -> dict:
    """调用 TiaWorker.exe，并保持 V21 目标、退出码与未知结果均失败关闭。"""
    if not TIA_WORKER.exists():
        return _worker_error(command, f"TiaWorker.exe not found at {TIA_WORKER}")

    try:
        target = _control_target()
    except ValueError as exc:
        return _worker_error(command, str(exc))

    payload = dict(payload)
    configured_project = str(target.project_path)
    supplied_project = payload.get("ProjectPath")
    if supplied_project and not _same_path(str(supplied_project), configured_project):
        return _worker_error(command, "拒绝非唯一配置中的 TIA 项目路径")
    if supplied_project:
        payload["ProjectPath"] = configured_project

    is_mutating = TiaWorkerClient.is_mutating_command(command)
    operation_id = ""
    if is_mutating:
        operation_id = str(payload.get("OperationId") or uuid.uuid4().hex)
        payload["OperationId"] = operation_id

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [str(TIA_WORKER), f"--tia-major-version={target.tia_version}", command, tmp_path],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout.strip()
        if output:
            decoded = json.loads(output)
            if decoded.get("ok") is not True:
                return _worker_error(command, str(decoded.get("error") or "TiaWorker 返回失败"), operation_id=operation_id)
            if result.returncode != 0:
                return _worker_error(
                    command,
                    str(decoded.get("error") or f"TiaWorker 返回码 {result.returncode}"),
                    operation_id=operation_id,
                )
            if operation_id:
                decoded["operation_id"] = operation_id
            return decoded
        return _worker_error(
            command,
            result.stderr or "TiaWorker 无输出",
            operation_id=operation_id,
            outcome_unknown=is_mutating,
        )
    except subprocess.TimeoutExpired:
        return _worker_error(
            command,
            "TiaWorker timeout (120s)",
            operation_id=operation_id,
            outcome_unknown=is_mutating,
        )
    except json.JSONDecodeError:
        return _worker_error(
            command,
            f"Invalid JSON: {output[:500]}",
            operation_id=operation_id,
            outcome_unknown=is_mutating,
        )
    except Exception as exc:
        return _worker_error(
            command,
            str(exc),
            operation_id=operation_id,
            outcome_unknown=is_mutating,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _resolve_path(project_path: str) -> str:
    target = _control_target()
    configured_project = str(target.project_path)
    if project_path and not _same_path(project_path, configured_project):
        raise ValueError("拒绝非唯一配置中的 TIA 项目路径")
    return configured_project


def _resolve_scl_template(template) -> Path:
    """校验 SCL 模板名：只允许 SCL_TEMPLATES 目录中实际存在的 .md 模板。

    模板内容会被拼入 prompt 发往外部 DeepSeek API，任意路径（绝对路径/
    .. 穿越）会把任意本地 .md 文件外发，因此模板名必须在目录实际文件
    （运行时枚举的白名单）之内；_rules.md 是规则文件而非模板，排除在外。
    不在白名单内直接抛 ValueError（参数错误），不降级为无模板生成。
    """
    if not isinstance(template, str) or not template.strip():
        raise ValueError("参数 template 必须是非空字符串")
    template = template.strip()
    if template == "_rules" or "/" in template or "\\" in template or ".." in template:
        raise ValueError(f"未知模板: {template}（不在 SCL 模板白名单内）")
    root = SCL_TEMPLATES.resolve()
    candidate = (root / f"{template}.md").resolve()
    if candidate.parent != root or not candidate.is_file():
        raise ValueError(f"未知模板: {template}（不在 SCL 模板白名单内）")
    return candidate


def _gen_scl_via_deepseek(description: str, template: str) -> dict:
    """调用 DeepSeek 生成 SCL 代码"""
    template_text = ""
    template_file = _resolve_scl_template(template)
    if template_file.exists():
        template_text = template_file.read_text(encoding="utf-8")

    # 加载 SCL 外部源规则（优雅降级：文件不存在时仅 log warning）
    rules_text = ""
    rules_file = SCL_TEMPLATES / "_rules.md"
    if rules_file.exists():
        try:
            rules_text = rules_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("读取 SCL 规则文件失败: %s", e)
    else:
        logger.warning("SCL 规则文件不存在: %s", rules_file)

    prompt = f"""你是西门子 SCL (Structured Control Language) 编程专家。

请根据以下描述生成符合 IEC 61131-3 标准的 SCL 代码。

## 要求
- 使用西门子 S7-1200/1500 SCL 语法
- 必须包含: 急停互锁、故障处理、输出限幅
- 变量命名: 匈牙利命名法 (bEmergencyStop, rMotorSpeed, iState 等)
- 每个 FB 包含状态机 (INIT/RUN/FAULT/STOP)
- 代码必须有中文注释
- FUNCTION_BLOCK 名称使用英文，如 "MotorControl"

{rules_text}

{template_text}

## 功能描述
{description}

## 输出格式
返回 JSON，含 scl_code 和 block_name 字段:
```json
{{"scl_code": "...", "block_name": "..."}}
```
只返回 JSON，不要其他内容。

请严格遵守《外部源 SCL 规范》中的全部规则，违反任意一条均会导致 TIA Portal 编译失败。"""

    resp = _deepseek_chat([{"role": "user", "content": prompt}])
    content = resp["choices"][0]["message"]["content"]

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    result = json.loads(content.strip())
    return {
        "status": "ok",
        "data": result,
        "scl_code": result.get("scl_code", ""),
        "block_name": result.get("block_name", ""),
    }


# ─── MCP 工具 ───────────────────────────────────────────


@mcp.tool()
def list_devices(project_path: str = "", auth_token: str = "") -> dict:
    """列出 TIA Portal 项目中的 PLC 设备。

    Args:
        project_path: TIA 项目路径 (.ap19 文件)，留空使用默认值
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    try:
        path = _resolve_path(project_path)
        return _run_worker("list-devices", {"ProjectPath": path})
    except ValueError as e:
        return {"status": "error", "error": str(e)}


# SCL 语义安全校验（与 LAD safety_validate_ladder 对齐的轻量启发式）
_MOTOR_OUTPUT_KEYWORDS = ("motor", "run", "fwd", "forward", "rev", "reverse", "pump", "conveyor")


def _scl_outputs_set_true(line: str, output_names: set) -> bool:
    """判断语句行中是否有输出被直接赋值为 TRUE 字面量。"""
    upper = line.upper()
    for name in output_names:
        m = re.search(r'\b' + re.escape(name) + r'\s*:=', upper)
        if not m:
            continue
        rest = upper[m.end():].lstrip()
        if rest.startswith("TRUE"):
            return True
    return False


def _require_scl_semantic_safety(scl_code: str) -> list:
    """对 SCL 做电机类输出块的语义安全校验（急停/过载/正反转互锁）。

    与 LAD 路径 safety_validate_ladder 对齐：仅当块声明了电机类输出
    （名称含 motor/run/fwd/rev/pump/conveyor）时才强制要求急停与过载
    引用；同时禁止在同一语句中同时把正转和反转输出置 TRUE 字面量。

    Returns:
        list[str]: 违规列表；为空表示通过。
    """
    if not scl_code or not scl_code.strip():
        return []

    output_section = ""
    m = re.search(r'\bVAR_OUTPUT\b(.*?)\bEND_VAR\b', scl_code, re.DOTALL | re.IGNORECASE)
    if m:
        output_section = m.group(1)
    output_names = {name.strip() for name in re.findall(r'\b([A-Za-z_]\w*)\s*:', output_section)}

    motor_outputs = {n for n in output_names
                     if any(k in n.casefold() for k in _MOTOR_OUTPUT_KEYWORDS)}
    if not motor_outputs:
        return []

    lowered = scl_code.casefold()
    warnings = []
    # 急停/过载引用（命名规则与 safety_validate_ladder 的 _is_estop/_is_overload 对齐）
    if not any(k in lowered for k in ("estop", "emergency", "stop")):
        warnings.append("电机类输出块缺少急停互锁引用（变量名须含 stop/emergency）")
    if not any(k in lowered for k in ("overload", "fault")):
        warnings.append("电机类输出块缺少过载保护引用（变量名须含 overload/fault）")

    # 正反转互锁：同一语句不得同时将正转与反转输出置 TRUE
    fwd_outputs = {n for n in motor_outputs
                   if any(k in n.casefold() for k in ("fwd", "forward"))}
    rev_outputs = {n for n in motor_outputs
                   if any(k in n.casefold() for k in ("rev", "reverse"))}
    if fwd_outputs and rev_outputs:
        for lineno, line in enumerate(scl_code.splitlines(), 1):
            if "TRUE" not in line.upper():
                continue
            if _scl_outputs_set_true(line, fwd_outputs) and _scl_outputs_set_true(line, rev_outputs):
                warnings.append(f"第 {lineno} 行同时将正转与反转输出置 TRUE，缺少互锁")
                break
    return warnings


@mcp.tool()
def import_scl_file(
    scl_code: str,
    block_name: str,
    project_path: str = "",
    tags: str = "",
    replace: bool = False,
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """将 SCL 源代码导入 TIA Portal 项目并生成程序块。

    工作流: 写入 .scl 文件 -> TIA 外部源导入 -> 生成 FB/FC/DB

    Args:
        scl_code: SCL 源代码 (FUNCTION_BLOCK ... END_FUNCTION_BLOCK)
        block_name: 程序块名称 (如 "MotorControl"，与 SCL 代码中的名称一致)
        project_path: TIA 项目路径，留空使用默认值
        tags: 可选，JSON 格式的标签列表，在导入 SCL 前先创建标签。
              格式: '[{"name":"I0_8","dataType":"Bool","address":"%I0.8","comment":"急停"},...]'
        replace: 是否覆盖同名外部源（True 则先删旧同名外部源再导入，避免 "name not unique" 错误）
        confirmation_token: 一次性人工确认令牌（危险工程操作必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("import_scl_file", block_name=block_name,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
    except ValueError as e:
        return {"status": "error", "error": str(e)}

    # 可选：先创建 PLC 标签（否则 SCL 中引用的标签名会报"未定义"）
    if tags:
        try:
            tag_list = json.loads(tags)
            from create_plc_tags import create_tags
            tag_result = create_tags(path, tag_list)
            if tag_result.get("status") != "ok":
                return {"status": "error",
                        "error": f"标签创建失败: {tag_result.get('error')}",
                        "tag_result": tag_result}
        except json.JSONDecodeError as e:
            return {"status": "error", "error": f"tags 参数 JSON 解析失败: {e}"}

    # SCL 静态校验（写盘前拦截已知编译错误）
    try:
        from scl_lint import lint_scl
        lint_errors = lint_scl(scl_code)
        if lint_errors:
            audit_log("import_scl_file", user_input=scl_code[:200], block_name=block_name,
                      result="lint_blocked", detail=str(lint_errors)[:200])
            return {"status": "error", "lint_errors": lint_errors,
                    "message": f"SCL 静态校验发现 {len(lint_errors)} 个违规，已阻止导入"}
    except ImportError:
        pass  # scl_lint 模块不可用时跳过校验

    # SCL 语义安全校验（与 LAD 路径 safety_validate_ladder 对齐：
    # 电机类输出块必须含急停/过载引用与正反转互锁）
    semantic_warnings = _require_scl_semantic_safety(scl_code)
    if semantic_warnings:
        audit_log("import_scl_file", user_input=scl_code[:200], block_name=block_name,
                  result="semantic_blocked", detail=str(semantic_warnings)[:200])
        return {"status": "error", "semantic_errors": semantic_warnings,
                "message": f"SCL 语义安全校验发现 {len(semantic_warnings)} 个违规，已阻止导入"}

    # 写入系统临时文件（去除 BOM，确保 UTF-8 无 BOM）。不得使用由调用方
    # 提供的 block_name 拼接路径，且 worker 返回后立即清理。
    scl_code = scl_code.lstrip("\ufeff")
    tmp_scl_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".scl", prefix="tia-scl-", delete=False, encoding="utf-8"
        ) as scl_file:
            scl_file.write(scl_code)
            tmp_scl_path = scl_file.name
        command = "import-scl-replace" if replace else "import-scl"
        result = _run_worker(command, {
            "ProjectPath": path,
            "SclFilePath": tmp_scl_path,
        })
    finally:
        if tmp_scl_path:
            try:
                os.unlink(tmp_scl_path)
            except OSError:
                pass

    success = result.get("status") != "error"
    audit_log("import_scl_file",
              user_input=scl_code[:200], block_name=block_name,
              replace=replace, result="ok" if success else "error",
              detail=str(result.get("error", ""))[:200],
              success=success)
    return result


@mcp.tool()
def create_plc_tags(
    tags_json: str,
    project_path: str = "",
    tag_table_name: str = "PickAndPlace_IO",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """在 TIA Portal 项目中批量创建 PLC 标签（幂等，已存在则跳过）。

    用于在导入 SCL 外部源文件之前创建所需的 I/O 标签，
    解决 SCL 中引用标签名（如 "I0_8"）因"未定义"而编译失败的问题。

    Args:
        tags_json: JSON 格式的标签列表。
                   格式: '[{"name":"I0_8","dataType":"Bool","address":"%I0.8","comment":"急停"},...]'
        project_path: TIA 项目路径，留空使用默认值
        tag_table_name: 标签表名称，默认 "PickAndPlace_IO"
        confirmation_token: 一次性人工确认令牌（直接改写工程内容，必填，fail-closed）
        auth_token: 认证令牌

    Returns:
        {"status": "ok", "created": N, "skipped": N, "errors": [...]}
    """
    _require_auth(auth_token)
    gate = _safety_gate("create_plc_tags", block_name=tag_table_name,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
    except ValueError as e:
        return {"status": "error", "error": str(e)}

    try:
        tag_list = json.loads(tags_json)
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"tags_json 解析失败: {e}"}

    from create_plc_tags import create_tags
    result = create_tags(path, tag_list, tag_table_name)
    success = result.get("status") != "error"
    audit_log("create_plc_tags", user_input=tags_json[:200], block_name=tag_table_name,
              result="ok" if success else "error",
              detail=str(result.get("error", ""))[:200],
              success=success)
    return result


@mcp.tool()
def compile_project(project_path: str = "", confirmation_token: str = "", auth_token: str = "") -> dict:
    """编译 TIA Portal 项目。

    Args:
        project_path: TIA 项目路径，留空使用默认值
        confirmation_token: 一次性人工确认令牌（危险工程操作必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("compile_project", confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
        result = _run_worker("compile", {"ProjectPath": path})
        success = result.get("ok") is True
        audit_log("compile_project", result="ok" if success else "error",
                  detail=str(result.get("error", ""))[:200],
                  success=success)
        return result
    except ValueError as e:
        audit_log("compile_project", result="error", detail=str(e)[:200], success=False)
        return {"status": "error", "error": str(e)}

@mcp.tool()
def list_blocks(
    block_type: str = "all",
    project_path: str = "",
    auth_token: str = "",
) -> dict:
    """列出 TIA 项目中的程序块（FB/FC/DB/SFB/SFC）。

    Args:
        block_type: 块类型 — "all" (全部), "fb", "fc", "db", "udt"
        project_path: TIA 项目路径，留空使用默认值
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    try:
        path = _resolve_path(project_path)
        return _run_worker("list-blocks", {"ProjectPath": path, "BlockType": block_type})
    except ValueError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def create_block(
    block_name: str,
    block_type: str = "FB",
    template: str = "general",
    project_path: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """在 TIA 项目中创建空程序块。

    Args:
        block_name: 块名称（如 "MyFunctionBlock"）
        block_type: 块类型 — "FB", "FC", "DB", "UDT"
        template: 模板名称（可选，预留扩展）
        project_path: TIA 项目路径，留空使用默认值
        confirmation_token: 一次性人工确认令牌（直接改写工程内容，必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("create_block", block_name=block_name,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
        result = _run_worker("create-block", {
            "ProjectPath": path,
            "BlockName": block_name,
            "BlockType": block_type,
        })
        success = result.get("ok") is True
        audit_log("create_block", block_name=block_name,
                  result="ok" if success else "error",
                  detail=str(result.get("error", ""))[:200],
                  success=success)
        return result
    except ValueError as e:
        audit_log("create_block", block_name=block_name,
                  result="error", detail=str(e)[:200], success=False)
        return {"status": "error", "error": str(e)}


def _resolve_export_path(export_path: str, block_name: str) -> str:
    """解析并校验块导出路径：只允许配置输出目录内的绝对路径。

    与 _resolve_path 的唯一目标校验模式对齐：留空时使用配置输出目录下的
    默认文件名（TiaWorker 要求 OutputPath 非空）；提供时规范化为绝对路径
    并要求仍位于 cfg.tia.output_dir 内，.. 穿越与目录外绝对路径一律拒绝
    （TiaWorker 收到的是绝对路径，导出会真实写盘）。
    """
    output_dir = os.path.normcase(os.path.abspath(str(cfg.tia.output_dir)))
    if not export_path:
        return os.path.join(output_dir, f"{block_name}.scl")
    candidate = os.path.normcase(os.path.abspath(export_path))
    if candidate != output_dir and not candidate.startswith(output_dir + os.sep):
        raise ValueError("拒绝输出目录之外的导出路径")
    return candidate


@mcp.tool()
def export_block(
    block_name: str,
    export_path: str = "",
    project_path: str = "",
    auth_token: str = "",
) -> dict:
    """导出 TIA 项目中的程序块为 SCL/DB 文件。

    Args:
        block_name: 块名称（如 "FB501"）
        export_path: 导出路径（可选，必须位于配置输出目录内，留空使用默认输出目录）
        project_path: TIA 项目路径，留空使用默认值
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("export_block", block_name=block_name)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
        resolved_export = _resolve_export_path(export_path, block_name)
        result = _run_worker("export-block", {
            "ProjectPath": path,
            "BlockName": block_name,
            # TiaWorker/Program.cs 的 ExportBlockInput DTO 读 OutputPath（不是 ExportPath）
            "OutputPath": resolved_export,
        })
        success = result.get("ok") is True
        audit_log("export_block", block_name=block_name,
                  result="ok" if success else "error",
                  detail=str(result.get("error", ""))[:200],
                  success=success)
        return result
    except ValueError as e:
        audit_log("export_block", block_name=block_name,
                  result="error", detail=str(e)[:200], success=False)
        return {"status": "error", "error": str(e)}


@mcp.tool()
def list_udts(project_path: str = "", auth_token: str = "") -> dict:
    """列出项目中所有 UDT 数据类型。

    Args:
        project_path: TIA 项目路径，留空使用默认值
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    try:
        path = _resolve_path(project_path)
        return _run_worker("list-udts", {"ProjectPath": path})
    except ValueError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def go_online(
    device_name: str = "PLC_1",
    project_path: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """建立与 PLC 的在线连接。

    Args:
        device_name: PLC 设备名称
        project_path: TIA 项目路径，留空使用默认值
        confirmation_token: 一次性人工确认令牌（在线连接状态变更，必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("go_online", block_name=device_name,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
        result = _run_worker("go-online", {"ProjectPath": path, "DeviceName": device_name})
        success = result.get("ok") is True
        audit_log("go_online", block_name=device_name,
                  result="ok" if success else "error",
                  detail=str(result.get("error", ""))[:200],
                  success=success)
        return result
    except ValueError as e:
        audit_log("go_online", block_name=device_name,
                  result="error", detail=str(e)[:200], success=False)
        return {"status": "error", "error": str(e)}


@mcp.tool()
def go_offline(
    device_name: str = "PLC_1",
    project_path: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """断开与 PLC 的在线连接。

    Args:
        device_name: PLC 设备名称
        project_path: TIA 项目路径，留空使用默认值
        confirmation_token: 一次性人工确认令牌（在线连接状态变更，必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("go_offline", block_name=device_name,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
        result = _run_worker("go-offline", {"ProjectPath": path, "DeviceName": device_name})
        success = result.get("ok") is True
        audit_log("go_offline", block_name=device_name,
                  result="ok" if success else "error",
                  detail=str(result.get("error", ""))[:200],
                  success=success)
        return result
    except ValueError as e:
        audit_log("go_offline", block_name=device_name,
                  result="error", detail=str(e)[:200], success=False)
        return {"status": "error", "error": str(e)}




@mcp.tool()
def download_to_plcsim(
    project_path: str = "",
    compile_first: bool = False,
    method: str = "auto",
    target_ip: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """将项目下载到 PLCSIM 仿真 PLC。

    下载策略（自动模式）:
      1. TiaWorker.exe — 通过 Openness API DownloadProvider 下载（需 GUI 确认）
      2. UI Automation — 模拟 GUI 点击（自动 fallback）
      3. 手动指引 — 最末备选

    Args:
        project_path: TIA 项目路径，留空使用默认值
        compile_first: 下载前先编译
        method: "auto" (自动), "tiaworker", "tiaworker-gui", "python" 或 "ui"
        target_ip: 已弃用；下载目标只能来自经验证的配置
        confirmation_token: 一次性人工确认令牌（危险工程操作必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("download_to_plcsim", block_name=project_path,
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate

    def _finish(status: str, **fields) -> dict:
        """构造下载结果并写入 HMAC 链式审计（每次工具调用只记一条）。"""
        audit_log("download_to_plcsim", user_input=project_path, block_name=project_path,
                  result=status,
                  detail=str(fields.get("message") or fields.get("error", ""))[:200],
                  success=status == "ok")
        out = {"status": status}
        out.update(fields)
        return out

    try:
        path = _resolve_path(project_path)
        from download_to_plcsim import (
            _try_download_via_python,
            _try_download_via_tiaworker,
            _try_download_via_tiaworker_gui,
            _verified_plcsim_target,
            download_via_ui,
        )
        method = method.strip().lower()
        if method not in {"auto", "tiaworker", "tiaworker-gui", "python", "ui"}:
            return _finish("error", error=f"不支持的 method: {method}")
        target_ip = _verified_plcsim_target(target_ip)

        if method == "ui":
            rc = download_via_ui(compile_first)
            return _finish("ok" if rc == 0 else "error",
                           message="UI Automation 下载完成" if rc == 0 else "UI Automation 下载失败")

        if method == "tiaworker":
            rc = _try_download_via_tiaworker(compile_first, target_ip)
            return _finish("ok" if rc == 0 else "error",
                           message="TiaWorker 下载完成" if rc == 0 else "TiaWorker 未确认设备下载成功")

        if method == "tiaworker-gui":
            rc = _try_download_via_tiaworker_gui(target_ip)
            return _finish("ok" if rc == 0 else "error",
                           message="TiaWorker GUI 下载完成" if rc == 0 else "TiaWorker GUI 未确认设备下载成功")

        if method == "python":
            rc = _try_download_via_python(compile_first, target_ip)
            return _finish("ok" if rc == 0 else "error",
                           message="Python API 下载完成" if rc == 0 else "Python API 未确认设备下载成功")

        # 仅当上一策略明确“不具备能力”(rc=-1) 时才切换，未知或失败结果禁止重试。
        rc = _try_download_via_tiaworker(compile_first, target_ip)
        if rc == 0:
            return _finish("ok", message="TiaWorker 下载完成")

        if rc == -1:
            rc = _try_download_via_tiaworker_gui(target_ip)
            if rc == 0:
                return _finish("ok", message="TiaWorker GUI 下载完成",
                               note="headless TiaWorker 不可用，使用 GUI 模式")

        if rc == -1:
            rc = _try_download_via_python(compile_first, target_ip)
            if rc == 0:
                return _finish("ok", message="Python API 下载完成",
                               note="TiaWorker 不可用，使用 Python API")

        if rc == -1:
            rc = download_via_ui(compile_first=False)
            if rc == 0:
                return _finish("ok", message="UI Automation 下载完成",
                               note="自动接口均不可用，使用 UI Automation")

        return _finish("error",
                       message="未获得设备级下载成功回执，请手动下载并只读核验",
                       manual_steps=[
                           "1. 打开 TIA Portal，右键 PLC 设备",
                           "2. 下载到设备 → 软件（全部）",
                           "3. PG/PC 接口选 PLCSIM",
                           "4. 下载 → 完成",
                       ])
    except ValueError as e:
        return _finish("error", error=str(e))


@mcp.tool()
def generate_scl_code(
    description: str,
    template: str = "general",
    auth_token: str = "",
) -> dict:
    """使用 AI 根据自然语言描述生成 SCL 代码。

    Args:
        description: 功能描述，如 "三相异步电机正反转控制，含急停和过载保护"
        template: 模板名 — 必须是 plc-code-templates/siemens-scl 目录下实际存在的
                  .md 模板（白名单校验），如 general, motor-control, conveyor, pid-controller
        auth_token: 认证令牌

    Returns:
        {"status": "ok", "data": {"scl_code": "...", "block_name": "..."}}
    """
    _require_auth(auth_token)
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
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """一站式：AI 生成 SCL 代码 + 导入到 TIA Portal 项目。

    Args:
        description: 功能描述
        block_name: 块名称，留空由 AI 自动命名
        template: 代码模板名（须为 plc-code-templates/siemens-scl 内实际存在的 .md 模板）
        project_path: TIA 项目路径
        confirmation_token: 一次性人工确认令牌（导入为危险工程操作，必填）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    result = generate_scl_code(description, template, auth_token=auth_token)
    if result.get("status") != "ok":
        return result

    data = result["data"]
    name = block_name or data.get("block_name", "AutoGen")
    scl = data.get("scl_code", "")

    if not scl:
        return {"status": "error", "error": "AI 未生成有效 SCL 代码"}

    return import_scl_file(scl, name, project_path,
                           confirmation_token=confirmation_token, auth_token=auth_token)


# ─── 梯形图 LAD 工具 ─────────────────────────────


def _gen_lad_spec(description: str, block_name: str) -> dict:
    """调用 DeepSeek 生成 LadderSpec JSON + 解析 + Schema 校验"""
    prompt = _LAD_PROMPT_TEMPLATE.format(description=description)
    ai_result = _call_deepseek(prompt)
    content = ai_result["choices"][0]["message"]["content"]

    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    raw = json_match.group(1).strip() if json_match else content.strip()

    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"DeepSeek 返回的不是合法 JSON: {e}. 原始内容前200字: {content[:200]}",
            e.doc, e.pos,
        )

    if not isinstance(spec, dict):
        raise ValueError("DeepSeek 返回的不是 JSON 对象")
    if "networks" not in spec or not isinstance(spec["networks"], list):
        raise ValueError("JSON 缺少 networks 数组")

    spec.setdefault("blockName", block_name or "AutoGen")
    spec.setdefault("blockNumber", 100)
    if block_name:
        spec["blockName"] = block_name

    validation = validate_ladder_spec(spec)
    if not validation["valid"]:
        raise ValueError(f"LadderSpec 格式校验失败: {validation['errors']}")

    # 语义安全校验统一由 create_ladder_block 调用一次（_run_cartgen 不再重复扫描）
    return spec


def _require_ladder_semantic_safety(spec: dict) -> dict:
    """将语义安全校验作为 CartGen/TIA 导入前的硬阻断。"""
    validation = safety_validate_ladder(spec)
    if not validation.get("safe"):
        warnings = validation.get("warnings", ["未知语义安全错误"])
        raise ValueError(f"LadderSpec 语义安全校验失败: {warnings}")
    return spec


def _run_cartgen(spec: dict) -> str:
    """保存 LadderSpec JSON + 调用 CartGen 生成 SimaticML XML，返回 XML 路径。

    语义安全校验由调用方 create_ladder_block 统一执行一次。
    """
    tmp_json = os.path.join(tempfile.gettempdir(), f"lad_{spec['blockName']}.json")
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    output_dir = cfg.tia.output_dir
    os.makedirs(output_dir, exist_ok=True)
    xml_path = os.path.join(output_dir, f"{spec['blockName']}.xml")
    dll_path = cfg.cartgen.dll_path

    r = subprocess.run(
        ["dotnet", "exec", dll_path, tmp_json, xml_path],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0:
        err_text = r.stderr.decode('utf-8', 'ignore') or r.stdout.decode('utf-8', 'ignore')
        raise RuntimeError(f"CartGen 失败: {err_text[:500]}")

    _verify_cartgen_artifacts(spec, xml_path)

    return xml_path


def _cartgen_io_manifest_path(xml_path: str) -> Path:
    return Path(xml_path).with_suffix(".io-map.json")


def _expected_io_mapping(spec: dict) -> dict:
    interface = spec.get("interface", {})

    def _entries(section: str) -> list[dict]:
        return [
            {"name": item["name"], "type": item["type"], "address": item["address"]}
            for item in interface.get(section, [])
        ]

    return {
        "blockName": spec["blockName"],
        "inputs": _entries("inputs"),
        "outputs": _entries("outputs"),
    }


def _verify_cartgen_artifacts(spec: dict, xml_path: str) -> None:
    """验证 CartGen 同时生成 XML 和未丢失 I/O 映射的清单。"""
    xml = Path(xml_path)
    if not xml.is_file() or xml.stat().st_size == 0:
        raise RuntimeError("CartGen 未生成有效 XML 文件")

    manifest = _cartgen_io_manifest_path(xml_path)
    if not manifest.is_file() or manifest.stat().st_size == 0:
        raise RuntimeError("CartGen 未生成 I/O 映射清单，拒绝导入")
    try:
        actual = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("CartGen I/O 映射清单不可读取，拒绝导入") from exc

    expected = _expected_io_mapping(spec)
    if actual != expected:
        raise RuntimeError("CartGen I/O 映射清单与 LadderSpec 不一致，拒绝导入")


def _clean_xml(xml_path: str) -> None:
    """清洗 XML 中空的 MultilingualTextItem 元素（原位覆盖）"""
    with open(xml_path, "r", encoding="utf-8") as f:
        xml = f.read()
    xml = re.sub(
        r'<MultilingualTextItem[^>]*>\s*<AttributeList>\s*<Culture>[^<]*</Culture>\s*<Text\s*/>\s*</AttributeList>\s*</MultilingualTextItem>\s*',
        "", xml,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)


def _import_xml_into_tia(xml_path: str) -> dict:
    """将 SimaticML XML 导入 TIA Portal"""
    p = _resolve_path("")
    if not p:
        raise ValueError("未指定项目路径，请在 config.yaml 或 .env 中设置 TIA_PROJECT_PATH")

    from tia_session import tia_session
    from Siemens.Engineering import ImportOptions
    from Siemens.Engineering.SW import SWImportOptions
    from Siemens.Engineering.Compiler import ICompilable
    from System.IO import FileInfo

    with tia_session(p) as (project, plc_sw):
        if not plc_sw:
            raise RuntimeError("未找到 PLC 设备")

        plc_sw.BlockGroup.Blocks.Import(
            FileInfo(xml_path), ImportOptions.Override, SWImportOptions(2))
        compiler = plc_sw.GetService[ICompilable]()
        compile_result = compiler.Compile()
        project.Save()

        # 编译失败必须失败关闭：与 call_fb_in_ob1.py 检查 cr.State 的做法一致
        state = compile_result.State.ToString()
        error_count = int(compile_result.ErrorCount)
        if state != "Success" or error_count > 0:
            return _make_result(
                ok=False, operation="_import_xml_into_tia",
                error=f"LAD 导入后编译失败: State={state}, ErrorCount={error_count}",
                result={"compile_state": state, "compile_error_count": error_count},
            )

    return _make_result(ok=True, operation="_import_xml_into_tia",
                        result={"compile_state": "Success", "compile_error_count": 0})


def _render_lad_svg(spec: dict) -> str:
    """渲染梯形图 SVG 预览，返回 SVG 字符串（不可用时返回空字符串）"""
    if not _HAS_SVG:
        return ""
    try:
        return render_svg_preview(spec)
    except Exception:
        return ""


def _audit_lad_creation(description: str, block_name: str, networks_count: int, result: str) -> None:
    """记录梯形图创建操作到审计日志"""
    audit_log("create_ladder_block", user_input=description,
              block_name=block_name, result=result,
              networks=networks_count)


@mcp.tool()
def create_ladder_block(
    description: str = "cart3cycle",
    block_name: str = "AutoCart3Cycle",
    project_path: str = "",
    auth_token: str = "",
) -> dict:
    """在 TIA Portal 中创建梯形图 (LAD) 功能块。

    description 说明:
      - "cart3cycle" → 材料小车往复3次（硬编码模板）
      - 其他描述 → 调 DeepSeek 生成 LadderSpec JSON → CartGen → TIA Portal

    Args:
        description: 功能描述，如 "电机正反转，带急停和过载"
        block_name: 块名称
        project_path: TIA 项目路径
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("create_ladder_block")
    if gate:
        return gate
    # 不允许硬编码模板绕过 LadderSpec 的结构和语义安全闸门。
    if description == "cart3cycle":
        return _make_result(ok=False, operation="create_ladder_block",
                            error="cart3cycle 硬编码路径未提供可审计 LadderSpec，已在导入前安全阻断")

    # AI 生成流程
    try:
        # 统一路径校验：任何非受控项目路径都被拒绝
        _resolve_path(project_path)
        spec = _gen_lad_spec(description, block_name)
        _require_ladder_semantic_safety(spec)
        xml_path = _run_cartgen(spec)
        _clean_xml(xml_path)
        import_result = _import_xml_into_tia(xml_path)
        if not import_result.get("ok"):
            _audit_lad_creation(description, spec.get("blockName"),
                                len(spec.get("networks", [])), "error")
            return _make_result(ok=False, operation="create_ladder_block",
                                error=import_result.get("error", "LAD 导入 TIA 失败"),
                                extra={"step": "_import_xml_into_tia"})
        svg_preview = _render_lad_svg(spec)
        _audit_lad_creation(description, spec.get("blockName"),
                            len(spec.get("networks", [])), "ok")
        return _make_result(ok=True, operation="create_ladder_block",
                            result={
                                "blockName": spec.get("blockName"),
                                "networks": len(spec.get("networks", [])),
                                "xmlPath": xml_path,
                                "svg_preview": svg_preview,
                            })
    except json.JSONDecodeError as e:
        return _make_result(ok=False, operation="create_ladder_block",
                            error=f"DeepSeek 返回的不是合法 JSON: {e}")
    except ValueError as e:
        return _make_result(ok=False, operation="create_ladder_block", error=str(e))
    except Exception as e:
        return _make_result(ok=False, operation="create_ladder_block",
                            error=f"{type(e).__name__}: {e}")


# ─── 一键全流程 ───────────────────────────────────────


@mcp.tool()
def call_fb_in_ob1(
    fb_names: list,
    project_path: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """在 OB1 中自动调用指定的 FB（如 FB501 ConveyorControl）。

    创建 MasterIO FB 聚合所有指定 FB，并在 OB1 中调用。
    适用于 IO 映射 FB 或任何需要在主循环中周期调用的 FB。

    Args:
        fb_names: FB 名称列表，如 ["IO_Map_MotorControl", "FB501"]
        project_path: TIA 项目路径，留空使用默认值
        confirmation_token: 一次性人工确认令牌（直接改写工程内容，必填，fail-closed）
        auth_token: 认证令牌
    """
    _require_auth(auth_token)
    gate = _safety_gate("call_fb_in_ob1", block_name=str(fb_names),
                        confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    try:
        path = _resolve_path(project_path)
    except ValueError as e:
        return _make_result(ok=False, operation="call_fb_in_ob1", error=str(e))

    try:
        from call_fb_in_ob1 import insert_fb_calls
        result = insert_fb_calls(fb_names)
        rc = result == 0
        return _make_result(ok=rc, operation="call_fb_in_ob1",
                            result={
                                "fb_names": fb_names,
                                "return_code": result,
                                "message": "OB1 调用链创建成功" if rc else f"返回码：{result}",
                            })
    except Exception as e:
        return _make_result(ok=False, operation="call_fb_in_ob1", error=str(e))


@mcp.tool()
def full_pipeline(
    description: str,
    block_name: str = "",
    project_path: str = "",
    confirmation_token: str = "",
    auth_token: str = "",
) -> dict:
    """一键全流程：自然语言 → LAD FB → IO_Map → OB1 调用链 → 编译。

    串联 create_ladder_block + gen_io_map + call_fb_in_ob1 的完整流程。

    Args:
        description: 功能描述，如 "电机正反转，带急停和过载保护"
        block_name: 块名称（可选，留空自动生成）
        project_path: TIA 项目路径（可选，留空使用默认）
        confirmation_token: 一次性人工确认令牌（危险工程操作必填，fail-closed）
        auth_token: 认证令牌

    Returns:
        {"status": "ok", "blockName": "...", "steps": [...]}
    """
    _require_auth(auth_token)
    gate = _safety_gate("full_pipeline", confirmation_token=confirmation_token, auth_token=auth_token)
    if gate:
        return gate
    steps = []

    # ── Step 1: 生成 LAD FB ──
    result = create_ladder_block(description, block_name or "AutoGen", project_path, auth_token=auth_token)
    if not result.get("ok"):
        return _make_result(ok=False, operation="full_pipeline",
                            error=result.get("error", "LAD FB 生成失败"),
                            extra={"step": "create_ladder_block", "steps": steps})
    gen_block_name = result["result"]["blockName"]
    steps.append({"step": "create_ladder_block", "blockName": gen_block_name,
                   "networks": result["result"].get("networks", 0)})

    # ── Step 2: 生成 IO 映射 SCL ──
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, str(Path(__file__).parent))
        from gen_io_map import generate_io_map

        # 优先使用 Step1 中 _run_cartgen 刚写入的临时 JSON
        # （lad_{blockName}.json 即本次生成的真实 LadderSpec，无需全量扫描模板目录）
        template_dir = cfg.generation.templates_dir
        json_path = None
        tmp = _os.path.join(tempfile.gettempdir(), f"lad_{gen_block_name}.json")
        if _os.path.exists(tmp):
            json_path = tmp
        else:
            for fname in _os.listdir(template_dir):
                if fname.endswith('.json'):
                    fpath = _os.path.join(template_dir, fname)
                    with open(fpath, encoding='utf-8') as f:
                        spec = json.load(f)
                    if spec.get('blockName') == gen_block_name:
                        json_path = fpath
                        break

        if not json_path:
            steps.append({"step": "gen_io_map", "status": "skipped",
                           "reason": "未找到模板 JSON 文件，IO 映射与 OB1 调用链未建成"})
            audit_log("full_pipeline", user_input=description, block_name=gen_block_name,
                      result="error", steps_count=len(steps),
                      detail="未找到模板 JSON，IO 映射未生成（fail-closed）")
            return _make_result(ok=False, operation="full_pipeline",
                                error="未找到模板 JSON，IO 映射与 OB1 调用链未建成",
                                extra={"step": "gen_io_map", "steps": steps})

        io_map_scl = generate_io_map(json_path)
        io_map_name = f"IO_Map_{gen_block_name}"
        output_dir = cfg.tia.output_dir
        scl_dir = _os.path.join(output_dir, 'scl')
        _os.makedirs(scl_dir, exist_ok=True)
        scl_path = _os.path.join(scl_dir, f"{io_map_name}.scl")
        with open(scl_path, 'w', encoding='utf-8-sig') as f:
            f.write(io_map_scl)
        steps.append({"step": "gen_io_map", "sclPath": scl_path, "blockName": io_map_name})

        # IO 映射 SCL 必须真正导入 TIA：仅写盘并报告成功是 fail-open。
        path = _resolve_path(project_path)
        tmp_scl_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".scl", prefix="tia-scl-", delete=False, encoding="utf-8"
            ) as scl_file:
                scl_file.write(io_map_scl.lstrip("\ufeff"))
                tmp_scl_path = scl_file.name
            import_result = _run_worker("import-scl-replace", {
                "ProjectPath": path,
                "SclFilePath": tmp_scl_path,
            })
        finally:
            if tmp_scl_path:
                try:
                    _os.unlink(tmp_scl_path)
                except OSError:
                    pass
        if import_result.get("ok") is not True:
            steps.append({"step": "gen_io_map_import", "status": "error",
                           "error": import_result.get("error", "IO 映射 SCL 导入 TIA 失败")})
            audit_log("full_pipeline", user_input=description, block_name=gen_block_name,
                      result="error", steps_count=len(steps),
                      detail=f"IO 映射 SCL 导入失败: {str(import_result.get('error', ''))[:200]}")
            return _make_result(ok=False, operation="full_pipeline",
                                error=import_result.get("error", "IO 映射 SCL 导入 TIA 失败"),
                                extra={"step": "gen_io_map_import", "steps": steps})
        steps.append({"step": "gen_io_map_import", "blockName": io_map_name, "result": "success"})
    except Exception as e:
        steps.append({"step": "gen_io_map", "status": "error", "error": str(e)})
        return _make_result(ok=False, operation="full_pipeline",
                            error=str(e), extra={"step": "gen_io_map", "steps": steps})

    # ── Step 3: OB1 调用链（insert_fb_calls 返回非 0 即失败，fail-closed）──
    try:
        from call_fb_in_ob1 import insert_fb_calls
        call_result = insert_fb_calls([io_map_name])
        if call_result != 0:
            steps.append({"step": "ob1_calls", "status": "error", "fb": io_map_name,
                           "error": f"OB1 调用链构建失败，返回码 {call_result}"})
            audit_log("full_pipeline", user_input=description, block_name=gen_block_name,
                      result="error", steps_count=len(steps),
                      detail=f"insert_fb_calls 返回 {call_result}")
            return _make_result(ok=False, operation="full_pipeline",
                                error=f"OB1 调用链构建失败，返回码 {call_result}",
                                extra={"step": "ob1_calls", "steps": steps})
        steps.append({"step": "ob1_calls", "fb": io_map_name, "result": "success"})
    except Exception as e:
        steps.append({"step": "ob1_calls", "status": "error", "error": str(e)})
        return _make_result(ok=False, operation="full_pipeline",
                            error=str(e), extra={"step": "ob1_calls", "steps": steps})

    audit_log("full_pipeline", user_input=description, block_name=gen_block_name,
              result="ok", steps_count=len(steps))
    return _make_result(ok=True, operation="full_pipeline",
                        result={"blockName": gen_block_name,
                                "networks": result["result"].get("networks", 0),
                                "steps": steps})


def _deepseek_chat(messages: list) -> dict:
    """调用 DeepSeek Chat API（公共内部函数）"""
    import requests
    api_key = cfg.deepseek.api_key
    if not api_key:
        raise ValueError("未配置 DEEPSEEK_API_KEY（请在 .env 或 config.yaml 中设置）")
    resp = requests.post(
        cfg.deepseek.api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": cfg.deepseek.model,
            "messages": messages,
            "temperature": cfg.deepseek.temperature,
            "max_tokens": cfg.deepseek.max_tokens,
        },
        timeout=cfg.deepseek.timeout_sec,
    )
    resp.raise_for_status()
    return resp.json()


def _call_deepseek(prompt: str) -> dict:
    """调用 DeepSeek API（兼容旧接口）"""
    return _deepseek_chat([{"role": "user", "content": prompt}])





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
        {{"type": "normally_open|normally_closed|coil|coil_set|coil_reset|timer_on_delay|timer_off_delay", "operand": "变量名（定时器类型不需要 operand，见下方定时器用法）"}}
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

## 定时器用法
- 延时接通: {{"type": "timer_on_delay", "timer_instance": "IEC_Timer_0", "preset_time": "T#5S"}}
- 延时断开: {{"type": "timer_off_delay", "timer_instance": "IEC_Timer_1", "preset_time": "T#3S"}}
- timer_instance 必须是唯一的（IEC_Timer_0, IEC_Timer_1, ...）
- preset_time 格式: T#5S (秒), T#100MS (毫秒), T#1M30S (1分30秒)
- 定时器的 Q 输出通过链式连接驱动后续元素，示例：
  ```
  {{"type": "normally_open", "operand": "iStart"}},
  {{"type": "timer_on_delay", "timer_instance": "IEC_Timer_0", "preset_time": "T#5S"}},
  {{"type": "coil", "operand": "oDone"}}
  ```
  等效于 LAD: || iStart ||--[TON IEC_Timer_0 PT=T#5S]--( ) oDone

## 变量命名规范
- 输入: iXxx（iStart, iStop, iOverload 等）
- 输出: oXxx（oRunFwd, oRunRev, oFault 等）
- 本地: mXxx（mSafetyOK, mState1 等）

## 用户描述
{description}"""

if __name__ == "__main__":
    # 认证令牌只从环境变量（TIA_MCP_AUTH_TOKEN / MCP_AUTH_TOKEN）读取；
    # 不提供 --auth-token CLI 参数，避免令牌暴露在进程命令行（ps/日志可见）。
    if not _AUTH_TOKEN:
        raise SystemExit("TIA MCP 拒绝启动：必须配置 TIA_MCP_AUTH_TOKEN 或 MCP_AUTH_TOKEN 环境变量")

    # 检查管理员权限 — TIA Portal Openness API 需要管理员权限
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print('⚠' * 30)
        print('⚠ TIA Portal Openness API 需要管理员权限！')
        print('⚠ 请以管理员身份运行此服务器:')
        print('⚠   "D:/Python3/python.exe" server.py')
        print('⚠' * 30)
        print()

    print(f"[TiaMCP] TIA Worker: {TIA_WORKER}")
    print(f"[TiaMCP] 默认项目: {cfg.tia.project_path}")
    print(f"[TiaMCP] DeepSeek: {'OK' if cfg.deepseek.api_key else '(未配置)'}")
    print(f"[TiaMCP] 输出目录: {cfg.tia.output_dir}")
    mcp.run()
