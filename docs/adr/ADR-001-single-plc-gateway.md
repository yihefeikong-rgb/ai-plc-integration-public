# ADR-001: PLC Engineering Gateway 作为唯一工业 MCP 入口

- **编号**: ADR-001
- **日期**: 2026-07-22
- **状态**: Proposed
- **作者**: Architecture Team
- **审查人**: TBD
- **影响范围**: mcp-servers/, orchestrator/, safety/, mcp_common/, edge-gateway/

---

## 1. 背景

本项目（AI 接入 PLC）在迭代过程中逐步生长出多个独立的工业 MCP 服务器：

| MCP 服务器 | 协议 | 成熟度 | 数量 |
|-----------|------|--------|------|
| plc-mcp-bridge | FastMCP | 高 | 65 工具 |
| tia-mcp (TiaWorker) | FastMCP | 高 (98%) | 16 工具 |
| opcua-mcp | FastMCP | 中 | 7 工具 |
| modbus-mcp | FastMCP | 低 (骨架) | 6 工具 |
| mitsubishi-mcp | FastMCP | 低 (骨架) | 3 工具 |
| robot-mcp | FastMCP | 中 | 7 工具 |
| desktop-mcp | 自实现 JSON-RPC | 中 | 12 工具 |
| tiacommander-mcp | — | 废弃 | — |

截至当前，共计约 116 个 MCP 工具散布在多个独立的 MCP 服务器中。这些服务器可以被 AI Agent 直接调用，绕过了统一的安全校验、目标约束和审计链路。此外，第三方 MCP 服务器（如 TiaCommander）也可以作为外部 Provider 接入系统，进一步加剧了入口分散的问题。

**核心问题**：缺乏一个统一的工业入口点来确保所有工业操作都经过目标校验、安全确认和审计记录。

---

## 2. 决策

### 2.1 核心决策

**PLC Engineering Gateway 是唯一对外工业 MCP**。所有外部 AI Agent（包括 Claude Code、Claude Desktop 及其他 MCP 客户端）只能通过 PLC Engineering Gateway 与工业设备交互。Gateway 是系统对外暴露的唯一工业 MCP 服务器入口。

### 2.2 架构分层

```
外部 AI Agent / MCP 客户端
        │
        ▼
┌─────────────────────────────────────┐
│  PLC Engineering Gateway (唯一入口)  │
│  ─ 目标校验                          │
│  ─ 安全确认 (SafetyGate)             │
│  ─ 审计日志 (链式 HMAC)              │
│  ─ 工具路由与适配                     │
└──────────┬──────────────────────────┘
           │
    ┌──────┼──────────┬──────────┐
    ▼      ▼          ▼          ▼
TiaWorker  CartGen   S7 协议    其他协议
(内部适配)  (内部适配)  (内部适配)  (内部适配)
```

### 2.3 内部适配器

- **TiaWorker** (C# TIA Openness): 项目正式、可维护、可公开的基础后端。负责 TIA Portal 工程操作（SCL 导入、编译、块管理）。
- **CartGen** (C# .NET 8): LadderSpec JSON 到 SimaticML XML 的转换引擎。
- **各协议实现** (S7/OPC UA/Modbus/三菱 MC): 运行态协议适配器，均属于内部适配层，不对外暴露 MCP 接口。

### 2.4 安全强制

任何工业副作用必须经过 Gateway 的三道关卡：

1. **目标校验**: 确认操作目标为配置中的受控目标（由 `mcp_common/control_target.py` 强制执行），拒绝 IP 漂移和未注册目标。
2. **安全确认**: 经过 SafetyGate 的互锁规则检查、影子仿真验证和静态预检。
3. **审计记录**: 所有控制意图先写入 HMAC 链式哈希审计日志，再执行实际操作。

---

## 3. 方案对比

### 方案 A: 保留多 MCP 入口（现状）

**描述**: 保持现有架构，各 MCP 服务器独立对外暴露，AI Agent 可以直接调用任意服务器。

**优点**:
- 无需重构，零迁移成本
- 各服务器独立部署和升级
- 对已有 MCP 客户端完全兼容

**缺点**:
- 安全链多头治理：validator、shadow_simulator、audit 散落在不同模块
- AI Agent 可以绕过安全层直接调用 S7 写入工具
- 无统一目标校验，IP 漂移风险高
- 新协议接入时需重复实现安全逻辑
- 审计日志分散，难以追溯完整操作链路

**评估**: 不可接受。安全风险过高，无法满足"所有工业操作必须经过审计"的硬性要求。

### 方案 B: PLC Engineering Gateway 单一入口（选定方案）

**描述**: 所有工业 MCP 工具收敛到 PLC Engineering Gateway，外部只能通过 Gateway 调用。

**优点**:
- 单一安全拦截点，安全链完整且不可绕过
- 统一目标校验，从源头拒绝非法目标
- 审计日志集中，操作链路可完整追溯
- 新协议接入时只需实现内部适配器，安全逻辑由 Gateway 统一提供
- 内部适配器切换不影响外部调用方

**缺点**:
- 需要重构，迁移成本较高
- Gateway 成为单点瓶颈（可通过水平扩展缓解）
- 已有 MCP 客户端需要更新连接地址
- 内部适配器变更需遵循 Gateway 契约

**评估**: 选定方案。安全收益远大于迁移成本。此决策与 Phase 5 统一编排层（D-008）的方向一致。

---

## 4. 影响

### 正面影响

1. **安全统一**: 所有工业操作经过单一安全拦截点，消除安全链多头治理。
2. **审计完整性**: 单一入口确保审计日志不遗漏任何控制操作。
3. **目标一致性**: 统一目标校验机制，杜绝 IP 漂移和未注册目标。
4. **简化外部集成**: 外部 AI Agent 只需连接一个 MCP 服务器即可获得所有工业能力。
5. **降低新协议接入成本**: 新协议适配器只需实现内部接口，安全逻辑由 Gateway 提供。

### 负面影响

1. **迁移成本**: 需要将现有 MCP 服务器的工具逐步迁移到 Gateway 中。
2. **单点故障**: Gateway 进程故障会导致所有工业操作不可用（可通过健康检查和自动重启缓解）。
3. **性能开销**: 所有操作多一层路由转发，增加毫秒级延迟（对工业操作可接受）。
4. **开发约束**: 内部适配器变更需遵循 Gateway 接口契约，不能随意修改。

---

## 5. 兼容性: TiaCommander 作为外部 Provider

### 5.1 TiaCommander 的定位

TiaCommander 是可选的外部 Provider，**不替代** PLC Engineering Gateway。

- TiaCommander 是闭源商业 MCP 服务器（原 beta 许可证已于 2026-06-19 到期）。
- 它可以通过 Gateway 的 Provider 适配机制接入，但必须遵循与内部适配器相同的安全约束。
- 外部 Provider 的写操作**禁止自动切换**。切换 Provider 必须经过显式的人工确认，且切换后仍需经过 Gateway 的安全校验。

### 5.2 Provider 接入规则

1. 外部 Provider 必须通过 Gateway 注册，不能直接对外暴露 MCP 接口。
2. 写操作默认使用 TiaWorker（项目正式后端），禁止自动回退到外部 Provider。
3. Provider 切换需人工确认，记录操作者身份和切换原因。
4. 外部 Provider 的操作同样经过 Gateway 的目标校验、安全确认和审计。

### 5.3 下载降级策略

```
1. TiaWorker (C# 直接下载)        ← 默认路径，优先使用
2. TiaWorker GUI 模式              ← 备选
3. Python 脚本 (PLCSIM API)       ← 备选
4. UI 手动操作 (用户指导)          ← 备选
5. Golden restore (绕过 TIA)      ← 最稳，不依赖 Provider
```

写操作禁止自动切换 Provider，所有降级路径需人工确认。

---

## 6. 未解决的问题

### P1: Gateway 与编排层的关系

Phase 5 统一编排层（orchestrator/）已经实现了工作流引擎、MCP 连接池和 SafetyGate 集成。Gateway 需要与编排层明确职责边界：

- Gateway 是 MCP 协议的入口层，负责工具路由和安全拦截。
- Orchestrator 是工作流引擎层，负责多步骤工作流编排。
- 两者是否合并为同一进程，还是保持独立进程通信？

### P2: 工具迁移策略

现有 116 个工具从各 MCP 服务器迁移到 Gateway 的优先级和节奏待确定：

- 高优先级：S7 写入工具、TIA 工程工具（涉及安全）
- 中优先级：诊断工具、导出工具
- 低优先级：实验性协议（Modbus、三菱 MC）

### P3: 外部 Provider 认证机制

TiaCommander 等外部 Provider 接入 Gateway 时需要明确的认证和授权机制：

- 如何验证外部 Provider 的身份？
- 如何限制外部 Provider 的权限范围？
- 如何审计外部 Provider 的操作？

### P4: 向后兼容

现有 MCP 客户端直接连接各 MCP 服务器。迁移到 Gateway 后，需要提供过渡期的兼容方案：

- 是否保留旧的 MCP 服务器入口直到迁移完成？
- 是否提供代理模式，将旧入口的请求转发到 Gateway？

---

## 7. 参考文献

1. **D-008: Phase 5 统一编排层** — `.plans/ai-plc-integration/decisions.md`。建立统一安全拦截点和编排层，与 Gateway 决策方向一致。
2. **D-009: Phase 5 MCP 客户端适配器** — `.plans/ai-plc-integration/decisions.md`。MCP 连接池和安全门集成，为 Gateway 提供基础设施。
3. **ARCHITECTURE.md** — 系统 4 层架构文档，描述了 MCP 协议层、安全层面和编排层的关系。
4. **README.md** — 项目总览，包含安全模型、不可突破的原则和受控仿真验收流程。
5. **docs/research-tia-mcp-ecosystem.md** — TIA Portal MCP 生态研究报告，覆盖了 TiaCommander、TiaWorker 等组件的对比分析。
6. **落地优化方案** — `.plans/ai-plc-integration/落地优化方案.md`。Phase L1-L4 的落地优化方案，包含 TiaWorker 缺陷修复和规范注入。
7. **safety/interlock-rules.yml** — 互锁规则定义，Gateway 安全校验的规则来源。
8. **mcp_common/control_target.py** — 唯一控制目标实现，Gateway 目标校验的基础。

---

## 附录 A: 变更历史

- 2026-07-22: 初始版本 (Proposed)
- 待定: 评审后更新

## 附录 B: 相关人员

- **架构师**: TBD
- **安全审查**: TBD
- **实施团队**: TBD
