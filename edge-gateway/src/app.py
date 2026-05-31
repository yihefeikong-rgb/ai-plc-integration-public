"""
Edge Gateway — 阶段1+2 主程序（Token 优化版）
  - 变化检测：值没变不调 AI
  - 本地阈值：超限才走 LLM
  - 降频采集：30s 间隔
"""

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings
from safety.audit import audit
from .ai_client import ai

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

    def _load_tags(self) -> list[dict]:
        path = Path(__file__).parent.parent / "config" / "tags.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return [
            {"tag": "coil.0", "protocol": "modbus", "name": "Start"},
            {"tag": "coil.1", "protocol": "modbus", "name": "Motor"},
            {"tag": "register.0", "protocol": "modbus", "name": "Temp"},
            {"tag": "input.0", "protocol": "modbus", "name": "LimitSW"},
        ]

    def _has_significant_change(self, tag: str, value: float | int | None) -> bool:
        """值有显著变化？超过 delta 或从 None 变有值"""
        if value is None:
            return False
        prev = self._prev_values.get(tag)
        if prev is None:
            self._prev_values[tag] = value
            return True
        cfg = next((t for t in self.tag_config if t["tag"] == tag), {})
        delta = cfg.get("threshold", {}).get("delta", 0)
        if delta and abs(value - prev) >= delta:
            self._prev_values[tag] = value
            return True
        if value != prev:
            self._prev_values[tag] = value
            return True
        return False

    def _is_out_of_bounds(self, tag: str, value: float | int | None) -> bool:
        """值超出阈值范围？"""
        if value is None:
            return False
        cfg = next((t for t in self.tag_config if t["tag"] == tag), {})
        limits = cfg.get("threshold", {})
        if not limits:
            return False
        return value < limits["min"] or value > limits["max"]

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
            _write_api.write(bucket=settings.influxdb_bucket, record=p)

    async def ai_control_loop(self, data: list[dict]):
        normal = [d for d in data if d["status"] == "ok"]
        if not normal:
            return

        changed = [d for d in normal if self._has_significant_change(d["tag"], d["value"])]
        abnormal = [d for d in normal if self._is_out_of_bounds(d["tag"], d["value"])]

        if not changed and not abnormal:
            return

        analysis = ai.analyze_data(abnormal if abnormal else changed[:5])
        print(f"[AI] 分析 | 变化 {len(changed)} 异常 {len(abnormal)} | {analysis[:80]}...")

        if "建议" in analysis or "recommend" in analysis.lower():
            available = [t["tag"] for t in self.tag_config]
            try:
                decision = json.loads(ai.decide_control(analysis, available))
                if decision.get("action") == "write":
                    print(f"[决策] 写入 {decision['target']} = {decision['value']}")
                    print(f"[原因] {decision.get('reason', 'N/A')}")
                    audit.log("ai_decision", decision.get("target", ""),
                              str(decision.get("value")), operator="ai",
                              detail=decision.get("reason", ""))
            except json.JSONDecodeError:
                pass

    async def run(self, read_func):
        self.running = True
        print(f"[Gateway] 启动 | 间隔 {self.scan_interval}s | "
              f"标签 {len(self.tag_config)} | InfluxDB: {'ON' if HAS_INFLUX else 'OFF'}")
        print(f"[Gateway] Token 优化: 变化检测+本地阈值+降频")

        while self.running:
            try:
                data = await self.scan_once(read_func)
                self._write_influx(data)
                ok_n = sum(1 for d in data if d["status"] == "ok")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 采集 {ok_n}/{len(data)} OK")
                await self.ai_control_loop(data)
            except Exception as e:
                print(f"[Gateway] 错误: {e}")
            await asyncio.sleep(self.scan_interval)

    def stop(self):
        self.running = False


async def main():
    from pymodbus.client import ModbusTcpClient

    gw = EdgeGateway()

    def modbus_read(tag: str) -> dict:
        c = ModbusTcpClient(host=settings.modbus_host, port=settings.modbus_port)
        c.connect()
        parts = tag.split(".")
        typ, addr = parts[0], int(parts[1])
        if typ == "coil":
            rr = c.read_coils(addr, count=1, device_id=1)
            return {"value": rr.bits[0] if not rr.isError() else None}
        elif typ == "register":
            rr = c.read_holding_registers(addr, count=1, device_id=1)
            return {"value": rr.registers[0] if not rr.isError() else None}
        elif typ == "input":
            rr = c.read_discrete_inputs(addr, count=1, device_id=1)
            return {"value": rr.bits[0] if not rr.isError() else None}
        return {"value": None}

    try:
        await gw.run(modbus_read)
    except KeyboardInterrupt:
        gw.stop()
        print("[Gateway] 已停止")


if __name__ == "__main__":
    asyncio.run(main())
