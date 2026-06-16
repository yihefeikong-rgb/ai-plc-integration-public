# 阶段 2：AI 控制闭环

> 目标：AI 根据 PLC 数据做实时决策，回写控制指令，形成"采集→分析→决策→执行→审计"的完整闭环。
> 这是系统从"只读监控"升级到"主动控制"的关键阶段。

---

## 📦 架构概览

```
PLC 数据 (S7 协议 / Modbus / OPC UA)
  ↓ 每 30 秒采集（通过 S7Adapter / Modbus Adapter）
┌──────────────────────────────────────────────────┐
│            边缘网关控制循环 (edge-gateway/src/)     │
│                                                    │
│  1. 采集所有标签数据                                │
│  2. 写入 InfluxDB 时序库                            │
│  3. 变化检测 ← 值没变就跳过，省 Token                │
│  4. 本地阈值 ← 不超限就跳过，省 Token                │
│  5. AI 分析 (DeepSeek)                              │
│  6. AI 决策 (写/等待/告警)                           │
│  7. 安全校验 (safety/validator.py)                   │
│  8. 执行写入 → 审计日志 (mcp_common/audit.py)       │
└──────────────────────────────────────────────────┘
  ↓
plc-mcp-bridge S7Adapter / tools_s7.py 写入 PLC
```

---

## ✅ 已完成组件

### 1. AI 控制循环

**位置:** `edge-gateway/src/app.py`（EdgeGateway 类）、`run_gateway.py`（启动入口）

核心逻辑在 `EdgeGateway` 类中。每 30 秒执行一次：

```python
# 简化伪代码
loop:
    data = await scan_once(read_func)       # 采集所有标签
    self._write_influx(data)                # 写入 InfluxDB
    changed = [d for d in data if           # 变化检测
               self._has_significant_change(d)]
    abnormal = [d for d in data if          # 本地阈值
                self._is_out_of_bounds(d)]
    if not changed and not abnormal:
        sleep(30); continue                 # 没变化就不调 AI
    analysis = ai.analyze_data(abnormal)    # AI 分析
    decision = ai.decide_control(analysis)  # AI 决策
    if decision.action == "write":
        audit.log(...)                      # 审计记录
```

**启动方式：**
```bash
# 直接运行
python run_gateway.py

# 或作为模块
python -m edge-gateway.src.app

# 或用 Docker
docker compose up -d edge-gateway
```

---

### 2. Token 优化三层

| 层级 | 机制 | 效果 |
|:----:|:-----|:----:|
| 🔹 **变化检测** | 值变化超过 `delta` 才触发 AI | 节省 ~70% 调用 |
| 🔹 **本地阈值** | 值超出 `min`/`max` 范围才走 LLM | 进一步过滤噪声 |
| 🔹 **降频采集** | 30 秒固定间隔 | 避免高频轮询 |

**阈值配置示例（`edge-gateway/config/tags.json`）：**
```json
{
  "tag": "register.0",
  "protocol": "modbus",
  "name": "Temperature",
  "threshold": {
    "min": 0,
    "max": 120,
    "delta": 5
  }
}
```

三种字段的含义：
| 字段 | 用途 | 说明 |
|:----|:-----|:------|
| `delta` | 变化检测 | 值变化 ≥ `delta` 才算"显著变化"，触发 AI 分析 |
| `min` / `max` | 本地阈值 | 值超出此范围直接触发 AI 告警，不需要变化 |
| 无阈值 | 被动采集 | 只有值变化时才触发 AI，不主动告警 |

---

### 3. AI 决策客户端

**位置:** `edge-gateway/src/ai_client.py`

封装 DeepSeek API，按任务复杂度分流：

```python
class AIClient:
    def analyze_data(tags, context) → str
    def decide_control(situation, available_tags) → str (JSON)
```

| 方法 | 模型 | 用途 |
|------|:----:|------|
| `analyze_data()` | `deepseek-chat` (0.3 temp) | 分析数据状态 |
| `decide_control()` | `deepseek-chat` (0.1 temp) | 生成 JSON 决策 |

`decide_control()` 输出格式：
```json
{"action": "write", "target": "coil.1", "value": 1, "reason": "温度正常，启动电机"}
{"action": "wait", "target": "", "value": null, "reason": "一切正常，无需操作"}
{"action": "alert", "target": "", "value": null, "reason": "温度异常，建议检查"}
```

安全规则硬编码在 Prompt 中：
- ❌ 绝不操作急停、安全回路标签
- ❌ 值变化不超过当前值的 50%
- ❓ 不确定时返回 `action: "alert"`（安全优先）

---

### 4. 安全写入校验

**位置:** `safety/validator.py`

每次写入前都会经过多层安全校验：

```python
def validate(tag_name, value, current_value) → ValidationResult
```

| 校验层级 | 触发条件 | 结果 |
|:---------|:---------|:-----|
| 急停禁用 | 标签名匹配 `ESTOP` / `EMERGENCY` / `SAFETY` | ❌ 拦截 |
| 熔断保护 | 连续 ≥ 3 次异常写入 | ❌ 熔断 |
| 值范围 | 绝对值 ≥ 1,000,000 | ❌ 拦截 |
| 值跳变 | 新值相对旧值变化 ≥ 10x | ❌ 拦截 |
| 需确认 | 标签匹配 `MOTOR` / `PUMP` / `VALVE` 等 | ⚠️ 标记 needs_confirmation |

**可配置规则（`safety/interlock-rules.yml`）：**
```yaml
write_rules:
  - target: "DB1.MotorSpeed"
    max_value: 3000
    min_value: 0
    require_bits: ["DB1.SafetyOK", "DB1.EmergencyStopOff"]

  - target: "DB1.HeaterPower"
    max_value: 100
    require_bits: ["DB1.TemperatureSensorOK"]
    cooldown_seconds: 5
```

---

### 5. 链式哈希审计日志

**位置:** `safety/audit.py`

所有控制操作都记录到不可篡改的审计日志：

```
日志行 1: {"action":"write", "target":"coil.1", "value":"1", hash="a1b2..."}
日志行 2: {"action":"write", "target":"register.0", "value":"50",
            "prev_hash":"a1b2...", hash="c3d4..."}
日志行 3: ...
```

| 特性 | 说明 |
|:----|:------|
| 链式哈希 | 每行包含前一行 hash，篡改任何一行都会破坏链 |
| 追加写入 | 只追加模式，历史不可覆盖 |
| 自动校验 | `audit.verify()` 扫描全链检测篡改 |
| 保留 1 年 | 每条日志包含 UTC 时间戳 + 操作信息 |

```python
from safety.audit import audit

# 记录操作
audit.log("write", "DB1.Motor", "1500", operator="ai-agent")

# 验证日志完整性
assert audit.verify()  # 返回 False 则表示被篡改
```

---

### 6. 标签配置

**位置:** `edge-gateway/config/tags.json`

定义了网关采集的所有标签，包含协议、名称、阈值：

| 字段 | 类型 | 必填 | 说明 |
|:----|:----|:----:|:-----|
| `tag` | string | ✅ | PLC 标签地址（`coil.0`, `register.1`, `input.0`） |
| `protocol` | string | ✅ | 协议类型（`modbus`, `opcua`） |
| `name` | string | ✅ | 可读名称（`Temperature`, `Motor Run`） |
| `threshold.min` | number | 否 | 最小值阈值 |
| `threshold.max` | number | 否 | 最大值阈值 |
| `threshold.delta` | number | 否 | 变化检测灵敏度 |

---

## 🚀 快速启动

### 前置条件

```bash
# 1. 环境变量
cp .env.example .env
# 编辑 .env, 填入 DEEPSEEK_API_KEY
# 默认 INFLUXDB_PASSWORD=plc-admin-2024, INFLUXDB_TOKEN=plc-dev-token-2024

# 2. 启动 InfluxDB + Grafana
docker compose --profile monitoring up -d

# 3. 启动网关（S7 模式，需要 PLCSIM 在线）
python -m edge_gateway.src.app

# 或 Modbus 模式
python -m edge_gateway.src.app --modbus
```

### 验证运行

```
[Gateway] 启动 | 间隔 30s | 标签 4 | InfluxDB: ON | 写入: 有
[Gateway] Token 优化: 变化检测+本地阈值+降频
[15:00:00] 采集 4/4 OK | 标签: Motor=1, Speed=1500, Temp=25.5
---
[AI] 分析 | 变化 1 异常 0 | 温度正常范围...
```

### 验证脚本（无需 PLCSIM）

```bash
# 运行全部检查（18 项）
python verify_phase2.py

# 单项检查
python verify_phase2.py safety    # 安全模块
python verify_phase2.py gateway   # EdgeGateway mock 模式
python verify_phase2.py s7        # S7 适配器（需要 --all 进行真实连接）
```

---

## 🧪 测试

```bash
# Safety 测试（21 项）
python -m pytest tests/test_safety_audit.py tests/test_safety_validator.py -v

# PLC MCP Bridge 测试（35 项）
python -m pytest mcp-servers/plc-mcp-bridge/tests/ -v

# Phase 2 验证（18 项，无外部依赖）
python verify_phase2.py
```

---

## ⚠️ 安全红线

1. ❌ **禁止 AI 直接操作急停回路** — 只能读取状态，不能写入
2. ❌ **禁止 AI 修改安全 PLC（F-CPU）的任何参数**
3. ❌ **禁止 AI 在生产环境无确认写入** — 影子仿真验证是前置条件
4. ⚡ **异常值自动熔断** — 连续 3 次写入超出合理范围，自动禁用 AI 控制
5. 📝 **审计日志不可篡改** — 链式哈希保证完整性

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `edge-gateway/src/app.py` | EdgeGateway 控制循环主类（S7/Modbus 双协议） |
| `edge-gateway/src/ai_client.py` | DeepSeek API 封装 |
| `edge-gateway/config/tags.json` | 标签配置（含阈值） |
| `mcp-servers/plc-mcp-bridge/s7_adapter.py` | S7 协议适配器（snap7 封装） |
| `mcp-servers/plc-mcp-bridge/tools_s7.py` | S7 工具 MCP 注册（4 工具） |
| `safety/validator.py` | 写入安全校验器 |
| `safety/interlock-rules.yml` | 互锁规则配置 |
| `mcp_common/audit.py` | 链式哈希审计日志 |
| `mcp_common/config.py` | 统一配置加载器（替代原 config/settings.py） |
| `docker-compose.yml` | InfluxDB + Grafana + OpenPLC |
| `verify_phase2.py` | Phase 2 端到端验证脚本（18 项检查） |

---

## 🔜 后续可选扩展

以下内容不属于核心控制闭环，可按需添加：

| 功能 | 说明 |
|:----|:------|
| Grafana 仪表盘 | InfluxDB 时序数据可视化（之前已移除，需要时恢复） |
| Ollama 本地 LLM | 本地部署 Qwen3，数据不出厂（需 GPU 或 CPU 推理） |
| OPC UA 写回验证 | 在 OPC UA MCP 端跑完整的写回测试 |
| 三菱 MC 协议 | 接入三菱 FX5U/Q 系列 PLC |
