# 研究发现 — AI 接入 PLC

> 最后更新：2026-06-23

---

## TS005 — Phase 5 统一编排层调研

> 研究者：Researcher (Haiku)
> 日期：2026-06-22

### 现有模块清单

| 模块 | 路径 | 功能 | 工具数 | 成熟度 |
|------|------|------|--------|--------|
| plc-mcp-bridge | mcp-servers/plc-mcp-bridge/ | S7 运行态 + TIA 工程态 + PLCSIM + FIO 全流水线 | 65 | 高 |
| tia-mcp | mcp-servers/tia-mcp/ | SCL/LAD 代码生成与导入、TiaWorker C# 调用 | 16 | 高(~98%) |
| desktop-mcp | mcp-servers/desktop-mcp/ | 桌面控制（鼠标/键盘/截屏），自实现 JSON-RPC | 12 | 中 |
| robot-mcp | mcp-servers/robot-mcp/ | 工业机器人控制（FIO Pick & Place） | 7 | 中 |
| opcua-mcp | mcp-servers/opcua-mcp/ | OPC UA 协议读写 | 7 | 中 |
| modbus-mcp | mcp-servers/modbus-mcp/ | Modbus TCP 协议 | 6 | 低(骨架) |
| mitsubishi-mcp | mcp-servers/mitsubishi-mcp/ | 三菱 MC 协议 | 3 | 低(骨架) |
| safety/ | safety/ | 安全层（validator + shadow_sim + audit） | — | 高 |
| mcp_common/ | mcp_common/ | 公共基础设施（audit/config/deepseek/connection） | — | 高 |
| edge-gateway | edge-gateway/ | 运行态 AI 控制闭环 | — | 中 |

**MCP 工具总计: ~116**

### 现有接口/协议

- **MCP stdio**: 所有 MCP 服务器统一对外接口（除 desktop-mcp 自实现 JSON-RPC）
- **FastMCP 框架**: 大部分服务器使用 `@mcp.tool()` 注册
- **代码级 import 耦合**: `tia-mcp`/`opcua-mcp`/`edge-gateway` 直接 import `safety.validator`
- **进程级耦合**: `plc-mcp-bridge` 通过 subprocess 调用 `TiaWorker.exe`
- **无统一消息总线、无服务发现、无健康检查**

### 是否已有编排层代码

**不存在统一编排层。** 现有"管线"代码均为单服务器内硬编码：

| 位置 | 性质 |
|------|------|
| `tools_pipeline.py::plc_run_pipeline` | P3 流水线（5步），仅针对 P3 场景 |
| `tia-mcp/server.py::full_pipeline` | TIA 工程态流水线，仅针对 TIA |
| `edge-gateway::ai_control_loop` | 运行态控制闭环，仅针对 Phase 2 |
| `docker-compose.yml` | Docker 基础设施编排，不涉及 MCP |

### 关键风险

1. **跨模块耦合严重** — edge-gateway 直接 import plc-mcp-bridge 的内部模块
2. **安全链多头治理** — 至少 4 处独立安全实现，规则不一致
3. **desktop-mcp 协议不统一** — 非 FastMCP，需额外适配
4. **无服务发现/健康检查** — 所有 MCP 服务器是 stdio 子进程，无优雅重启

### Phase 4 骨架状态

- `mcp-servers/robot-mcp/` 已有骨架代码（7 工具，Pick & Place 场景）
- robot-mcp 自实现急停检查，未接入统一 `safety/validator.py`
- 预留 Palletizer 场景但未实现

### 设计建议要点

1. 建立统一安全链入口点（解决多头治理）
2. 统一所有 MCP 服务器为 FastMCP 协议
3. 将"管线"概念提升到编排层，不在每个服务器重复实现
4. `mcp_common/` 已就绪，可作为编排层构建基础

---

## TS004 — Phase 3 剩余任务与 FB501 问题（已完成）

> 研究者：Researcher (Haiku / DS-V4-Flash)
> 日期：2026-06-22
> 状态：DONE

### 要点
1. TIA MCP 工具映射缺口 — 6 个 TiaWorker 命令未映射 → 已修复（新增 7 工具）
2. FB501 自动调用失效 → 已修复（call_fb_in_ob1 接入 MCP）
3. layout_engine.py 分支叠加 bug → 已修复

---

## TS002 — Phase 3 Python 层测试（已完成）

> 状态：DONE

### 要点
- server.py 9 个 MCP 工具全部有 mock 测试覆盖（40 测试）
- p3_flow.py 编译输出 JSON 解析修复
- gen_io_map.py 15 测试 + create_plc_tags.py 17 测试
- 新增 83 测试全部通过

---

## Phase 6B — cc-haha 自动化接入调研

> 研究者：Claude Code (Flash)
> 日期：2026-06-23

### cc-haha 架构发现

1. **三层架构**：CLI（Commander.js + Ink） / Desktop（Electron + React/Vite） / Sidecar（统一二进制）
2. **Sidecar 三种模式**：
   - `server` 模式：启动 Bun HTTP/WS 服务器（默认 `127.0.0.1:3456`），28 条 REST API 路由
   - `cli` 模式：运行 CLI 入口
   - `adapters` 模式：IM 机器人（飞书/微信/Telegram/钉钉/WhatsApp）
3. **API 路由覆盖**：sessions、conversations、tasks、agents、settings、status、scheduled-tasks 等
4. **WebSocket**：`/ws/{sessionId}` 客户端镜像，`/sdk/{sessionId}` SDK 内部

### 自动化路线排序

1. **A：Sidecar API 自动化**（推荐）— HTTP REST API，精细控制，低实现成本
2. **B：CLI 子进程**（可行但不优先）— 进程管理复杂，无持久状态
3. **C：GUI 桌面自动化**（不推荐）— 脆性、慢、cc-haha 已有 API

### 关键结论

- cc-haha 的设计意图就是 API 优先（sidecar server 模式专为此设计）
- 最小 MVP 不需要 GUI 自动化，纯 API 调用即可
- 可在一阶段约束下实现受控自动化（停在 Review 前）
