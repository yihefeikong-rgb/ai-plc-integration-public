# 任务路线图 — AI 接入 PLC

> 最后更新：2026-06-23
> 原则：只放路线图，不放大段细节。详细内容见 `docs/` 目录。

---

## 当前迭代（2026-06-23 ~ ）

### Slice P1: CCB + Codex + Claude Code 协作层落地 ✅
- 目标：只在项目根目录内补齐第一阶段协作层文件，不进入业务代码目录
- 允许文件：`AGENTS.md`、`claude.md`、`.ccb/`、`.plans/ai-plc-integration/`、`.plans/ai-plc-integration/agents/`、`.plans/ai-plc-integration/bridge/`
- 禁止文件：`backend`、`frontend`、`docs`、`mcp-servers`、`edge-gateway`、`orchestrator`、`scripts`、`tests`
- 实现步骤：
  1. 建立 `.ccb/` 最小规则文件
  2. 建立 `bridge/` 状态文件与空模板
  3. 收紧 `AGENTS.md`、`claude.md`、`agents/*.md` 的第一阶段边界
  4. 更新 `handoff.md` 记录当前阶段状态
- 验证：
  - 仅出现协作层文件 diff
  - `bridge/state.json` 与 `bridge/lock.json` 为最小初始状态
  - 不存在 hooks、orchestrator、无人值守接入
- 验收标准：可由人工按 `bridge/runs/{run_id}/task_packet.md` → `bridge/runs/{run_id}/claude_result.md` → `bridge/runs/{run_id}/codex_review.md` → `bridge/runs/{run_id}/next_action.md` 跑通一轮闭环

### Slice P2: Bridge v1 runners ✅
- `runner_dry_run.py`：只读状态、stdout prompt、支持停止态
- `runner_step.py`：受控单步 `--execute`，需 `YES` 确认
- `runner_step.py --copy`：cc-haha GUI 兼容模式，只复制 prompt 到剪贴板
- 安全边界：
  - 不自动循环
  - 不自动重试
  - 不自动修改 bridge 运行态文件
  - 不自动 git 操作
  - 不进入无人值守

### 当前待决
- 是否继续推进 Bridge v2（如模板/运行态拆分、提交前清单、更多 GUI 兼容）
- 是否回到主项目业务路线（TIA / Factory I/O / RBAC）

### Slice 1: 项目骨架建立 ✅

- 建立 .plans/ 目录结构 + 4 agent 角色文件
- 写入 CLAUDE.md 运营规则
- 验收：新 agent 能在 5 分钟内从文件系统理解项目全貌

### Slice 2: AI PLC Assistant 后端测试基础
- 目标：为 33 个 API 端点建立 pytest 基础测试
- 涉及文件：`ai-plc-assistant/backend/tests/`（新建目录）
- 涉及模块：chat / knowledge / search / generate / prompts / conversations / projects / settings
- 依赖：Slice 1
- 实现步骤：
  1. researcher 确认后端路由结构和现有测试模式
  2. developer 创建 conftest.py（FastAPI TestClient + mock LLM）
  3. developer 按模块写测试（chat → knowledge → generate → 其他）
  4. reviewer 审查测试覆盖率和质量
- 测试方式：`D:/Python3/python.exe -m pytest ai-plc-assistant/backend/tests/ -v`
- 验收标准：核心路径覆盖率 80%+，所有测试通过
- 回滚办法：删除 `ai-plc-assistant/backend/tests/` 目录

### Slice 3: 安全复核机制验证
- 目标：验证 reviewer 独立审查流程能正常工作
- 涉及文件：`safety/` 目录下所有文件
- 依赖：Slice 1
- 实现步骤：
  1. researcher 列出 safety/ 目录所有文件及其职责
  2. developer 选取一个安全模块写测试用例（如 validator_interlock.py）
  3. reviewer 独立审查该变更（按 5 维度打分）
  4. team-lead 验收复核流程是否完整
- 测试方式：`D:/Python3/python.exe -m pytest tests/test_safety*.py tests/test_validator*.py -v`
- 验收标准：完成一次完整的 developer → reviewer → team-lead 闭环
- 回滚办法：git revert

### Slice 4: 前端组件测试
- 目标：React 关键组件的 vitest 单元测试
- 涉及文件：`ai-plc-assistant/frontend/src/components/ChatArea.jsx`、`Sidebar.jsx`、`SettingsPanel.jsx`
- 依赖：Slice 1
- 实现步骤：
  1. researcher 确认前端测试工具链（vitest 配置）
  2. developer 写 3 个组件的渲染测试
  3. reviewer 审查
- 测试方式：`cd ai-plc-assistant/frontend && npx vitest run`
- 验收标准：3 个组件至少各有基础渲染测试
- 回滚办法：删除测试文件

---

## 待规划

### V1.x 迭代
- RAG 嵌入模型升级（bge-m3）
- 工程搜索中文分词（jieba）
- Playwright E2E 测试
- 代码 Diff 视图

### V2.0
- TIA Openness 深度集成
- AI Agent 直连 PLC 运行态
- RBAC 权限控制
- 统一编排层 (Phase 5)

---

## 已完成

| 切片 | 完成日期 | 提交 |
|------|---------|------|
| 全仓审查修复 (58 A级) | 2026-06-20 | fbb1659 |
| 梯形图 SVG 可视化 | 2026-06-18 | cfaa19c |
| 后端 pytest 基础测试 (39用例) | 2026-06-18 | fac5f5d |
