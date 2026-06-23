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

---

## TS018 — robot-mcp snap7 回退路径验证

### 目标
验证 robot-mcp 的 S7 回退路径（`BACKEND=snap7`）能用 python-snap7 v3 实际连接 PLCSIM Advanced，确保 OPC UA 不可用时自动降级到 S7 协议。

### 背景
- python-snap7 v3.0.0 已安装（纯 Python，零 C 依赖）
- robot-mcp 已有 snap7 回退代码（`connect_snap7()` + snap7 `read_io`/`write_io` 分支）
- PLCSIM Advanced V8.0 已安装
- robot-mcp 当前 snap7 API 使用 `snap7.client.Client()`、`read_area`/`write_area`——v3 均兼容

### 范围
- 验证 `connect_snap7()` 实际连接到 PLCSIM 实例
- 验证 `read_io()` snap7 路径读取输入传感器值
- 验证 `write_io()` snap7 路径写入执行器
- 验证急停检查在 snap7 模式下工作
- 验证 snap7 不可用时的优雅降级
- 新增测试覆盖 snap7 路径
- 不做：修改 robot-mcp 核心逻辑、OPC UA 功能、simulated 模式

### 角色路径
```
Developer → Reviewer → Documenter
```

### 验收标准
- [ ] robot-mcp snap7 模式连接到 PLCSIM 实例成功
- [ ] S7 读/写 I/O 全流程通过（mock + 真实连接）
- [ ] 急停检查在 snap7 模式下有效
- [ ] snap7 不可用时不崩溃（优雅降级到 simulated）
- [ ] 新增测试全部通过，不影响现有 21 个模拟后端测试
- [ ] Reviewer 按 5 维度审查通过

### 实现清单（Developer）
- 安装 python-snap7 v3（已完成）
- 创建测试：`test_snap7_backend.py` 覆盖 snap7 连接/读写/急停/降级
- 如果发现 robot-mcp snap7 代码有 v3 兼容问题，适配修复
- 运行全量测试确认不破坏现有功能

### 审查清单（Reviewer）
- snap7 回退是否覆盖所有故障场景？
- 测试是否覆盖正常 + 异常路径？
- 现有 simulated 模式测试是否仍然通过？

---

## TS019 — PLCSIM Advanced 集成验证

### 目标
验证 python-snap7 v3 通过 S7 协议连接 PLCSIM Advanced 的完整流程，确认虚拟 PLC 可读写。

### 背景
- PLCSIM Advanced V8.0 已安装
- python-snap7 v3.0.0 已安装（纯 Python S7 通信）
- S7 适配器（`s7_adapter.py` / `tools_s7.py`）使用 v3 兼容 API
- 30 S7 测试已通过（mock 模式）
- 本任务首次在真实 PLCSIM 实例上验证

### 范围
- 创建 PLCSIM Advanced 实例（或使用已有 factoryio 实例）
- 用 python-snap7 v3 直连 PLCSIM（不经过 MCP 服务器）
- 验证基本读写：M 区、DB 区、位/字节/字/双字
- 验证连接/断开生命周期
- 验证多标签批量读写
- 将验证结果写入测试或文档
- 不做：修改 s7_adapter.py 逻辑、部署到生产、Factory I/O 集成

### 角色路径
```
Developer → Reviewer → Documenter
```

### 验收标准
- [ ] python-snap7 v3 成功连接 PLCSIM Advanced 实例
- [ ] M 区位/字节读写验证通过
- [ ] DB 区读写验证通过
- [ ] 连接/断开/重连生命周期正常
- [ ] 验证结果记录到测试或文档
- [ ] Reviewer 确认结果

### 实现清单（Developer）
- 确认 PLCSIM 实例状态（创建/启动 factoryio 实例）
- 编写连接验证脚本或测试
- 验证 S7 读写全流程
- 记录验证结果到 docs 或 findings

### 审查清单（Reviewer）
- 验证方法是否可靠？
- 是否有异常场景遗漏？
- 验证结果是否清晰记录？

---

## TS020 — 全仓端到端集成测试

### 目标
完成「后端 → 编排层 → MCP 服务器 → PLCSIM」全链路端到端验证。

### 依赖
- TS018 完成（robot-mcp snap7 回退已验证）
- TS019 完成（PLCSIM 连接已验证）

### 范围
- 启动编排层 + MCP 服务器 + PLCSIM 的全栈集成测试
- 验证 S7 监控工作流端到端（编排层 → plc-mcp-bridge → PLCSIM）
- 验证 TIA 流水线工作流（编排层 → tia-mcp → PLCSIM）
- 验证机器人工作流（编排层 → robot-mcp → PLCSIM snap7 回退）
- 验证前端 API → 编排层 → PLCSIM 全链路
- 编写集成测试（标记 `@pytest.mark.integration`，默认 skip）
- 不做：修改业务代码、引入新功能

### 角色路径
```
Developer → Reviewer → Documenter
```

### 验收标准
- [ ] S7 工作流端到端测试通过（编排层 → plc-mcp-bridge → PLCSIM）
- [ ] 机器人工作流端到端测试通过（编排层 → robot-mcp snap7 → PLCSIM）
- [ ] 集成测试标记为 `@pytest.mark.integration`，mock 测试不受影响
- [ ] 全部 mock 测试仍通过（orchestrator 221 / backend 261 / S7 30）
- [ ] Reviewer 确认集成测试方案合理

### 实现清单（Developer）
- 按 TS019 验证结果编写 PLCSIM 集成测试 fixture
- `test_end_to_end.py`：编排层 → MCP → PLCSIM 全链路测试（标记 integration）
- 运行现有全部 mock 测试确认无退化
- 记录集成测试结果

### 审查清单（Reviewer）
- 集成测试是否覆盖关键路径？
- mock 测试是否仍然独立（不依赖集成测试 fixture）？
- 安全链（SafetyGate）在集成模式是否验证？

---

## TS021 — 修复 TIA 流水线 pipeline 阻断 bug

### 目标
修复当前 TIA 全流水线（`tia_full_pipeline`）中三个阻断级 bug，让最小闭环（AI → SCL → 导入 → 编译）有机会跑通。

### 参考来源
- `软件/plc_-ai_-assist-main/Form1.cs` —— 导入 SCL 流程（CreateFromFile → GenerateBlocksFromSource）
- `软件/Siemens_SCL_外部源编程规范.md` 第 1.3 节 —— 重导前必须先删旧外部源
- 落地优化方案.md D-09 / D-02 / D-03 缺陷分析

### 范围
- **必须完成**：
  1. **D-09** — `generate_scl_code` 返回 `scl_code` 字符串，`import_scl_file` 接收 `scl_code`，`tia_full_pipeline` 步骤 3→4 数据契约统一
  2. **D-02** — TiaWorker 新增 `import-scl-replace` 命令（先删同名外部源 → CreateFromFile → GenerateBlocksFromSource）
  3. **D-03** — 写 `.scl` 文件前去除 BOM + 显式 UTF-8 无 BOM 编码
- **不做**：SCL 规范注入、编译错误结构化、多块依赖顺序、提示词优化

### 角色路径
```
Developer → Reviewer → Documenter
```

### 验收标准
- [ ] `generate_scl_code` 返回 `{scl_code: string, block_name: string, ...}`（非文件路径）
- [ ] `import_scl_file` 接受 `scl_code` 参数，不再强制要求文件路径
- [ ] `tia_full_pipeline` 步骤 3→4 使用 `scl_code` 直传（不依赖文件路径字段）
- [ ] TiaWorker `import-scl-replace` 命令可用，重复调用不报 `name not unique`
- [ ] 写 `.scl` 文件时首字节非 `EF BB BF`
- [ ] 所有修复有单元测试覆盖
- [ ] 现有的 617+ 测试全部通过（不退化）
- [ ] Reviewer 按 5 维度审查通过

### 实现清单（Developer）

**D-09 — 数据契约修复（`mcp-servers/tia-mcp/server.py` + `orchestrator/workflows/tia_full_pipeline.py`）：**
1. 确认 `generate_scl_code` 的返回值结构 → 改为统一返回 `{"scl_code": "...", "block_name": "...", ...}`
2. 确认 `import_scl_file` 的签名 → 增加 `scl_code: Optional[str] = None` 参数
3. 修复 `tia_full_pipeline.py` 步骤 3→4 传递字段名（`scl_code` 而非 `scl_path`）
4. 写测试验证数据契约（不 mock 关键路径）

**D-02 — import-scl-replace 命令（`TiaWorker/Program.cs`）：**
1. TiaWorker 新增命令解析分支 `import-scl-replace`
2. 封装：查 ExternalSources 是否存在同名块 → 存在则先删 → CreateFromFile → GenerateBlocksFromSource
3. `server.py` 映射新增 MCP 工具（或在现有 import_scl 中加 replace 选项）
4. 写单元测试（C# / Python 层）

**D-03 — BOM 防御（`mcp-servers/tia-mcp/server.py`）：**
1. 写 `.scl` 文件前加 `scl_code.lstrip("\ufeff")`
2. `File.write_text(..., encoding="utf-8")` 确保 UTF-8 无 BOM
3. 写单元测试验证

### 审查清单（Reviewer）
- D-09：新数据契约是否与 `generate_scl_code` 调用方兼容？
- D-02：`import-scl-replace` 是否正确处理"外部源不存在"的边缘情况？
- D-03：BOM 清除是否覆盖了所有写 .scl 路径？
- 测试是否覆盖正常 + 异常路径？
- 现有测试是否不受影响？

---

## TS022 — SCL 规范注入 AI 提示词 + 静态校验器

### 目标
提升 AI 生成 SCL 代码的编译通过率，让 10 个标准 prompt 的首次编译通过率 ≥ 80%。通过规范注入（前端约束）+ 静态校验（后端拦截）双重保障。

### 参考来源
- `软件/Siemens_SCL_外部源编程规范.md` 第 2-6 章 — V21 实测 SCL 铁律
- 落地优化方案.md L2-T1~L2-T4

### 范围
- **必须完成**：
  1. **规范抽取**：从 `软件/Siemens_SCL_外部源编程规范.md` 提取关键铁律 → `plc-code-templates/siemens-scl/_rules.md`（≤2000 token）
  2. **规范注入 AI**：`_gen_scl_via_deepseek` system prompt 加载 `_rules.md`，用户 prompt 末尾附加规范遵守指令
  3. **SCL 静态校验器**：`scl_lint.py`，在 `import_scl_file` 写盘前对 `scl_code` 做正则检查（至少 5 条规则）
  4. **lint 集成**：`import_scl_file` 调 `scl_lint`，失败返回 `{status:"error", lint_errors:[...]}`，不写盘不导入
- **不做**：编译错误结构化、AI 重试循环、多块依赖顺序、真实环境验证

### scl_lint 检查规则（至少实现 5 条）
1. `VAR_INPUT` / `VAR_IN_OUT` 内禁 `String[n]` / `WString[n]`
2. IEC 实例调用必须有 `#` 前缀（`#ton(IN:=..., PT:=...)` 而非 `ton(...)`）
3. `TSEND_C` / `TRCV_C` 不允许出现 `EN :=` 或 `ENO =>`
4. 不允许 `MB_CLIENT` 出现在外部源 SCL 中
5. `IF`/`CASE`/`FOR`/`WHILE`/`REPEAT` 成对闭合
6. 块调用 Output 形参用 `=>` 而非 `:=`

### 角色路径
```
Developer(Sonnet) → Reviewer(Opus) → Documenter(Flash)
```

### 验收标准
- [ ] `plc-code-templates/siemens-scl/_rules.md` 存在，包含 ≥ 10 条关键铁律，≤ 2000 token
- [ ] `_gen_scl_via_deepseek` 的 system prompt 加载 `_rules.md`
- [ ] `scl_lint.py` 实现 ≥ 5 条正则检查规则
- [ ] `import_scl_file` 写盘前调用 `scl_lint`，lint 失败不写盘不导入
- [ ] lint 失败返回 `{status:"error", lint_errors:["...", ...]}`
- [ ] 所有代码有单元测试覆盖
- [ ] 现有测试不退化
- [ ] Reviewer(Opus) 审查通过

### 实现清单（Developer）

**L2-T1 — 规范抽取：**
1. 创建 `plc-code-templates/siemens-scl/` 目录
2. 读 `软件/Siemens_SCL_外部源编程规范.md`，提取第 2-6 章关键铁律
3. 输出 `_rules.md`，内容为 AI 可直接读取的约束列表（每条一行，清晰明确）
4. 控制总 token ≤ 2000

**L2-T2 — 规范注入：**
1. `server.py` 中 `_gen_scl_via_deepseek` 的 system prompt 加载 `_rules.md` 文件
2. 用户 prompt 末尾追加"请严格遵守《外部源 SCL 规范》中的全部规则，违反任意一条均会导致 TIA Portal 编译失败"
3. 如果 `_rules.md` 文件不存在，优雅降级（不崩溃，仅 warn log）

**L2-T3 — SCL 静态校验器：**
1. 新建 `mcp-servers/tia-mcp/scl_lint.py`
2. 实现主函数 `lint_scl(scl_code: str) -> list[dict]`，返回 `[{"rule": "NO_STRING_LEN_IN_VAR", "line": 行号, "message": "描述"}]`
3. 至少实现 5 条检查规则（见上）
4. 每条规则返回行号方便定位

**L2-T4 — lint 集成：**
1. `server.py` 的 `import_scl_file` 在写 `.scl` 文件前调用 `scl_lint.lint_scl(scl_code)`
2. 有错误时返回 `{"status": "error", "lint_errors": [...]}`，不写盘
3. 写测试验证 lint 正确拦截违规代码、放过合法代码

### 审查清单（Reviewer）
- `_rules.md` 的规则是否准确对应 SCL 规范原文？
- `scl_lint` 的正则是否可能误判合法 SCL（假阳性）？
- lint 拦截是否足够早（在写盘前）？
- 降级路径是否合理（`_rules.md` 不存在时 AI 仍能工作）？
- 测试是否覆盖正常 + 异常路径？

---

## TS023 — 编译错误结构化 + AI 重试循环

### 目标
让 TIA 全流水线具备自我修复能力：编译失败时自动获取错误明细，回传 AI 修正，最多重试 3 次。

### 参考来源
- 落地优化方案.md L3-T1、L3-T2
- 缺陷 D-10：TiaWorker compile 返回 `errors=数量` 无错误明细

### 范围
- **必须完成**：
  1. **编译错误结构化**（L3-T1）：TiaWorker `compile` 命令返回 `{success, errors:[{line, file, text, severity}]}`
  2. **`tia_full_pipeline` 加重试循环**（L3-T2）：步骤 5 编译失败 → 取 errors 明细 → 拼 prompt → 重跑步骤 3→4→5，最多 3 次
- **不做**：多块依赖顺序（T024）、真实环境验证（T025）、scl_lint 扩展

### 角色路径
```
Developer(Sonnet) → Reviewer(Opus) → Documenter(Flash)
```

### 验收标准
- [ ] TiaWorker `compile` 命令返回结构包含 `errors` 列表，每项含 `line`/`file`/`text`/`severity`
- [ ] `tia_full_pipeline` 步骤 5 编译失败时自动获取错误明细
- [ ] 重试循环：错误回传 AI → 重跑生成+导入+编译，最多 3 次
- [ ] 3 次全部失败后返回完整错误日志（不无限重试）
- [ ] 编译通过时不触发重试
- [ ] 所有代码有单元测试覆盖
- [ ] 现有测试不退化
- [ ] Reviewer(Opus) 审查通过

### 实现清单（Developer）

**L3-T1 — 编译错误结构化（`TiaWorker/Program.cs`）：**
1. 读 `Program.cs` 中 `compile` 命令的现有实现
2. 调 TIA Portal 编译 API 后，获取编译器输出（`CompilerResult` 对象）
3. 提取错误明细：行号、文件名、错误文本、严重级别
4. 返回结构增强为：`{"ok": true, "result": {"success": true/false, "errors": [{"line": 5, "file": "FB_Motor.scl", "text": "语法错误...", "severity": "error"}, ...]}}`
5. 写 C# 单元测试验证结构化错误

**L3-T2 — tia_full_pipeline 加重试循环（`orchestrator/workflows/tia_full_pipeline.py`）：**
1. 修改 pipeline 步骤 5（编译）：调用 `compile` 后检查结果
2. 编译失败时解析 `errors` 列表，提取错误行号+文本
3. 拼重试 prompt：`"你之前生成的 SCL 有以下编译错误：\n[第5行] ...\n\n请修正后重新生成完整代码"`
4. 重新调用步骤 3→4→5，最多 3 次
5. 3 次失败后返回 `{status:"error", attempts:3, all_errors:[...], final_error:"..."}`
6. 编译通过时不触发重试

### 审查清单（Reviewer）
- 编译错误结构化是否完备？
- 重试循环是否有限次中止？
- 重试 prompt 是否包含足够上下文让 AI 定位问题？
- 测试是否覆盖正常 + 异常 + 边界路径？

---

## TS025 — 真实环境冒烟脚本

### 目标
编写可在真实 TIA V21 + PLCSIM Advanced 环境运行的冒烟脚本，验证最小闭环：AI 生成 SCL → 导入 → 编译 → 下载 → snap7 读到变量翻转。

### 范围
- **必须完成**：
  1. `scripts/e2e_smoke.py` — 端到端冒烟脚本，固定 prompt="三相异步电机正反转带急停和过载保护"
  2. 调用 `tia_full_pipeline` 工作流，打印每步结果
  3. 运行后 snap7 验证 PLC 变量
  4. 中文日志输出 + 每步耗时 + 失败明确提示
  5. 前置环境检查（TIA Portal 进程、PLCSIM、API Key）
- **不做**：多块场景、复杂业务逻辑、Factory I/O 集成

### 角色路径
```
Developer(Sonnet) → Reviewer(Opus)
```

### 验收标准
- [ ] `scripts/e2e_smoke.py` 存在可运行
- [ ] 固定 prompt 调用 `tia_full_pipeline` 工作流
- [ ] 前置检查：TIA Portal 进程 / PLCSIM / DeepSeek API Key
- [ ] 中文日志 + 每步耗时 + 成功/失败标志
- [ ] 编译通过后 snap7 读 PLC 变量验证
- [ ] 失败时给出明确错误提示和排查建议
- [ ] Reviewer(Opus) 审查通过

### 实现清单（Developer）
1. 建 `scripts/e2e_smoke.py`，导入 orchestrator 模块
2. 写 `check_prerequisites()`：检测 TIA Portal 进程、PLCSIM 连接、API Key
3. 写 `run_smoke()`：调 `tia_full_pipeline`，中文日志输出
4. 写 `verify_plc()`：调 snap7 读 M0.0 等变量验证
5. 写 `main()`：前置检查 → 运行 → 验证 → 报告
6. 根目录放 `scripts/__init__.py`（空文件）

---

## TS026 — 一键启动 + Demo 文档

### 目标
新机器 5 分钟内跑通 Demo。

### 范围
- **必须完成**：
  1. `start.bat` — 一键启动 5 个服务
  2. `scripts/preflight.py` — 前置环境检查
  3. `scripts/demo.py` — 固化 Demo 脚本（基于 e2e_smoke.py）
  4. `docs/quickstart-落地版.md` — 5 步文档
- **不做**：安装程序、docker 化、持续集成

### 角色路径
```
Developer(Sonnet) → Reviewer(Opus)
```

### 验收标准
- [ ] `start.bat` 启动 5 个服务 + 打开浏览器
- [ ] `preflight.py` 检测所有前置条件
- [ ] `demo.py` 中文日志 + 进度提示
- [ ] `docs/quickstart-落地版.md` 5 步文档
- [ ] Reviewer(Opus) 审查通过

---

## TS024 — 多块依赖顺序工作流

### 目标
实现按依赖顺序导入多个 PLC 程序块的工作流：UDT → 变量表 → 全局 DB → FC/FB/OB → 实例 DB → 编译。确保下游块引用上游 UDT/DB 时不会因顺序错误而失败。

### 参考来源
- 落地优化方案.md L3-T3
- `软件/Siemens_SCL_外部源编程规范.md` 第 1.4 节"声明依赖导入顺序"

### 范围
- **必须完成**：
  1. 新工作流 `tia_multi_block_pipeline`，接收按类型分类的块列表
  2. 按 `UDT → 变量表 → 全局 DB → FC/FB/OB → 实例 DB → 编译` 顺序导入
  3. 每步使用 `import-scl-replace` 支持重复导入
  4. 支持 3 块依赖场景（UDT `MotorParams` → 全局 DB `DB_Process` → FB `MotorCtrl`）
- **不做**：真实环境验证（T025）、通用 DAG 依赖解析、循环依赖检测

### 角色路径
```
Developer(Sonnet) → Reviewer(Opus) → Documenter(Flash)
```

### 验收标准
- [ ] `tia_multi_block_pipeline` 工作流注册并按依赖顺序导入
- [ ] 支持 UDT → 全局 DB → FC/FB/OB 三种块类型
- [ ] 每步使用 `import-scl-replace`，不报 `name not unique`
- [ ] 3 块依赖场景（UDT→DB→FB）测试通过
- [ ] 依赖顺序错误时给出明确错误信息
- [ ] 有测试覆盖
- [ ] 现有测试不退化
- [ ] Reviewer(Opus) 审查通过

### 实现清单（Developer）
1. 新建 `orchestrator/workflows/tia_multi_block_pipeline.py`
2. 设计输入格式：`{blocks: [{type:"UDT", name:"MotorParams", scl_code:"..."}, {type:"DB", name:"DB_Process", scl_code:"..."}, {type:"FB", name:"MotorCtrl", scl_code:"..."}]}`
3. 按依赖顺序排序：UDT(1) → 变量表(2) → 全局DB(3) → FC/FB/OB(4) → 实例DB(5)
4. 每步调 `import_scl_file(scl_code=..., block_name=..., replace=True)`，顺序执行
5. 全部导入完成后调 `compile`
6. 导入失败或编译失败时中止并返回错误

### 审查清单（Reviewer）
- 依赖顺序是否正确覆盖常见 PLC 工程场景？
- 导入或编译失败时是否有清晰的中止路径？
- 工作流是否与 `tia_full_pipeline` 合理共存？