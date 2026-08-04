"""硬件配置工具 — 设备拓扑、机架/插槽、I/O 映射"""
import time

from _helpers import mcp, _run_tiaworker, _format_result, _check_project, PROJECT_PATH

# 只读拓扑查询缓存：get-device-config / get-rack-slot 返回的设备/机架/插槽拓扑
# 在会话内相对稳定，按 (command, PROJECT_PATH) 缓存复用，避免重复调用时每次都
# 启动重量级 TiaWorker.exe 子进程（timeout=120）重复获取同一份数据。
_TOPOLOGY_TTL = 60  # 缓存有效期（秒），与 _helpers._PREVIEW_TTL 一致


class _TopologyCache:
    """带 TTL 的只读拓扑查询缓存，仅缓存成功结果"""

    def __init__(self, ttl: int = _TOPOLOGY_TTL):
        self._store: dict[tuple, tuple[float, dict]] = {}
        self._ttl = ttl

    def get(self, key: tuple) -> dict | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        timestamp, result = entry
        if time.time() - timestamp > self._ttl:
            del self._store[key]
            return None
        return result

    def put(self, key: tuple, result: dict) -> None:
        self._store[key] = (time.time(), result)


_topology_cache = _TopologyCache()


def _get_topology(command: str) -> dict:
    """获取只读设备拓扑数据：命中缓存直接复用，未命中才启动 TiaWorker.exe"""
    key = (command, PROJECT_PATH)
    if (cached := _topology_cache.get(key)) is not None:
        return cached
    result = _run_tiaworker(command, {"ProjectPath": PROJECT_PATH}, timeout=120)
    if result.get("success"):
        _topology_cache.put(key, result)
    return result


@mcp.tool(name="plc_get_device_config", annotations={"readOnlyHint": True})
async def get_device_config() -> str:
    """获取 TIA 项目中所有设备的硬件配置（机架/插槽结构）"""
    if err := _check_project(): return err
    result = _get_topology("get-device-config")
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
    result = _get_topology("get-rack-slot")
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
