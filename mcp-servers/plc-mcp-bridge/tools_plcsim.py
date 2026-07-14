"""PLCSIM Advanced 管理工具"""
import os
from _helpers import mcp, _run_python, _format_result
from _helpers import PLCSIM_API, GOLDEN_ZIP, STORAGE_PATH
from mcp_common.control_target import TargetConfigurationError, get_control_target, require_control_ip


def _resolve_target(name: str = "", ip: str = ""):
    """管理操作只能作用于唯一隔离 PLCSIM 实例。"""
    try:
        target = get_control_target()
        if name and name != target.plcsim_instance:
            raise TargetConfigurationError(
                f"PLCSIM 实例必须为 {target.plcsim_instance}，收到 {name}"
            )
        require_control_ip(ip or target.plc_ip)
        return target, ""
    except TargetConfigurationError as exc:
        return None, f"🚫 操作被拒绝: {exc}"


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
    name: str = "",
    ip: str = "",
    cpu_type: str = "1511",
) -> str:
    """创建并启动一个新的 PLCSIM Advanced 空壳实例"""
    target, error = _resolve_target(name, ip)
    if error:
        return error
    result = _run_python(
        PLCSIM_API,
        ["create", target.plcsim_instance, target.plc_ip, cpu_type],
        timeout=120,
    )
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_stop_instance",
    annotations={"destructiveHint": True},
)
async def stop_instance(name: str = "") -> str:
    """停止并删除指定 PLCSIM Advanced 实例"""
    target, error = _resolve_target(name)
    if error:
        return error
    result = _run_python(PLCSIM_API, ["stop", target.plcsim_instance], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", ""))


@mcp.tool(
    name="plc_get_state",
    annotations={"readOnlyHint": True},
)
async def get_instance_state(name: str = "") -> str:
    """获取 PLCSIM 实例的运行状态(RUN/STOP/Off 等)"""
    target, error = _resolve_target(name)
    if error:
        return error
    instances = _run_python(PLCSIM_API, ["list"]).get("output", "")
    for line in instances.split("\n"):
        if target.plcsim_instance in line:
            return f"实例 `{target.plcsim_instance}` 状态:\n{line.strip()}"
    return f"实例 `{target.plcsim_instance}` 未找到或未运行"


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
    target, error = _resolve_target(name, ip)
    if error:
        return error
    n = target.plcsim_instance
    gz = golden_zip or GOLDEN_ZIP
    sp = storage_path or STORAGE_PATH
    p = target.plc_ip

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
async def archive_to_golden(name: str = "", golden_zip: str = "") -> str:
    """将当前 PLCSIM 实例状态保存为 golden backup

    下载到 PLCSIM 成功后调用此工具，更新 golden backup。
    下次 restore_from_golden 就能恢复到最新状态。
    """
    target, error = _resolve_target(name)
    if error:
        return error
    n = target.plcsim_instance
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
    target, error = _resolve_target(name, ip)
    if error:
        return error
    n = target.plcsim_instance
    p = target.plc_ip
    result = _run_python(PLCSIM_API, ["tcpip", n, p], timeout=60)
    return _format_result(result.get("success"), error=result.get("error", "切换失败"))
