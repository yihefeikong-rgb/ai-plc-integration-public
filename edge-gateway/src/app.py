"""
Edge Gateway — 阶段1+2 主程序（Token 优化版）
  - 变化检测：值没变不调 AI
  - 本地阈值：超限才走 LLM
  - 降频采集：30s 间隔
  - S7 协议读写 PLC（通过 plc-mcp-bridge 适配器）
  - 安全写入校验
"""

import json
import os
import asyncio
import inspect
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from mcp_common.config import env_config
from mcp_common.audit import audit
from mcp_common.control_target import get_control_target

settings = env_config()

# ── 导入 plc-mcp-bridge 的 S7 适配器 ──
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"))
from s7_adapter import S7Adapter  # noqa: E402
from safety.validator import validator as safety_validator
from src.ai_client import ai, parse_decision
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
except Exception as e:
    HAS_INFLUX = False
    logger.warning("[InfluxDB] 初始化失败，遥测降级为关闭: %s", e)


def _audit_ai_reject(raw_response: str) -> None:
    """记录 AI 决策未通过硬校验的审计条目（fail-closed，拒绝不留盲区）。"""
    try:
        raw_obj = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        raw_obj = {}
    try:
        audit.log(
            "write_rejected",
            str(raw_obj.get("target", "")) if isinstance(raw_obj, dict) else "",
            str(raw_obj.get("value", "")) if isinstance(raw_obj, dict) else "",
            operator="ai",
            success=False,
            detail="AI 决策输出未通过 parse_decision 硬校验，fail-closed 拒绝",
        )
    except Exception as e:
        logger.error("[审计] 决策拒绝记录失败: %s", e)


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
        points = []
        for d in data:
            if d["status"] != "ok" or d.get("value") is None:
                continue
            try:
                value = float(d["value"])
            except (TypeError, ValueError) as e:
                logger.warning("[InfluxDB] 丢弃不可转换数值 %s=%r: %s",
                               d.get("tag", "?"), d.get("value"), e)
                continue
            points.append(
                Point("plc_metrics")
                .tag("tag_name", d["tag"])
                .tag("protocol", d.get("protocol", ""))
                .field("value", value)
                .time(datetime.now(timezone.utc))
            )
        if not points:
            return
        try:
            # 单批写入，避免逐 tag 串行阻塞 HTTP POST
            _write_api.write(bucket=settings.influxdb_bucket, record=points)
        except Exception as e:
            logger.error("[InfluxDB] 批量写入失败 (%d 点): %s", len(points), e)

    async def ai_control_loop(self, data: list[dict], read_func=None, write_func=None):
        if self._ai_fused:
            return

        normal = [d for d in data if d["status"] == "ok"]
        if not normal:
            return

        changed = [d for d in normal if self._has_significant_change(d["tag"], d["value"])]
        abnormal = [d for d in normal if self._is_out_of_bounds(d["tag"], d["value"])]

        if not changed and not abnormal:
            return

        try:
            analysis = await ai.analyze_data(abnormal if abnormal else changed[:5])
        except Exception as e:
            self._ai_json_fail_count += 1
            logger.error("[AI] 分析调用异常(连续 %d 次): %s", self._ai_json_fail_count, e)
            if self._ai_json_fail_count >= 3:
                logger.critical("[AI] 连续 %d 次 AI 调用失败，触发熔断",
                                self._ai_json_fail_count)
                self._ai_fused = True
            return
        print(f"[AI] 分析 | 变化 {len(changed)} 异常 {len(abnormal)} | {analysis[:80]}...")

        # 有变化或异常就走 AI 决策
        if changed or abnormal:
            available = [t["tag"] for t in self.tag_config]
            # 当前值快照：parse_decision 的 >50% 跳变保护依赖它（代码强制）
            current_values = {d["tag"]: d.get("value") for d in data}
            try:
                raw_response = await ai.decide_control(analysis, available)
                decision = parse_decision(raw_response, available, current_values)
                # decide_control 会把未通过硬校验的输出转成固定 alert JSON
                # （ai_client.py 兜底），识别该签名让『连续失败熔断』真正生效
                if (decision is not None and decision.get("action") == "alert"
                        and decision.get("target") == ""
                        and decision.get("value") is None
                        and "已转为 alert" in str(decision.get("reason", ""))):
                    decision = None
                if decision is None:
                    self._ai_json_fail_count += 1
                    logger.error("[AI] 决策输出未通过硬校验(连续 %d 次): %.200s",
                                 self._ai_json_fail_count, raw_response)
                    _audit_ai_reject(raw_response)
                    if self._ai_json_fail_count >= 3:
                        logger.critical("[AI] 连续 %d 次 AI 决策失败，触发熔断",
                                        self._ai_json_fail_count)
                        self._ai_fused = True
                    return
                self._ai_json_fail_count = 0  # 决策通过硬校验，重置熔断计数
                if decision.get("action") == "write":
                    await self._safe_write(decision, available, data,
                                           read_func, write_func)
            except Exception as e:
                # 与 analyze_data 的异常计数逻辑一致：决策调用异常也计入熔断
                self._ai_json_fail_count += 1
                logger.error("[AI] 决策调用异常(连续 %d 次): %s",
                             self._ai_json_fail_count, e)
                if self._ai_json_fail_count >= 3:
                    logger.critical("[AI] 连续 %d 次 AI 决策失败，触发熔断",
                                    self._ai_json_fail_count)
                    self._ai_fused = True

    async def _safe_write(self, decision: dict, available: list[str], data: list[dict],
                          read_func=None, write_func=None) -> None:
        """AI 写 PLC 的 fail-closed 安全路径。

        链路: 白名单 → resolve_s7_write_address(地址→语义) → 读当前值
              → validate(语义名+current_value) → 审计意图先行 → 写入 → 如实审计
        """
        target = decision.get("target")
        value = decision.get("value")
        reason = decision.get("reason", "")
        if not isinstance(target, str) or not target:
            logger.error("[安全] AI 决策缺少目标地址，拒绝写入")
            return

        def _audit_reject(msg: str) -> None:
            print(f"[安全] 阻断写入 {target} = {value}: {msg}")
            try:
                audit.log("write_rejected", target, str(value), operator="ai",
                          success=False, detail=msg)
            except Exception as e:
                logger.error("[审计] 拒绝记录失败: %s", e)

        # 1. 白名单：目标必须是扫描标签之一（原始地址精确匹配）
        if target not in available:
            _audit_reject(f"目标 {target} 不在可写标签白名单内")
            return

        # 2. 原始地址必须映射到安全语义（interlock-rules.yml 白名单）
        try:
            mapping = safety_validator.resolve_s7_write_address(target)
        except Exception as e:
            # InterlockConfigError：互锁规则/地址映射未成功加载（fail-closed），
            # 与"正常未映射地址"区分并走审计拒绝路径，不留无痕盲区
            _audit_reject(f"互锁规则未加载，拒绝解析写入地址: {e}")
            return
        if not mapping:
            _audit_reject(f"未映射的允许写入地址: {target}")
            return
        semantic_target = mapping.get("target")
        if not isinstance(semantic_target, str) or not semantic_target:
            _audit_reject(f"地址映射缺少语义目标: {target}")
            return

        # 3. 读取当前值（值跳变保护，validate 的 current_value 不能为 None）
        current_value = None
        entry = next((d for d in data if d.get("tag") == target), None)
        if entry is not None:
            current_value = entry.get("value")
        if read_func is not None:
            try:
                r = await read_func(target)
                if r.get("status", "ok") == "ok":
                    current_value = r.get("value")
            except Exception as e:
                logger.warning("[安全] 当前值读取失败 %s: %s", target, e)

        # 4. 互锁校验（用语义名而非原始地址，require_bits/范围/确认模式才能生效）
        result = safety_validator.validate(semantic_target, value,
                                           current_value=current_value)
        if not result.allowed:
            _audit_reject(result.reason)
            return
        if result.needs_confirmation:
            _audit_reject(f"需要人工确认: {result.reason}（网关无确认通道，fail-closed 阻断）")
            return

        # 5. 无写入通道也拒绝（不做“已执行”伪装）
        if write_func is None:
            _audit_reject("网关未配置写入通道，拒绝 AI 写请求")
            return

        # 6. 审计意图先行：记录失败即拒绝写入（fail-closed）
        try:
            audit.begin_control_operation(
                "edge_gateway.ai_write", target, "ai",
                {"value": str(value), "semantic_target": semantic_target},
            )
        except Exception as e:
            logger.error("[审计] 意图记录失败，拒绝写入 %s = %s: %s", target, value, e)
            return

        # 7. 执行写入
        print(f"[决策] 写入 {target} = {value}（{semantic_target}）")
        print(f"[原因] {reason or 'N/A'}")
        write_success = False
        write_error = ""
        try:
            result = write_func(target, value)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, str) and ("❌" in result or "🚫" in result):
                raise RuntimeError(result)
            write_success = True
            print(f"[写入] {result}")
        except Exception as e:
            write_error = str(e)
            logger.error("[写入] 失败 %s = %s: %s", target, value, e)

        # 8. 如实审计结果（写失败也以 success=False 落链，不伪造成功）
        detail_parts = []
        if reason:
            detail_parts.append(reason)
        if semantic_target:
            detail_parts.append(f"semantic_target={semantic_target}")
        if write_error:
            detail_parts.append(f"写入错误: {write_error}")
        try:
            audit.log("ai_decision", target, str(value), operator="ai",
                      success=write_success, detail="; ".join(detail_parts))
        except Exception as e:
            logger.error("[审计] 决策记录失败: %s", e)

    async def run(self, read_func, write_func=None):
        self.running = True
        has_write = "有" if write_func else "无"
        print(f"[Gateway] 启动 | 间隔 {self.scan_interval}s | "
              f"标签 {len(self.tag_config)} | InfluxDB: {'ON' if HAS_INFLUX else 'OFF'} | "
              f"写入: {has_write}")
        print(f"[Gateway] Token 优化: 变化检测+本地阈值+降频")

        consecutive_failures = 0
        while self.running:
            try:
                data = await self.scan_once(read_func)
                # 同步 InfluxDB 批量写入放入线程，避免阻塞事件循环
                await asyncio.to_thread(self._write_influx, data)
                ok_n = sum(1 for d in data if d["status"] == "ok")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 采集 {ok_n}/{len(data)} OK")
                await self.ai_control_loop(data, read_func, write_func)
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.error("[Gateway] 错误: %s", e, exc_info=True)
            # 持续失败时指数级退避，避免 30s 空转刷屏且错误无追溯
            backoff = min(consecutive_failures, 5) * self.scan_interval
            await asyncio.sleep(backoff if consecutive_failures else self.scan_interval)

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
        try:
            connected = await modbus_client.connect()
        except Exception as e:
            logger.error("[Modbus] 连接异常: %s", e)
            connected = False
        if not connected:
            logger.critical("[Modbus] 连接失败，网关拒绝启动（fail-closed）")
            return

        async def modbus_read(tag: str) -> dict:
            if not modbus_client.connected:
                try:
                    await modbus_client.connect()
                except Exception as e:
                    return {"status": "error", "error": f"Modbus 重连失败: {e}"}
            parts = tag.split(".")
            if len(parts) != 2:
                return {"status": "error", "error": f"无效 Modbus 标签: {tag}"}
            try:
                addr = int(parts[1])
            except ValueError:
                return {"status": "error", "error": f"无效 Modbus 地址: {tag}"}
            typ = parts[0]
            if typ == "coil":
                rr = await modbus_client.read_coils(addr, count=1, slave=1)
                if rr.isError():
                    return {"status": "error", "error": f"Modbus 读线圈失败: {tag}"}
                return {"value": rr.bits[0]}
            elif typ == "register":
                rr = await modbus_client.read_holding_registers(addr, count=1, slave=1)
                if rr.isError():
                    return {"status": "error", "error": f"Modbus 读寄存器失败: {tag}"}
                return {"value": rr.registers[0]}
            elif typ == "input":
                rr = await modbus_client.read_discrete_inputs(addr, count=1, slave=1)
                if rr.isError():
                    return {"status": "error", "error": f"Modbus 读离散输入失败: {tag}"}
                return {"value": rr.bits[0]}
            return {"status": "error", "error": f"未知 Modbus 标签类型: {typ}"}

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
        ip = get_control_target().plc_ip
        # env_config() 的 default_env 不含 S7_RACK/S7_SLOT，Config.get 恒回退默认；
        # 直接读环境变量（.env 已由 env_config() 载入 os.environ），让配置真正生效
        rack = int(os.getenv("S7_RACK", "0"))
        slot = int(os.getenv("S7_SLOT", "1"))
        logger.info("%s", s7.connect(ip, rack, slot))
        if not s7.is_connected:
            logger.critical("[Gateway] S7 连接失败，网关拒绝启动（fail-closed）")
            return

        # 注册 bit_reader：require_bits 互锁（急停/安全回路）需独立读位
        _bit_warned: set[str] = set()

        def _read_safety_bit(address: str):
            if not s7.is_connected:
                return None
            try:
                return bool(s7.read_address(address))
            except ValueError as e:
                # S7Adapter 只支持数字地址（M0.0/MB/MW/MD/DBn.MWx），
                # interlock-rules.yml 若写符号位地址（如 DB1.SafetyOK）无法读取，
                # 属配置不匹配：fail-closed 返回 None（拒绝写入）并对每个地址告警一次
                if address not in _bit_warned:
                    _bit_warned.add(address)
                    logger.error(
                        "[安全] 互锁位地址 %s 不是 S7Adapter 可读的数字地址"
                        "（支持 M0.0/MB/MW/MD/DBn.MWx）：%s。require_bits 将恒"
                        "判失败（fail-closed），请改用数字位地址或 OPC UA 位读取",
                        address, e)
                return None
            except Exception:
                return None

        safety_validator.set_bit_reader(_read_safety_bit)

        async def s7_read(tag: str) -> dict:
            try:
                # snap7 同步读放入线程，避免阻塞事件循环
                val = await asyncio.to_thread(s7.read_address, tag)
                return {"value": val if val is not None else None}
            except Exception as e:
                logger.error("[S7] 读取失败 %s: %s", tag, e)
                return {"status": "error", "error": f"读取失败 {tag}"}

        async def s7_write(address: str, value) -> str:
            result = await asyncio.to_thread(s7.write_address, address, value)
            if isinstance(result, str) and ("❌" in result or "🚫" in result):
                raise RuntimeError(result)
            return result

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
