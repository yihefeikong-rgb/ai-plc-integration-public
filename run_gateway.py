"""阶段2 边缘网关启动脚本（Token 优化版）"""
import sys, json, asyncio
from pathlib import Path
from datetime import datetime, timezone

PROJECT = Path(__file__).parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "edge-gateway" / "src"))

from pymodbus.client import ModbusTcpClient
from config.settings import settings
from safety.audit import audit
from ai_client import ai


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


TAG_CONFIG = [
    {"tag": "coil.0", "protocol": "modbus", "name": "Start"},
    {"tag": "coil.1", "protocol": "modbus", "name": "Motor"},
    {"tag": "register.0", "protocol": "modbus", "name": "Temp",
     "threshold": {"min": 0, "max": 120, "delta": 5}},
    {"tag": "register.1", "protocol": "modbus", "name": "Speed",
     "threshold": {"min": 0, "max": 3000, "delta": 50}},
    {"tag": "input.0", "protocol": "modbus", "name": "LimitSW"},
]


def _has_change(tag: str, value, prev) -> bool:
    if value is None:
        return False
    if prev is None:
        return True
    cfg = next((t for t in TAG_CONFIG if t["tag"] == tag), {})
    delta = cfg.get("threshold", {}).get("delta", 0)
    if delta and abs(value - prev) >= delta:
        return True
    return bool(value != prev)


def _is_abnormal(tag: str, value) -> bool:
    if value is None:
        return False
    cfg = next((t for t in TAG_CONFIG if t["tag"] == tag), {})
    limits = cfg.get("threshold", {})
    if not limits:
        return False
    return value < limits["min"] or value > limits["max"]


async def main():
    interval = 30
    prev_values = {}

    print(f"[Gateway] 阶段2 边缘网关启动 | 间隔 {interval}s | 标签 {len(TAG_CONFIG)}")
    print(f"[Gateway] Modbus: {settings.modbus_host}:{settings.modbus_port}")
    print(f"[Gateway] InfluxDB: {settings.influxdb_url}")
    print(f"[Gateway] Token 优化: 变化检测+本地阈值+降频")

    try:
        from influxdb_client import InfluxDBClient, Point
        from influxdb_client.client.write_api import SYNCHRONOUS
        influx = InfluxDBClient(
            url=settings.influxdb_url, token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        write_api = influx.write_api(write_options=SYNCHRONOUS)
        print("[Gateway] InfluxDB 已连接")
    except Exception as e:
        influx = None
        print(f"[Gateway] InfluxDB 不可用: {e}")

    while True:
        try:
            data = []
            for cfg in TAG_CONFIG:
                try:
                    r = modbus_read(cfg["tag"])
                    data.append({"tag": cfg["tag"], "name": cfg["name"],
                                 "value": r.get("value"), "status": "ok"})
                except Exception as e:
                    data.append({"tag": cfg["tag"], "name": cfg["name"],
                                 "status": "error", "error": str(e)})

            normal = [d for d in data if d["status"] == "ok"]
            if influx:
                for d in normal:
                    if d.get("value") is not None:
                        p = Point("plc_metrics").tag("tag_name", d["tag"]) \
                            .field("value", float(d["value"])) \
                            .time(datetime.now(timezone.utc))
                        write_api.write(bucket=settings.influxdb_bucket, record=p)

            ok_n = len(normal)
            vals = {d['tag']: d['value'] for d in normal}
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {ok_n}/{len(data)} OK | {vals}")

            changed = []
            for d in normal:
                tag, v = d["tag"], d["value"]
                if _has_change(tag, v, prev_values.get(tag)):
                    changed.append(d)
                prev_values[tag] = v

            abnormal = [d for d in normal if _is_abnormal(d["tag"], d["value"])]

            if not changed and not abnormal:
                print("---")
                await asyncio.sleep(interval)
                continue

            analysis = ai.analyze_data(abnormal if abnormal else changed[:5])
            print(f"[AI] {analysis[:100]}...")

            try:
                decision = json.loads(ai.decide_control(
                    analysis, [t['tag'] for t in TAG_CONFIG]))
                if decision.get("action") == "write":
                    target = decision["target"]
                    value = decision["value"]
                    print(f"[决策] {target} = {value} | {decision.get('reason', '')}")
                    audit.log("ai_decision", target, str(value),
                              operator="ai", detail=decision.get("reason", ""))
            except (json.JSONDecodeError, Exception):
                pass

            print("---")
        except Exception as e:
            print(f"[Gateway] 错误: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Gateway] 已停止")
