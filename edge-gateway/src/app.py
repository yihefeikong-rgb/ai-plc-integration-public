"""
Edge Gateway — 阶段1+2 主程序（Token 优化版）
  - 变化检测：值没变不调 AI
  - 本地阈值：超限才走 LLM
  - 降频采集：30s 间隔
  - S7 协议读写 PLC（通过 plc-mcp-bridge 适配器）
  - 安全写入校验
"""

import json
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from mcp_common.config import env_config
from mcp_common.audit import audit

settings = env_config()

# ── 导入 plc-mcp-bridge 的 S7 适配器 ──
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
from s7_adapter import S7Adapter  # noqa: E402
from safety.validator import validator as safety_validator
from src.ai_client import ai
from src.change_detector import has_significant_change, is_out_of_bounds

try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    _influx = InfluxDBClient(
        url=settings.influxdb_url, token=settings.influxdb_token,
        org=settings.influxdb_org,
    )
    _write_api = _influx.write_api(write_options=SYNCHRONOUS)
    HAS_INFLUX = True
except Exception:
    HAS_INFLUX = False


class EdgeGateway:
    def __init__(self):
        self.scan_interval = 30
        self.running = False
        self.tag_config = self._load_tags()
        self._prev_values: dict[str, float | int | None] = {}
        self._ai_json_fail_count: int = 0
        self._ai_fused: bool = False

    def _load_tags(self) -> list[dict]:
        config_dir = Path(__file__).parent.parent / "config"
        # 尝试加载 S7 配置（Phase 2 默认）
        s7_path = config_dir / "tags_s7.json"
        if s7_path.exists():
            return json.loads(s7_path.read_text(encoding="utf-8"))
        # 回退到 Modbus 配置
        modbus_path = config_dir / "tags.json"
        if modbus_path.exists():
            return json.loads(modbus_path.read_text(encoding="utf-8"))
        # 默认 S7 地址
        return [
            {"tag": "M0.0", "protocol": "s7", "name": "Start"},
            {"tag": "M0.1", "protocol": "s7", "name": "Motor"},
            {"tag": "MW10", "protocol": "s7", "name": "Temp",
             "threshold": {"min": 0, "max": 120, "delta": 5}},
            {"tag": "MW12", "protocol": "s7", "name": "Speed",
             "threshold": {"min": 0, "max": 3000, "delta": 50}},
        ]

    def _has_significant_change(self, tag: str, value: float | int | None) -> bool:
        result = has_significant_change(tag, value, self._prev_values, self.tag_config)
        if result and value is not None:
            self._prev_values[tag] = value
        return result

    def _is_out_of_bounds(self, tag: str, value: float | int | None) -> bool:
        return is_out_of_bounds(tag, value, self.tag_config)

    async def scan_once(self, read_func) -> list[dict]:
        results = []
        for cfg in self.tag_config:
            try:
                r = await read_func(cfg["tag"])
                results.append({
                    "tag": cfg["tag"], "name": cfg["name"],
                    "protocol": cfg["protocol"], "value": r.get("value"),
                    "status": r.get("status", "ok"),
                })
            except Exception as e:
                results.append({"tag": cfg["tag"], "name": cfg["name"],
                                "status": "error", "error": str(e)})
        return results

    def _write_influx(self, data: list[dict]):
        if not HAS_INFLUX:
            return
        for d in data:
            if d["status"] != "ok" or d.get("value") is None:
                continue
            p = Point("plc_metrics") \
                .tag("tag_name", d["tag"]) \
                .tag("protocol", d.get("protocol", "")) \
                .field("value", float(d["value"])) \
                .time(datetime.now(timezone.utc))
            try:
                _write_api.write(bucket=settings.influxdb_bucket, record=p)
            except Exception as e:
                logger.error("[InfluxDB] 写入失败 tag=%s: %s", d["tag"], e)

    async def ai_control_loop(self, data: list[dict], write_func=None):
        if self._ai_fused:
            return

        normal = [d for d in data if d["status"] == "ok"]
        if not normal:
            return

        changed = [d for d in normal if self._has_significant_change(d["tag"], d["value"])]
        abnormal = [d for d in normal if self._is_out_of_bounds(d["tag"], d["value"])]

        if not changed and not abnormal:
            return

        analysis = await ai.analyze_data(abnormal if abnormal else changed[:5])
        print(f"[AI] 分析 | 变化 {len(changed)} 异常 {len(abnormal)} | {analysis[:80]}...")

        # 有变化或异常就走 AI 决策
        if changed or abnormal:
            available = [t["tag"] for t in self.tag_config]
            try:
                raw_response = await ai.decide_control(analysis, available)
                decision = json.loads(raw_response)
                self._ai_json_fail_count = 0  # 解析成功，重置熔断计数
                if decision.get("action") == "write":
                    result = safety_validator.validate(decision["target"], decision["value"])
                    if not result.allowed:
                        print(f"[安全] 阻断写入 {decision['target']} = {decision['value']}: {result.reason}")
                        audit.log("blocked", decision.get("target", ""),
                                  str(decision.get("value")), operator="ai",
                                  detail=result.reason)
                    else:
                        if result.needs_confirmation:
                            print(f"[安全] 警告: {decision['target']} 需要人工确认")
                        print(f"[决策] 写入 {decision['target']} = {decision['value']}")
                        print(f"[原因] {decision.get('reason', 'N/A')}")
                        # 执行真实写入
                        if write_func:
                            try:
                                write_result = write_func(decision["target"], decision["value"])
                                print(f"[写入] {write_result}")
                            except Exception as e:
                                print(f"[写入] 失败: {e}")
                        audit.log("ai_decision", decision.get("target", ""),
                                  str(decision.get("value")), operator="ai",
                                  detail=decision.get("reason", ""))
            except json.JSONDecodeError:
                self._ai_json_fail_count += 1
                logger.error("[AI] 非 JSON 响应(连续 %d 次): %s",
                             self._ai_json_fail_count, raw_response[:200])
                if self._ai_json_fail_count >= 3:
                    logger.critical("[AI] 连续 %d 次非 JSON 响应，触发熔断",
                                    self._ai_json_fail_count)
                    self._ai_fused = True
            except Exception as e:
                logger.error("[AI] 决策调用异常: %s", e)

    async def run(self, read_func, write_func=None):
        self.running = True
        has_write = "有" if write_func else "无"
        print(f"[Gateway] 启动 | 间隔 {self.scan_interval}s | "
              f"标签 {len(self.tag_config)} | InfluxDB: {'ON' if HAS_INFLUX else 'OFF'} | "
              f"写入: {has_write}")
        print(f"[Gateway] Token 优化: 变化检测+本地阈值+降频")

        while self.running:
            try:
                data = await self.scan_once(read_func)
                self._write_influx(data)
                ok_n = sum(1 for d in data if d["status"] == "ok")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 采集 {ok_n}/{len(data)} OK")
                await self.ai_control_loop(data, write_func)
            except Exception as e:
                print(f"[Gateway] 错误: {e}")
            await asyncio.sleep(self.scan_interval)

    def stop(self):
        self.running = False


async def main(protocol: str = "s7"):
    """启动 Edge Gateway

    Args:
        protocol: 通信协议 "s7"（默认）或 "modbus"
    """
    gw = EdgeGateway()

    if protocol == "modbus":
        from pymodbus.client import AsyncModbusTcpClient

        modbus_client = AsyncModbusTcpClient(
            host=settings.modbus_host,
            port=int(settings.modbus_port),
        )
        await modbus_client.connect()

        async def modbus_read(tag: str) -> dict:
            if not modbus_client.connected:
                await modbus_client.connect()
            parts = tag.split(".")
            typ, addr = parts[0], int(parts[1])
            if typ == "coil":
                rr = await modbus_client.read_coils(addr, count=1, slave=1)
                return {"value": rr.bits[0] if not rr.isError() else None}
            elif typ == "register":
                rr = await modbus_client.read_holding_registers(addr, count=1, slave=1)
                return {"value": rr.registers[0] if not rr.isError() else None}
            elif typ == "input":
                rr = await modbus_client.read_discrete_inputs(addr, count=1, slave=1)
                return {"value": rr.bits[0] if not rr.isError() else None}
            return {"value": None}

        try:
            await gw.run(modbus_read)
        except KeyboardInterrupt:
            gw.stop()
        finally:
            modbus_client.close()
            print("[Gateway] 已停止")
    else:
        # S7 协议模式（默认）
        s7 = S7Adapter()
        ip = settings.get("s7_plc_ip", "192.168.0.110")
        rack = int(settings.get("s7_rack", "0"))
        slot = int(settings.get("s7_slot", "1"))
        print(s7.connect(ip, rack, slot))

        async def s7_read(tag: str) -> dict:
            try:
                val = s7.read_address(tag)
                return {"value": val if val is not None else None}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        def s7_write(address: str, value) -> str:
            return s7.write_address(address, value)

        try:
            await gw.run(s7_read, write_func=s7_write)
        except KeyboardInterrupt:
            gw.stop()
            print(s7.disconnect())
            print("[Gateway] 已停止")


if __name__ == "__main__":
    import sys as _sys
    proto = "s7"
    if "--modbus" in _sys.argv:
        proto = "modbus"
    asyncio.run(main(protocol=proto))
