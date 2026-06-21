# 架构决策记录 — AI 接入 PLC

> 原则：记录架构选择、取舍和原因。每个决策包含日期、背景、选项、选择、理由。

---

## D-001：选择 CCteam-creator 作为执行层

- **日期**：2026-06-22
- **背景**：项目已有 7 个顶层文档，任务跟踪靠 TODO.md，无复核机制，会话间上下文丢失严重
- **选项**：
  - A. 继续当前 ad-hoc 方式（不引入额外结构）
  - B. 引入 CCteam-creator 的 .plans/ + agent 分工 + 文件化流程
  - C. 迁移到 Reasonix 或其他工具
- **选择**：B — 引入 CCteam-creator 执行层
- **理由**：
  - 不依赖外部工具，纯文件系统驱动，任何 agent 都能接
  - 与现有 CLAUDE.md 机制兼容，增量接入而非推倒重来
  - 文件化流程天然适合 git 版本控制

## D-002：项目名使用 `ai-plc-integration`

- **日期**：2026-06-22
- **背景**：.plans/ 目录需要项目名，仓库实际名为 `ai-plc-integration`
- **选择**：`.plans/ai-plc-integration/`
- **理由**：与 GitHub 仓库名一致，避免混淆

## D-003：最小团队 4 角色

- **日期**：2026-06-22
- **背景**：CCteam-creator 支持 6 个角色，但当前项目规模不需要全配
- **选择**：team-lead + researcher + developer + reviewer（4 角色）
- **理由**：
  - 暂不需要独立 e2e-tester（Playwright 测试在 V1.x 才启动）
  - 暂不需要独立 custodian（代码清理频率低）
  - 4 角色已覆盖 generator-evaluator 分离 + 独立研究 + 任务分派

## D-004：不迁移现有文档，改为索引

- **日期**：2026-06-22
- **背景**：7 个顶层文档内容丰富，但重叠
- **选择**：保留现有文档不动，.plans/docs/ 作为索引和补充
- **理由**：
  - 避免大规模文档迁移引入风险
  - 现有文档已通过 git 历史追踪
  - .plans/docs/ 专注"agent 需要快速读取的真相"

## D-005：引入 Documenter 角色 + 扩展 Project Brain

- **日期**：2026-06-22
- **背景**：GPT 反馈指出项目核心问题是知识无法沉淀，需要独立 Documenter 角色和 handoff/tech_debt/risks 文件
- **选择**：
  - 新增 `Documenter` 角色（Sonnet / DS V4 Pro）
  - 创建 `handoff.md` 作为会话交接标准格式
  - 创建 `tech_debt.md` 记录技术债务
  - 创建 `risks.md` 记录项目/依赖/许可证/模型风险
  - 更新 `CLAUDE.md` 和 `AGENTS.md`，将 Project Brain 作为会话恢复第一入口
- **修正（同一会话）**：
  - 运行测试后发现 `ai-plc-assistant/backend/tests/` 已有 250 个测试，并非零测试
  - 修正 `findings.md` 和 `tech_debt.md` 中"AI PLC Assistant 零测试"为"后端测试有损坏用例"
- **理由**：
  - 文档更新不能依赖 developer 自觉，必须有独立角色负责
  - `handoff.md` 能让新会话在 5 分钟内恢复上下文
  - 技术债务和风险单独成册，避免散落在 TODO 和聊天记录中
  - Project Brain 先于 Agent Team 完善，后续换模型/换 CLI 不会丢失上下文
## D-006：持久化 Team OS 调度机制（CLAUDE.md 核心宪法）

- **日期**：2026-06-22
- **背景**：
  - 发现换对话后 Agent 不再调度角色，而是自己埋头干
  - 仅靠 Prompt 提醒无法持久化行为约束
  - 需要一套"换对话也不失效"的调度机制
- **选项**：
  - A. 每次新对话手动发送调度 Prompt
  - B. 将核心调度规则写入 CLAUDE.md，利用其强制读取机制
  - C. 引入外部配置文件或 MCP 工具
- **选择**：B — 将"核心宪法"和"状态机逻辑"硬编码到 CLAUDE.md
- **理由**：
  - Claude Code 启动时强制读取项目根目录下的 CLAUDE.md
  - 写入 CLAUDE.md 的规则变成了"基因"，换对话、重启终端都有效
  - 无需外部依赖，纯文件系统驱动
- **实现**：
  - 在 CLAUDE.md 顶部添加【Team OS 核心宪法】章节
  - 定义四阶段状态机：Research → Develop → Review → Document
  - 定义启动协议（Bootstrap Protocol）：每次会话先读 task_queue.md 和 progress.md
  - 定义越权禁令：严禁未拆分任务直接写代码、严禁一步多做
  - 定义状态文件为唯一真实来源
- **后续使用**：
  - 每天开始工作：`Claude, resume state.`
  - 添加新需求：先加入 task_queue.md，再开始 Phase 1 (Research)

## D-007：TS004 完成 — TIA MCP 工具链扩展

- **日期**：2026-06-22
- **背景**：Phase 3 TIA 工程态需要完整的 MCP 工具链，但 server.py 只有 9 个工具，缺少块管理、在线连接等核心功能
- **选择**：
  - 新增 6 个高优先级 MCP 工具（list_blocks, create_block, export_block, list_udts, go_online, go_offline）
  - 新增 `call_fb_in_ob1` 工具，实现 FB 自动调用到 OB1
  - 修复 layout_engine.py 分支叠加 bug
- **理由**：
  - TiaWorker 已支持这些命令，只需映射到 MCP 工具
  - FB501 自动调用是 Phase 3 最后的功能缺口
  - 梯形图分支布局 bug 影响可视化输出质量
- **结果**：
  - MCP 工具从 9 个扩展到 16 个
  - layout_engine.py 分支布局修复
  - Phase 3 完成度从 90% 推进到 98%

## D-008：Phase 5 统一编排层 — 最小可行骨架

- **日期**：2026-06-22
- **背景**：
  - 项目已有 7 个 MCP 服务器（plc-mcp-bridge, tia-mcp, opcua-mcp, modbus-mcp, mitsubishi-mcp 等），总计 ~116 个工具
  - 无统一编排层，跨模块耦合严重（如 TIA 下载流程需要手动串联多个 MCP 工具调用）
  - 安全链多头治理：validator、shadow_simulator、audit 散落在不同模块中，无统一拦截点
  - 需要一套轻量级编排机制来串联多步骤工作流
- **选项**：
  - A. 引入重量级工作流引擎（如 Temporal、Prefect、Airflow）
  - B. 创建独立 `orchestrator/` 模块，装饰器风格工作流注册 + 统一安全拦截点
  - C. 在每个 MCP 服务器内部各自实现编排逻辑
- **选择**：B — 创建独立 `orchestrator/` 模块，最小可行骨架先行
- **理由**：
  - 不引入重量级外部依赖（Temporal 需要独立服务部署，Prefect 需要额外基础设施）
  - 装饰器 `@workflow` 风格简单直观，学习成本低，适合中小规模工作流
  - 统一安全拦截点（`safety_gate.py`）将 validator + shadow_simulator + audit 收敛到一处，消除多头治理
  - 独立模块不侵入现有 MCP 服务器代码，后续接入时只需注册工具和工作流
  - 先骨架后集成：当前只实现引擎 + 一个示例工作流（tia_download），后续逐步将现有 MCP 服务器接入
- **实现**：
  - `core.py`：`@workflow` 装饰器 + `Context` 类（状态追踪、步骤记录）
  - `safety_gate.py`：`SafetyGate` 类统一封装安全检查（写前验证、影子仿真、审计日志）
  - `registry.py`：`MCPRegistry` 类管理服务器和工具注册
  - `workflows/tia_download.py`：示例 4 步工作流（TIA 生成 SCL → 导入 → 编译 → 下载）
- **后果**：
  - 后续需将现有 MCP 服务器（plc-mcp-bridge, tia-mcp 等）逐一接入编排层
  - 当前为最小骨架，未覆盖的工作流需逐步添加（如 OPC UA 监控、Modbus 采集等）
  - 安全拦截点已统一，但需要在实际接入时验证不绕过安全链
  - 53 个测试全部通过，覆盖核心引擎和安全拦截点

