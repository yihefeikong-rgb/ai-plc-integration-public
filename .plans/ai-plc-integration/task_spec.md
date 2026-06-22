# Task Specifications — AI 接入 PLC

> 每个 task_spec 条目是单一 vertical slice 的完整合同。只有 team-lead 可以创建/修改。

## TS001 — 初始化 Team OS 工作流

### 目标
让多角色协作从语言约定变成文件层、入口层、权限层、交接层的硬约束。

### 范围
- 必须完成：task_queue.md、task_spec.md、CLAUDE.md 更新、角色文件边界固化、最小 slice 示例。
- 不做：任何业务功能代码、任何 TIA/S7/PLC 相关实现。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] `task_queue.md` 存在且包含当前活动任务。
- [ ] `task_spec.md` 存在且包含 TS001。
- [ ] `CLAUDE.md` 中新增 "Team OS 主控规则" 章节，明确主对话只能拆分、调度、验收。
- [ ] `agents/*.md` 每个文件都包含：输入、输出、禁止事项。
- [ ] 一个最小 slice 示例在 `workflows/vertical-slice.md` 中可运行描述。
- [ ] `progress.md` 与 `handoff.md` 已更新。

### 研究问题（Researcher）
- 当前 `.plans/ai-plc-integration/` 还缺哪些文件？
- 当前 `CLAUDE.md` 中哪些规则与 Team OS 冲突？

### 实现清单（Developer）
- 创建/修改上述文件，不写业务代码。

### 审查清单（Reviewer）
- 角色边界是否清晰？
- 是否有主对话越权空间？
- 是否有文件缺失？

## TS002 — 完成 Phase 3 TiaWorker 剩余 10%

### 目标
将 Phase 3（TIA Portal 工程态 / TiaWorker）从 90% 推到 100%，使 TIA MCP 工具链达到可稳定交付状态。

### 范围
- 识别当前 Phase 3 剩余未完成的子项（代码、测试、文档、稳定性）。
- 不引入 Phase 4（工业机器人）或 Phase 5（统一编排）的新功能。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] Researcher 已输出 Phase 3 剩余任务的完整 findings。
- [ ] Developer 已完成剩余实现，新增/修复的代码有测试覆盖。
- [ ] 相关 TIA MCP 测试全部通过。
- [ ] Reviewer 按 5 维度审查，结论为 STRONG 或 ADEQUATE。
- [ ] `docs/phase-3-tia-engineering.md` 和 `.plans/ai-plc-integration/docs/architecture.md` 已同步。

### 研究问题（Researcher）
- 当前 `mcp-servers/tia-mcp/` 目录中哪些子模块标记为 TODO / FIXME / 未实现？
- 哪些 TIA MCP 工具没有测试覆盖？
- `p3_flow.py` / `download_to_plcsim.py` / `TiaWorker/` 中哪些路径未经验证？
- 文档与代码不一致的地方有哪些？

### 实现清单（Developer）
- 按 findings 完成剩余实现和测试补充。
- 更新相关 docs。

### 审查清单（Reviewer）
- 实现是否符合 invariants？
- 测试是否覆盖新增路径？
- 文档是否同步？

### 文档同步（Documenter）
- 更新 `progress.md`：Phase 3 完成 100%。
- 更新 `handoff.md`。
- 同步 `docs/phase-3-tia-engineering.md`。

---

## TS002 — 完成 Phase 3 TiaWorker 剩余 10%

### 目标
将 Phase 3（TIA Portal 工程态 / TiaWorker）从 90% 推到 100%，重点补齐测试覆盖和关键功能缺口。

### 范围
- 补齐 `mcp-servers/tia-mcp/` Python 层的单元测试。
- 修复 `p3_flow.py` 编译输出 JSON 解析兼容性问题。
- 为 `gen_io_map.py` 和 `create_plc_tags.py` 添加测试。
- 不引入 Phase 4（工业机器人）或 Phase 5（统一编排）的新功能。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] `server.py` 的 9 个 MCP 工具均有 mock 测试覆盖。
- [ ] `p3_flow.py` 编译输出 JSON 解析与实际 TiaWorker 输出格式一致。
- [ ] `gen_io_map.py` 和 `create_plc_tags.py` 有单元测试。
- [ ] 新增测试全部通过。
- [ ] Reviewer 按 5 维度审查，结论为 STRONG 或 ADEQUATE。
- [ ] `docs/phase-3-tia-engineering.md` 和 `.plans/ai-plc-integration/docs/architecture.md` 已同步。

### 研究问题（Researcher）
- 已由 Researcher 完成：`.superpowers/sdd/research-ts002-report.md`

### 实现清单（Developer）
- 按 findings 优先实现 P0/P1 项。
- 更新相关 docs。

### 审查清单（Reviewer）
- 实现是否符合 invariants？
- 测试是否覆盖新增路径？
- 文档是否同步？

### 文档同步（Documenter）
- 更新 `progress.md`：Phase 3 P0/P1 测试与修复完成。
- 更新 `handoff.md`。
- 同步 `docs/phase-3-tia-engineering.md`。

---

## TS003 — 补齐 TiaWorker C# 核心测试

### 目标
为 TiaWorker C# 层核心业务方法添加单元测试，从空壳测试提升到关键路径覆盖。

### 范围
- 优先覆盖 `import-scl`, `compile`, `download`, `list-devices` 命令。
- 不改动 TiaWorker 核心逻辑，只加测试。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] `UnitTest1.cs` 空壳测试被替换或删除。
- [ ] 至少 4 个核心命令有独立测试。
- [ ] C# 测试项目 `dotnet test` 全部通过。
- [ ] Reviewer 确认测试质量。

### 文档同步（Documenter）
- 更新 `progress.md`：TiaWorker C# 核心测试完成。
- 更新 `handoff.md`。

---

## TS004 — 扩展 TIA MCP 工具映射与 FB501 自动调用

### 目标
补上 Phase 3 最后的功能缺口：更多 TiaWorker 命令映射为 MCP 工具，并修复 FB501 自动调用问题。

### 范围
- 将高优先级 TiaWorker 命令映射为 MCP 工具：`list-blocks`, `create-block`, `export-block`, `list-udts`, `go-online`, `go-offline`。
- 修复 `ConveyorControl FB501` 未在 OB1 自动调用的问题（`call_fb_in_ob1.py` 接入 `full_pipeline` / `download_to_plcsim`）。
- 修复 `layout_engine.py` 分支叠加 bug。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] 新增 MCP 工具可用。
- [ ] FB501 自动调用流程验证通过。
- [ ] 新增测试通过。
- [ ] Reviewer 通过。

### 文档同步（Documenter）
- 更新 `progress.md`：Phase 3 工具映射与 FB501 修复完成。
- 更新 `handoff.md`。
- 同步 `docs/phase-3-tia-engineering.md`。

---

## TS005 — 启动 Phase 5 统一编排层

### 目标
定义并启动 Phase 5（统一编排层）的最小可行实现。

### 范围
- 明确 Phase 5 的边界：统一编排哪些 MCP 服务器/模块？
- 不实现 Phase 4（工业机器人）。
- 只产出 Phase 5 的架构设计和第一个最小可运行 slice。

### 角色路径
```
Researcher → Developer → Reviewer → Documenter
```

### 验收标准
- [ ] Researcher 已输出 Phase 5 范围、依赖、风险的 findings。
- [ ] Developer 已完成统一编排层的骨架代码（或设计文档）。
- [ ] Reviewer 确认设计满足 invariants 且不过度设计。
- [ ] 相关架构文档已同步。

### 研究问题（Researcher）
- Phase 5 需要统一编排哪些现有模块？（S7/OPCUA/Modbus/TIA/Mitsubishi/安全层）
- 现有架构中是否已经存在编排层代码？
- 需要引入新的编排抽象吗？（如工作流引擎、状态机）

### 实现清单（Developer）
- 按 findings 创建 Phase 5 骨架。
- 写最小可运行示例或测试。

### 审查清单（Reviewer）
- 架构是否清晰？
- 是否有安全红线风险？

### 文档同步（Documenter）
- 更新 `progress.md`：Phase 5 启动。
- 更新 `handoff.md`。
- 同步架构文档。

---

## TS006 — P5 编排层启动引导（Bootstrap）

### 目标
实现编排层启动时自动连接所有配置好的 MCP 服务器，并自动注册所有工作流。

### 范围
- 新建 `orchestrator/bootstrap.py`，提供 `bootstrap()` 异步函数
- 读取 `server_configs.ALL_SERVERS`，逐个调用 `pool.connect_server()`
- 连接成功后注册到 `Registry`
- 自动调用各工作流模块的 `register_*` 函数
- 提供 `shutdown()` 清理函数
- 错误处理：单个服务器连接失败不阻塞其他服务器

### 验收标准
- [ ] `bootstrap()` 函数存在且可调用
- [ ] 连接所有 `ALL_SERVERS` 中的服务器
- [ ] 工作流自动注册（无需手动调用 register 函数）
- [ ] 单服务器失败不阻塞其他
- [ ] 有测试覆盖（mock connect）
- [ ] Reviewer 通过

---

## TS007 — S7 读写安全工作流

### 目标
在编排层中实现 S7 监控工作流，替代 edge-gateway 的核心功能（采集→变化检测→AI分析→安全写入）。

### 范围
- 新建 `orchestrator/workflows/s7_monitor.py`
- 工作流步骤：读取标签 → 变化检测 → AI 分析（mock）→ SafetyGate 检查 → 写入
- 使用 `ctx.call("plc-mcp-bridge.s7_read")` 和 `ctx.call("plc-mcp-bridge.s7_write")`
- 内置变化检测逻辑（delta 阈值）
- 写入操作自动经过 SafetyGate

### 验收标准
- [ ] 工作流注册为 `s7_monitor`
- [ ] 读取→分析→写入完整流程可用（mock 模式）
- [ ] SafetyGate 拦截写入操作
- [ ] 变化检测逻辑有测试
- [ ] Reviewer 通过

---

## TS008 — TIA 全流水线跨服务器工作流

### 目标
实现跨 plc-mcp-bridge + tia-mcp 的端到端 TIA 工程流水线。

### 范围
- 新建 `orchestrator/workflows/tia_full_pipeline.py`
- 工作流步骤：创建项目 → 生成 SCL → 导入 → 编译 → 下载到 PLCSIM
- 跨服务器调用：plc-mcp-bridge（项目操作）+ tia-mcp（代码生成/导入）
- 每步结果传递给下一步
- 错误处理：任一步骤失败时中止并返回错误

### 验收标准
- [ ] 工作流注册为 `tia_full_pipeline`
- [ ] 跨服务器调用正确路由
- [ ] 步骤间数据传递正确
- [ ] 失败中止逻辑有测试
- [ ] Reviewer 通过

---

## TS009 — desktop-mcp 接入 + 工具分类

### 目标
将 desktop-mcp 接入编排层，并为所有工具添加分类标签。

### 范围
- 在 `server_configs.py` 添加 `DESKTOP_MCP` 配置
- 将 `DESKTOP_MCP` 加入 `ALL_SERVERS` 和 `SERVER_MAP`
- 在 `registry.py` 中为 `ToolInfo` 添加 `category` 字段（safety/monitoring/control/engineering/desktop）
- 为已有工具分类提供辅助函数

### 验收标准
- [ ] `DESKTOP_MCP` 配置存在且格式正确
- [ ] `ToolInfo` 有 `category` 字段
- [ ] 分类辅助函数可用
- [ ] 测试覆盖
- [ ] Reviewer 通过

---

## TS010 — FastAPI 入口点

### 目标
为编排层提供 HTTP API，暴露工作流执行、状态查询、工具列表等能力。

### 范围
- 新建 `orchestrator/api.py`
- 端点：
  - `GET /workflows` — 列出所有已注册工作流
  - `POST /workflows/{name}/run` — 执行指定工作流
  - `GET /tools` — 列出所有可用工具
  - `GET /servers` — 列出所有已连接服务器
  - `GET /health` — 健康检查
- 启动时调用 `bootstrap()`
- 与现有 ai-plc-assistant 后端集成（独立路由文件）

### 验收标准
- [ ] 5 个端点可用
- [ ] 启动时自动 bootstrap
- [ ] 工作流执行返回 WorkflowResult
- [ ] 有测试覆盖（TestClient）
- [ ] Reviewer 通过