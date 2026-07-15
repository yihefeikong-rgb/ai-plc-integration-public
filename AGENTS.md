# AGENTS.md — AI 接入 PLC

本文件是当前工作区的首要指令文件。`OpenCode.md` 不存在，不能作为路径、操作规则或安全边界的来源。

## 第一阶段协作层边界

当前只落地 **CCB + Codex + Claude Code 协作层 Phase 1**。

- 允许改动：`AGENTS.md`、`claude.md`、`.ccb/`、`.plans/ai-plc-integration/`、`.plans/ai-plc-integration/agents/`、`.plans/ai-plc-integration/bridge/`
- 禁止改动：`backend`、`frontend`、`docs`、`mcp-servers`、`edge-gateway`、`orchestrator`、`scripts`、`tests`
- 禁止触碰：业务代码、PLC 控制逻辑、S7 通信、TIA Openness、MCP 服务、前后端接口、前端页面
- 禁止行为：重构现有项目结构、移动/删除/重命名现有核心文件、启用 hooks、orchestrator、无人值守、自动轮询

本阶段只搭建规则文件、状态模板、Agent 协议和人工闭环文件。

## 第二阶段 A：离线红测临时授权

用户已于 2026-07-15 明确确认开始审查计划的执行。本节是对“第一阶段协作层边界”的**窄范围临时例外**，只用于由其他模型建立第一批失败契约测试；除本节列出的文件外，第一阶段限制继续有效。

- 允许修改：
  - `orchestrator/tests/test_nl_to_plcsim_live_contract.py`
  - `orchestrator/tests/test_mcp_credentials_contract.py`（允许新建）
  - `.plans/ai-plc-integration/refactor_phase2a_pipeline_auth_red_tests.md`
  - `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`（允许新建）
- 禁止修改：所有生产代码，包括 `orchestrator/*.py`、`orchestrator/workflows/*.py`、`backend`、`frontend`、`mcp-servers`、`safety`、`scripts` 和根 `tests/`。
- 只允许运行计划文件中列出的纯离线测试；禁止启动 TIA、PLCSIM、Factory I/O、MCP 子进程、后端服务或桌面程序。
- 本阶段目标是稳定复现失败，不得为了让测试通过而修改生产实现。
- 完成红测后必须停止并交回 Codex 审查；不得自动 `git add`、`commit`、`push`，不得扩大授权目录。

## 第二阶段 B：首批契约绿色实现授权

用户已于 2026-07-15 进一步明确授权 Codex 使用子代理实施并由 Codex 审核。第二阶段 B 只允许把第二阶段 A 的两组契约从 RED 推进到 GREEN：

- 允许修改：
  - `orchestrator/core.py`
  - `orchestrator/workflows/nl_to_plcsim_pipeline.py`
  - `orchestrator/registry.py`
  - `orchestrator/mcp_client.py`
  - `orchestrator/mcp_pool.py`
  - `orchestrator/server_configs.py`
  - `orchestrator/tests/test_nl_to_plcsim_live_contract.py`
  - `orchestrator/tests/test_api.py`
  - `orchestrator/tests/test_core.py`
  - `orchestrator/tests/test_mcp_credentials_contract.py`
  - `orchestrator/tests/test_mcp_pool.py`
  - `mcp-servers/robot-mcp/server.py`（仅允许修正认证令牌的环境默认值）
  - `mcp-servers/robot-mcp/test_simulated_backend.py`（仅允许增加认证默认值测试）
  - `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`
- 目标 1：把 `authenticated_operator` 从用户业务输入中分离为受信执行元数据，工作流白名单仍只校验业务字段。
- 目标 2：由 MCP adapter 在传输边界注入服务器凭据，拒绝调用者自带凭据，缺失凭据时在调用 session 前失败关闭，日志不得暴露令牌；连接池必须串行化断开与同名重连，避免旧、新 MCP 实例并存。
- 禁止修改：上述清单之外的生产代码、测试和配置；禁止顺手重构、统一所有工具返回类型或扩大到确认令牌、Robot、设备身份等后续阶段。
- 只允许运行纯离线单元/契约测试；禁止启动 TIA、PLCSIM、Factory I/O、真实 MCP 子进程、后端服务或桌面程序。
- 子代理不得执行 `git add`、`commit`、`push`；每个任务必须先看到对应测试按预期失败，再做最小实现并交回 Codex 双重审查。

## 快速命令

| 命令 | 操作 |
|------|------|
| `D:/Python3/python.exe scripts/preflight.py --json` | 只读环境门槛检查；不等同于下载或 PLC 可读 |
| `D:/Python3/python.exe -m pytest` | 默认只收集/运行离线测试，已排除硬件、桌面和网络标记 |
| `start.bat` | 启动本地后端；其内嵌 orchestrator 是 MCP 子进程的唯一生命周期所有者 |
| `D:/Python3/python.exe scripts/p3_flow.py` | 可能恢复、下载或启动仿真；仅在隔离目标、人工确认后使用 |

已移除不存在的 `start_all.py`、`run_gateway.py`、`auto_full_pipeline.py` 和 `scripts/launch_factory_io.py` 命令。不得把本文档中的命令视为连接真实 PLC 的授权。

## 关键架构事实

- **唯一控制目标**：`mcp-servers/tia-mcp/config.yaml` 的 `target` 节是 V21、`demo_V21.ap21`、`factoryio` 和 `192.168.0.110` 的唯一来源；`validate_control_target()` 发现漂移即阻断。
- **项目根路径**：`config_loader.py:23` — `_PROJECT_ROOT = Path(__file__).parent.parent.parent`
- **TIA 通信链**：`server.py(FastMCP) → JSON 临时文件 → TiaWorker.exe(C# .NET Framework 4.8) → TIA Openness DLL`
- **下载策略优先级（V21）**：`TiaWorker(C#, headless) → Python API(GUI) → UI Automation → 手动`
- **LAD 生成链**：`自然语言 → DeepSeek → LadderSpec JSON → CartGen(.NET 8) → SimaticML XML → 导入 TIA`
- **TiaWorker.csproj** 目标 .NET Framework 4.8（编译到 `bin/`）；**CartGen.csproj** 目标 net8.0
- **TIA Portal 版本**: V21（2023），模块化 DLL 加载路径已适配
- **PLCSIM Advanced 版本**: V8.0（向后兼容 V5.0+ API）
- `.env` 可覆盖配置变量，但空值不会覆盖安全默认值；任何 V18、旧项目、实例名或 IP 漂移都会被目标契约拒绝。

## 已知 Bug

- **ConveyorControl FB501** 已在 TIA 项目中但**未在 OB1 中调用**，下载后传送带不会响应
- **TIA 每次下载需重新扫描设备**（西门子已知行为，非缺陷）
- **TCP/IP 模式**: 需先安装 PLCSIM 虚拟网卡（VirtualSwitchMisconfigured）
- **ConveyorControl FB501**：历史记录称其未在 OB1 调用；当前仓库未完成真实 TIA 验证，不能据此判断现场状态。
- **Factory I/O / PLCSIM**：TCP/IP、Softbus、自动连接和场景启动均未在本次修复中动态验证；不得作为部署结论。
- **机器人、OPC UA、三菱 MCP**：没有经过真实硬件验收。
- **缓存清理**：不要执行递归删除命令作为常规修复步骤；先确认程序已关闭、目标路径和影响范围。

## PythonNET 注意事项

- **PythonNET 3.0+** 调用 PLCSIM API 时必须用枚举类型，不能用 int 隐式转换。正确写法：`instance.Interface = SimulationInterface.TCPIP` 而非 `instance.Interface = TCPIP`

## 已有指令文件（优先级从上到下）

- **`AGENTS.md`** — 当前工作区指令与安全边界。
- **`claude.md`** — 历史项目总纲；与代码冲突时以代码、配置和测试为准。
- `.plans/ai-plc-integration/docs/invariants.md` — 不可破坏约束。

`OpenCode.md` 当前不存在，不能作为规则或命令来源。

---

## Project Brain 读取顺序

新会话恢复上下文时，按以下顺序读取 `.plans/ai-plc-integration/` 下文件：

1. `handoff.md` — 上次交接状态
2. `task_plan.md` — 当前路线图
3. `progress.md` — 最新进度
4. `findings.md` — 已有结论
5. `decisions.md` — 架构决策
6. `tech_debt.md` — 技术债务
7. `risks.md` — 项目风险
8. `docs/architecture.md` — 架构真相
9. `docs/api-contracts.md` — API 契约
10. `docs/invariants.md` — 不可破坏约束

> 每次会话结束时，Documenter 负责更新 `handoff.md`。
