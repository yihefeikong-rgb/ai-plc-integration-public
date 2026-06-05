# 阶段 1：运行态基础

> 目标：搭建边缘网关，让 AI 能通过自然语言实时读/写 PLC 数据（OPC UA / Modbus / MC 协议）。
> 这是整个系统的基础——先让 AI 能"看见"设备，才能谈后续的控制和工程态。

---

## 📦 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI 层 (Claude/Cursor)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ OPC UA MCP   │  │ Modbus MCP   │  │ TIA MCP (Phase 3)   │  │
│  │ 读写西门子   │  │ 通用读写     │  │ 工程态              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
└─────────┼──────────────────┼─────────────────────────────────────┘
          │                  │
┌─────────┴──────────────────┴─────────────────────────────────────┐
│                    边缘网关 (edge-gateway/)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 数据采集     │  │ AI 分析决策  │  │ 安全审计             │  │
│  │ Modbus/OPCUA │  │ DeepSeek API │  │ 链式哈希 + 写入校验  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                      │
│  ┌──────┴─────────────────┴──────────────────────────────────┐  │
│  │ InfluxDB 时序数据库                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │
┌─────────┴──────────────────────────────────────────────────────┐
│                     PLC 层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 西门子 S7-   │  │ 三菱 FX5U   │  │ OpenPLC (仿真)      │  │
│  │ 1200/1500    │  │ (待接入)     │  │ Modbus TCP          │  │
│  │ OPC UA       │  │ MC 协议      │  │ port 502            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ 已完成组件

### 1. OPC UA MCP Server

**位置:** `mcp-servers/opcua-mcp/server.py`

用于西门子 S7-1200/1500 的 OPC UA 通信，封装为 FastMCP 服务。

**工具列表：**

| 工具 | 功能 | 安全校验 |
|------|------|:--------:|
| `read_tag(tag_name)` | 读取单个标签 | ✅ 审计日志 |
| `read_tags(tag_names)` | 批量读取 | ✅ 审计日志 |
| `list_tags(root)` | 浏览 OPC UA 地址空间 | — |
| `write_tag(tag_name, value, operator)` | 写入标签 | ✅ 互锁+熔断+审计 |

**写入安全流程：**
```
AI 请求: write_tag("DB1.MotorSpeed", 1500)
  ↓ validator.validate() 检查：
  │  ├─ 标签不是急停/安全回路 → 通过
  │  ├─ 值不超限 (max=3000) → 通过
  │  ├─ 不是异常跳变 → 通过
  │  └─ 连续错误未超限 → 通过
  ↓ audit.log() 记录操作
  ↓ 写入 OPC UA 节点
  ↓ 返回结果 + needs_confirmation 标志
```

**互锁规则配置:** `safety/interlock-rules.yml`
```yaml
write_rules:
  - target: "DB1.MotorSpeed"
    max_value: 3000
    min_value: 0
    require_bits: ["DB1.SafetyOK", "DB1.EmergencyStopOff"]
```

---

### 2. 边缘网关

**位置:** `edge-gateway/`

核心模块，负责数据采集、AI 分析决策、InfluxDB 写入。

| 文件 | 说明 |
|------|------|
| `src/app.py` | 主循环：采集 → 变化检测 → 本地阈值 → AI 分析 → 决策 → 审计 |
| `src/ai_client.py` | DeepSeek API 封装（简单/复杂任务分流） |
| `config/tags.json` | 采集标签配置（含阈值） |
| `Dockerfile` | 容器化构建 |
| `requirements.txt` | Python 依赖 |

**控制循环（30 秒间隔）：**
```
采集所有标签数据
  ↓ 写入 InfluxDB
  ↓ 变化检测（值变化 > delta 才算变化）
  ↓ 本地阈值检查（超限才调 AI）
  ↓ AI 分析 + 决策 (DeepSeek)
  ↓ 写入决策 → 审计日志
```

**Token 优化三层：**
1. **变化检测** — 值没变不调 AI（节省 ~70% 调用）
2. **本地阈值** — 超限才走 LLM（进一步过滤噪声）
3. **降频采集** — 30s 间隔（避免高频轮询）

---

### 3. PLCSIM Advanced 自动化

**位置:** `mcp-servers/tia-mcp/plcsim_api.py`（775 行）

PLCSIM Advanced V5.0 .NET API 的 Python 封装，支持完整的实例生命周期管理。

**功能矩阵：**

| 功能 | 方法 | 依赖 |
|------|------|------|
| 创建空壳实例 | `create_instance()` | PLCSIM GUI |
| 黄金备份 | `archive_instance()` | 实例必须在 STOP |
| 从备份恢复 | `restore_instance()` | 已验证通过 |
| 切换 TCP/IP | `switch_to_tcpip()` | 需虚拟网卡 |
| 实例管理 CLI | `python plcsim_api.py <cmd>` | — |
| 后台保活 | `plcsim_keeper.py` | Softbus 模式 |

**CLI 用法：**
```bash
# 创建实例
python plcsim_api.py create factoryio

# 查看实例列表
python plcsim_api.py list

# 黄金备份
python plcsim_api.py archive factoryio ./backups/golden.zip ./persist

# 从备份恢复
python plcsim_api.py restore factoryio ./backups/golden.zip ./persist

# 后台保活（保持实例运行）
python plcsim_keeper.py
```

---

### 4. Factory IO 连接

**状态：已连接（Softbus 模式）**

| 配置项 | 值 |
|--------|-----|
| 驱动 | Siemens S7-PLCSIM → S7-1500 |
| 实例名 | `factoryio` |
| 连接方式 | Softbus（本地进程通信） |
| 测试场景 | From A to B |

**auto.cfg（`C:\ProgramData\Real Games\Factory IO\auto.cfg`）：**
```
drivers.siemens_s7plcsim.instance_name = 'factoryio'
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.connection_timeout = 60
```

**场景文件 XML 结构（.factoryio）：**
```xml
<Drivers CurrentDriver="6144">
  <SiemensS7PLCSIM>
    <Properties UseWords="False" InstanceName="factoryio" />
  </SiemensS7PLCSIM>
</Drivers>
```

| 驱动 | XML 标签 | `CurrentDriver` |
|:----|:---------|:---------------:|
| S7-PLCSIM (Softbus) | `SiemensS7PLCSIM` | 6144 |
| S7-1200/1500 TCP | `SiemensS71200S71500TCP` | 6144 |
| Modbus TCP Client | `ModbusTCPClient` | 6176 |

- **注意:** 切换场景驱动必须在 GUI 中操作（F4），auto.cfg 不能切换当前驱动

---

### 5. 安全模块

**位置:** `safety/`

| 文件 | 功能 |
|------|------|
| `audit.py` | 链式哈希审计日志（不可篡改） |
| `validator.py` | 写入校验：急停禁用、熔断、值跳变检测 |
| `interlock-rules.yml` | 可配置的安全规则 |

**审计日志结构（每行一个 JSON）：**
```json
{
  "timestamp": "2026-06-04T12:00:00+00:00",
  "action": "write",
  "target": "DB1.MotorSpeed",
  "value": "1500",
  "operator": "ai-agent",
  "success": true,
  "detail": "",
  "prev_hash": "0000...",
  "hash": "a1b2..."
}
```

**安全红线（绝对遵守）：**
1. ❌ 禁止 AI 直接操作急停回路（只能读状态）
2. ❌ 禁止 AI 修改安全 PLC（F-CPU）参数
3. ❌ 禁止 AI 在生产环境无确认写入
4. ⚡ 连续 3 次异常值自动熔断，切断 AI 控制权限

---

## 🚀 快速启动

### 前置条件

| 需求 | 版本 | 用途 |
|------|------|------|
| Python 3.10+ | — | MCP Server + 工具链 |
| Docker | latest | 边缘网关 + InfluxDB |
| .NET SDK | 8.0 | CartGen（Phase 3） |
| PLCSIM Advanced | V5.0 | 西门子 S7-1500 仿真 |
| Factory I/O | latest | 3D 可视化 |

### 环境变量

```bash
# 复制模板
cp .env.example .env

# 必需配置
DEEPSEEK_API_KEY=sk-your-key-here

# 可选配置
OPCUA_ENDPOINT=opc.tcp://192.168.1.10:4840
MODBUS_HOST=localhost
INFLUXDB_PASSWORD=your-password
INFLUXDB_TOKEN=your-token
```

### 启动边缘网关

```bash
# 方式 1：直接运行（开发）
python run_gateway.py

# 方式 2：Docker 部署
make phase1
# 或
docker compose up -d influxdb
python run_gateway.py
```

### 启动 OPC UA MCP Server

```bash
# OPC UA 读写服务
cd mcp-servers/opcua-mcp
python server.py
# 暴露 4 个 MCP 工具：
#   read_tag / read_tags / list_tags / write_tag
```

### 启动 PLCSIM + Factory IO

见 `docs/factory-io-setup-guide.md` 详细步骤。快速指引：

```bash
# 1. 启动 PLCSIM Advanced GUI
# 2. 创建或恢复实例
python mcp-servers/tia-mcp/plcsim_api.py restore factoryio \
  ./backups/golden.zip ./persist
# 3. 打开 Factory IO，连接
# 4. 一键启动（推荐）
python start_all.py
```

---

## 🧪 测试

```bash
make test
# 或
python -m pytest tests/ -v
```

当前测试覆盖：
- `tests/test_config_loader.py` — 22 测试（配置解析、环境变量、Schema 校验）
- `tests/test_safety_audit.py` — 7 测试（链式哈希、防篡改检测）
- `tests/test_safety_validator.py` — 14 测试（急停禁用、熔断、值跳变）

---

## ⚠️ 重要约束

### PLCSIM PowerOff 铁律
**任何方式的 PowerOff 后实例无法再次启动**，必须重启电脑。
更新程序时：TIA Portal 切 STOP → 下载 → 切回 RUN，不要关实例。

### 首次下载限制
首次将硬件配置下载到 PLCSIM 必须通过 **TIA Portal GUI 手动完成**。
Openness API 不支持首次下载（Siemens 官方限制）。首次完成后可用 API 自动化。

### 虚拟网卡
TCP/IP 模式需要 PLCSIM 虚拟网卡。已安装（接口 ID=13），切换前需调用
`SimulationRuntimeManager.ResetNetInterfaceBindings()`。

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `mcp-servers/opcua-mcp/server.py` | OPC UA MCP Server |
| `mcp-servers/tia-mcp/plcsim_api.py` | PLCSIM .NET API 封装 |
| `mcp-servers/tia-mcp/plcsim_keeper.py` | PLCSIM 后台保活 |
| `edge-gateway/src/app.py` | 边缘网关主循环 |
| `edge-gateway/src/ai_client.py` | DeepSeek API 封装 |
| `safety/audit.py` | 链式哈希审计日志 |
| `safety/validator.py` | 写入安全校验器 |
| `safety/interlock-rules.yml` | 互锁规则配置 |
| `run_gateway.py` | 网关启动脚本 |
| `start_all.py` | PLCSIM + Factory IO + TIA MCP 一键启动 |

---

## 🔜 后续

| 待办 | 所属阶段 |
|------|:--------:|
| 三菱 MC 协议 MCP Server | Phase 1 |
| OPC UA 仿真环境搭建 | Phase 1 |
| AI 控制闭环完整验证 | Phase 2 |
| 图表可视化（Grafana） | Phase 2 |
| 本地 LLM 部署（Ollama） | Phase 2 |
