# ADR-003: TIA Provider 路由与所有权

- **编号**: ADR-003
- **日期**: 2026-07-22
- **状态**: Proposed (read-only migration validation)
- **作者**: Architecture Team
- **审查人**: TBD
- **影响范围**: mcp-servers/plc-gateway/, orchestrator/

---

## 1. 背景

PLC Engineering Gateway 支持多种 TIA 后端 Provider，当前包括：

| Provider | 类型 | 可用性 | 写入能力 | 适用场景 |
|----------|------|--------|---------|---------|
| TiaWorker | 项目自有开源 | 只读迁移期使用 | Gateway 未暴露写能力 | 离线/受控只读验证 |
| TiaCommander | 外部闭源 | 可选（默认关闭） | Gateway 当前不启用写模式 | 后续独立审查 |

双 Provider 架构需要明确的**路由规则**和**所有权边界**，避免：
- 同一操作由不同 Provider 执行导致结果不一致
- 写操作在 Provider 间自动 fallback 导致安全漏洞
- AI 客户端无法预测哪个 Provider 将执行操作

---

## 2. 决策

### 2.1 路由规则

| 操作类型 | 默认 Provider | 可选 Provider | 是否允许 fallback | 需要 Preview | 需要确认 |
|---------|-------------|-------------|-----------------|-------------|---------|
| 项目信息读取 | TiaWorker | TiaCommander | 是（只读） | 否 | 否 |
| 块列表/XML/接口 | TiaWorker | TiaCommander | 是（只读） | 否 | 否 |
| 硬件列表 | TiaWorker | TiaCommander | 是（只读） | 否 | 否 |
| 编译 | TiaWorker | 否 | 否 | 是 | 是 |
| 创建/删除块 | TiaWorker | 否 | 否 | 是 | 是 |
| 导入 XML | TiaWorker | 否 | 否 | 是 | 是 |
| 网络元数据修改 | TiaCommander | TiaWorker | 否 | 是 | 是 |
| 网络结构修改 | TiaCommander | 否 | 否 | 是 | 是 |

### 2.2 核心原则

1. **写操作永不自动 fallback。** 如果默认 Provider 不可用，写操作必须失败并给出明确错误，而非静默切换到另一个 Provider。

2. **TiaCommander 默认只读。** 写操作必须通过 `read_only=False` 显式启用，且只能在配置了安全链的环境中使用。

3. **TiaWorker 是所有权默认值。** 除非 TiaCommander 是唯一可用的 Provider，否则所有普通操作优先使用 TiaWorker。

4. **Provider 选择由路由策略决定，而非 AI 客户端。** 客户端可以通过 `preferred_provider` 参数提示，但最终决策由 Gateway 的 `RoutingPolicy` 做出。

---

## 3. TiaCommander 不可用时的行为

| 场景 | 行为 |
|------|------|
| TiaCommander 未安装 | Gateway 降级到 TiaWorker-only 模式，TiaCommander 写操作返回错误 |
| TiaCommander 进程崩溃 | 连接池自动断开，下次调用重新连接 |
| TiaCommander 写操作超时 | 标记为 RECONCILE_REQUIRED，需要人工介入 |
| 版本不匹配（V18 vs V21） | 阻止所有操作，返回版本冲突错误 |

---

## 4. 未来 Provider 扩展

预留 Provider 接口支持以下未来扩展：

| Provider | 用途 | 优先级 |
|----------|------|--------|
| S7Adapter | S7 运行态读写 | 低（已有 plc-mcp-bridge） |
| PLCSIMAdapter | PLCSIM 仿真控制 | 低（已有独立工具） |
| OPCUAAdapter | OPC UA 协议 | 低（已有独立 MCP） |

---

## 5. 安全考虑

- **写操作必须有明确的 Audit Trail。** 审计日志记录 Provider、操作者、目标、时间戳和 HMAC 链式哈希。
- **TiaCommander 写操作必须通过 Preview/Confirm 流程。** 不允许直接调用 `apply_patch`。
- **Provider 切换事件必须记录。** 当路由策略因 Provider 不可用而变更时，记录日志。

---

## 6. 影响

- 正面：明确的 Provider 路由消除不确定性
- 正面：TiaCommander 只读默认降低误操作风险
- 负面：TiaCommander 写操作需要额外配置步骤
- 迁移：当前使用 TiaWorker 的工作流不受影响

---

## 7. 相关 ADR

- [ADR-001: PLC Engineering Gateway 作为唯一工业 MCP 入口](ADR-001-single-plc-gateway.md)
- [ADR-002: TiaCommander 外部闭源 TIA 后端](ADR-002-tiacommander-adoption.md)
