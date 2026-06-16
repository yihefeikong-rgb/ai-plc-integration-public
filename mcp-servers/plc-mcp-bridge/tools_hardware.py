"""硬件配置工具 — 设备拓扑、机架/插槽、I/O 映射"""
from _helpers import mcp, _run_tiaworker, _format_result, _check_project, PROJECT_PATH


@mcp.tool(name="plc_get_device_config", annotations={"readOnlyHint": True})
async def get_device_config() -> str:
    """获取 TIA 项目中所有设备的硬件配置（机架/插槽结构）"""
    if err := _check_project(): return err
    result = _run_tiaworker("get-device-config", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        devices = d.get("devices", [])
        if devices:
            lines = [f"硬件配置 ({d.get('deviceCount', len(devices))} 台设备)："]
            for dev in devices:
                lines.append(f"\n  {dev['name']} ({dev['type']})")
                for item in dev.get("items", []):
                    indent = "  " * (item["depth"] + 1)
                    lines.append(f"{indent}|- {item['name']} [{item['type']}]")
            return "\n".join(lines)
        return "项目中无硬件设备"
    return _format_result(False, error=result.get("error", "查询失败"))


@mcp.tool(name="plc_get_rack_slot", annotations={"readOnlyHint": True})
async def get_rack_slot() -> str:
    """获取设备机架/插槽拓扑和 I/O 地址分配"""
    if err := _check_project(): return err
    result = _run_tiaworker("get-rack-slot", {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        d = result.get("data", {})
        devices = d.get("devices", [])
        if devices:
            lines = [f"机架/插槽拓扑 ({d.get('deviceCount', len(devices))} 台设备)："]
            for dev in devices:
                lines.append(f"\n  {dev['device']}")
                for slot in dev.get("slots", []):
                    indent = "  " * (slot["depth"] + 1)
                    lines.append(f"{indent}|- [{slot['type']}] {slot['name']}")
            return "\n".join(lines)
        return "项目中无设备"
    return _format_result(False, error=result.get("error", "查询失败"))
