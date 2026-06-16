"""诊断工具 — PLC 在线状态、连接管理"""
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, _dry_run_msg, PROJECT_PATH


@mcp.tool(name="plc_get_status_info", annotations={"readOnlyHint": True})
async def get_plc_status(device_name: str = "") -> str:
    """获取 PLCSIM 实例的运行状态（RUN/STOP/Off 等）

    Args:
        device_name: PLC 设备名称（默认自动选择）
    """
    if err := _check_project(): return err
    result = _run_tiaworker("get-plc-status", {
        "ProjectPath": PROJECT_PATH,
        "DeviceName": device_name,
    })
    if result.get("success"):
        d = result.get("data", {})
        return f"设备: {d.get('device', '?')}\n状态: {d.get('status', '?')}\n在线: {d.get('online', '?')}"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_go_online", annotations={"destructiveHint": False})
async def go_online(device_name: str = "", dry_run: bool = False) -> str:
    """连接到 PLC（建立在线连接）

    Args:
        device_name: PLC 设备名称（默认自动选择）
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "DeviceName": device_name}
    if dry_run:
        return _dry_run_msg("go-online", params)
    result = _run_tiaworker("go-online", params)
    if result.get("success"):
        return f"✅ 已连接到 PLC"
    return _format_result(False, error=result.get("error", "连接失败"))


@mcp.tool(name="plc_go_offline", annotations={"destructiveHint": False})
async def go_offline(device_name: str = "", dry_run: bool = False) -> str:
    """断开与 PLC 的在线连接

    Args:
        device_name: PLC 设备名称（默认自动选择）
        dry_run: 预览模式，不实际执行
    """
    if err := _check_project(): return err
    params = {"ProjectPath": PROJECT_PATH, "DeviceName": device_name}
    if dry_run:
        return _dry_run_msg("go-offline", params)
    result = _run_tiaworker("go-offline", params)
    if result.get("success"):
        return f"✅ 已断开与 PLC 的连接"
    return _format_result(False, error=result.get("error", "断开失败"))
