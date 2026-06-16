# 阶段 1：运行态基础

> 目标：搭建边缘网关，让 AI 能通过自然语言实时读/写 PLC 数据（S7 协议 / OPC UA）。
> 这是整个系统的基础——先让 AI 能"看见"设备，才能谈后续的控制和工程态。

---

## 📦 架构概览

```
PLC 数据 (S7 协议 / OPC UA)
  ↓ S7Adapter (python-snap7)
┌─────────────────────────────────────────────────────┐
│  PLC MCP Bridge (mcp-servers/plc-mcp-bridge/)       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ tools_s7 │ │ blocks   │ │ tags     │ │ project││
│  │ 4工具    │ │ 11工具   │ │ 7工具    │ │ 13工具 ││
│  └────┬─────┘ └──────────┘ └──────────┘ └────────┘│
└───────┼──────────────────────────────────────────────┘
        │ MCP stdio
┌───────┴────────────────────────────────────────────┐
│  AI 层 (Claude Code / Cursor)                       │
│  通过 MCP 工具直接读写 PLC 变量                      │
└────────────────────────────────────────────────────┘
        │
┌───────┴────────────────────────────────────────────┐
│  EdgeGateway (edge-gateway/) — Phase 2             │
│  控制循环: 采集→分析→决策→写入→审计                │
└────────────────────────────────────────────────────┘
```

---

## ✅ 已完成组件

### 1. S7 协议运行时通信（主方案）

**位置:** `mcp-servers/plc-mcp-bridge/s7_adapter.py` + `tools_s7.py`

通过 python-snap7 直接读写西门子 PLC（PLCSIM / 真机），是 Phase 1 运行态通信的主方案。

**特点:**
- 不需要 OPC UA Server 启用
- 兼容 PLCSIM 仿真和 S7-1200/1500 真机
- 支持 M（Merker）/ MB / MW / MD / DB 地址

**MCP 工具（4个）：**

| 工具 | 功能 | 安全 |
|:----|:-----|:----:|
| `s7_connect(ip, rack, slot)` | 连接 PLC | — |
| `s7_read(address)` | 读变量 | 只读 |
| `s7_write(address, value)` | 写变量 | ✅ Safety 校验 + 审计 |
| `s7_status()` | 连接/CPU 状态 | — |

**验证结果（2026-06-16，PLCSIM TCP/IP 模式）：**
```
Connect:           ✅ 192.168.0.110 (Rack=0, Slot=1)
Read M0.0:         ✅ False
Read MW10:         ✅ 1234
Write MW10=1234:   ✅ 读回验证 = 1234
Write MD20=3.14:   ✅ 读回验证 = 3.14
Write M0.0=True:   ✅ 读回验证 = True
EdgeGateway 采集:  ✅ 13/13 标签连续 3 轮通过
```

---

### 2. OPC UA MCP Server（备选方案）

**位置:** `mcp-servers/opcua-mcp/server.py`

用于西门子 S7-1200/1500 的 OPC UA 通信，封装为 FastMCP 服务。

**工具列表：**

| 工具 | 功能 | 安全校验 |
|------|------|:--------:|
| `opcua_connect(endpoint)` | 连接 OPC UA 服务器 | — |
| `opcua_read(node_id)` | 读取节点值 | ✅ 审计日志 |
| `opcua_browse(node_id)` | 浏览地址空间 | ✅ 只读 |
| `opcua_write(node_id, value)` | 写入节点 | ✅ 互锁+熔断+审计 |
| `opcua_get_status()` | 连接与熔断器状态 | — |
| `opcua_disconnect()` | 断开连接 | — |
| `opcua_reset_fuse()` | 重置熔断器 | — |

> **注意:** OPC UA 在 PLCSIM 上不可用，需真机 S7-1200/1500 测试。运行态通信以 S7 协议为主。

---

### 3. S7 适配器（供 EdgeGateway 共享使用）

**位置:** `mcp-servers/plc-mcp-bridge/s7_adapter.py`

封装 python-snap7，提供统一的 S7 读写接口：

```python
from s7_adapter import S7Adapter

adapter = S7Adapter()
adapter.connect("192.168.0.110", 0, 1)

val = adapter.read_address("MW10")     # 读 Merker 字
val = adapter.read_address("M0.0")     # 读 Merker 位
val = adapter.read_address("MD20")     # 读 Merker 双字
adapter.write_address("MW10", 1500)    # 写入
adapter.disconnect()
```

地址格式支持：
- `M0.0` — 位（Merker）
- `MB0` — 字节（Merker Byte）
- `MW10` — 字（Merker Word, int16）
- `MD20` — 双字（Merker Double, float32）
- `DB1.MW10` — DB 块中的字

---

### 4. Safety 安全模块

**位置:** `safety/`

| 文件 | 功能 | 测试 |
|------|------|:----:|
| `validator.py` | 写入校验：急停禁用、熔断、值跳变检测 | ✅ 14 测试 |
| `interlock-rules.yml` | 可配置的互锁规则 | ✅ 3 条规则 |
| `audit.py`（重导出 `mcp_common/audit.py`） | 链式哈希审计日志 | ✅ 7 测试 |

**安全红线（绝对遵守）：**
1. ❌ 禁止 AI 直接操作急停回路（只能读状态）
2. ❌ 禁止 AI 修改安全 PLC（F-CPU）参数
3. ❌ 禁止 AI 在生产环境无确认写入
4. ⚡ 连续 3 次异常值自动熔断，切断 AI 控制权限

---

### 5. 审计日志

**位置:** `mcp_common/audit.py`

链式哈希审计日志，不可篡改，支持验证完整性。

```python
from mcp_common.audit import get_audit_logger
logger = get_audit_logger()
logger.log("write", "MW10", "1500", operator="ai")
assert logger.verify()  # True: 未被篡改
```

---

## 🚀 快速启动

### 前置条件

| 需求 | 版本 | 用途 |
|------|------|------|
| Python 3.13+ | — | MCP Server + 工具链 |
| python-snap7 | — | S7 协议通信 |
| PLCSIM V18 | V18 | 西门子 S7-1500 仿真 |
| TIA Portal | V18 | 项目管理与下载 |

### 环境变量

复制 `.env.example` 到 `.env`，至少配置：

```bash
# DeepSeek API（AI 决策用）
DEEPSEEK_API_KEY=sk-your-key-here

# S7 协议 PLC 连接
S7_PLC_IP=192.168.0.110
S7_RACK=0
S7_SLOT=1
```

### 启动 S7 读写服务

```bash
# stdio 模式（给 Claude Code 用）
cd mcp-servers/plc-mcp-bridge && python server.py

# 测试连接
python -c "
from s7_adapter import S7Adapter
a = S7Adapter()
print(a.connect('192.168.0.110', 0, 1))
print(a.read_address('M0.0'))
a.disconnect()
"
```

### 完整验证

```bash
# Phase 2 验证脚本（涵盖所有 Phase 1 能力）
python verify_phase2.py

# 真实 PLC 连接测试
python verify_phase2.py --all
```

---

## 🧪 测试

```bash
# PLC MCP Bridge 测试（35 项）
python -m pytest mcp-servers/plc-mcp-bridge/tests/ -v

# Safety 测试（21 项）
python -m pytest tests/test_safety_validator.py tests/test_safety_audit.py -v

# Phase 2 验证（20 项，含真实 S7 连接）
python verify_phase2.py --all
```

---

## ⚠️ PLCSIM TCP/IP 模式工作流

PLCSIM 切换到 TCP/IP 模式后才能被 Python/snap7 连接：

```
1. PLCSIM 设为内部模式（Softbus）
2. TIA Portal 下载项目到仿真器（内部模式下载稳定）
3. 停止 PLCSIM 实例
4. 切换到 TCP/IP Single Adapter 模式
5. 重新启动实例
6. Python/snap7 通过 192.168.0.110 连接读写
```

注意：TCP/IP 模式下 TIA Portal 无法在线连接是正常的，用 Python 读写即可。

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| ping 192.168.0.110 超时 | PLCSIM 未开 TCP/IP 模式 | 切到 TCP/IP |
| `Object does not exist` | 地址在 PLC 程序中未定义 | 确认 TIA 项目中定义了该地址 |
| `TCP connection failed` | PLCSIM 没启动或 IP 不对 | `tasklist \| grep PLCSIM` 检查进程 |
| MW10 读不了 | S7-PLCSIM V18 不支持 MW | ✅ 已修复（s7_adapter 用 mb_read 替代 db_read） |

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `mcp-servers/plc-mcp-bridge/tools_s7.py` | S7 协议 MCP 工具（4 个） |
| `mcp-servers/plc-mcp-bridge/s7_adapter.py` | S7 协议适配器（供 MCP + EdgeGateway 共享） |
| `mcp-servers/opcua-mcp/server.py` | OPC UA MCP Server（备选） |
| `edge-gateway/src/app.py` | 边缘网关控制循环（Phase 2） |
| `safety/validator.py` | 写入安全校验器 |
| `safety/interlock-rules.yml` | 互锁规则配置 |
| `mcp_common/audit.py` | 链式哈希审计日志 |
| `mcp_common/config.py` | 统一配置加载器 |
| `verify_phase2.py` | Phase 2 验证脚本 |
| `.env` | 环境变量配置 |

---

## 🔜 后续

| 待办 | 所属阶段 |
|------|:--------:|
| OPC UA 真机验证 | Phase 1（备选方案） |
| 三菱 MC 协议 MCP Server | Phase 1（缺硬件） |
| AI 控制闭环完整验证 | ✅ Phase 2 已完成 |
| InfluxDB + Grafana 部署 | Phase 2（需 Docker） |
| 本地 LLM 部署（Ollama） | Phase 2 |
