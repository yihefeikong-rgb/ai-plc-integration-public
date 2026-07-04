# Change Policy

## 第一阶段允许范围

- `AGENTS.md`
- `claude.md`（文档内部统一称为 `CLAUDE.md`）
- `.ccb/`
- `.plans/ai-plc-integration/`
- `.plans/ai-plc-integration/agents/`
- `.plans/ai-plc-integration/bridge/`

## 第一阶段禁止范围

- `backend`
- `frontend`
- `docs`
- `mcp-servers`
- `edge-gateway`
- `orchestrator`
- `scripts`
- `tests`

## 第一阶段禁止动作

- 修改业务代码
- 修改 PLC 控制逻辑
- 修改 S7 通信
- 修改 TIA Openness
- 修改 MCP 服务
- 修改前后端接口和页面
- 重构现有项目结构
- 移动、删除、重命名现有核心文件
- 启用 hooks、orchestrator、自动轮询、无人值守

## 执行原则

- 只做最小必要改动
- 只补齐协作闭环文件
- 任何超出范围的需求都必须先人工确认

## Phase 3A 补充规则

- 允许存在单步 dry-run runner，但仅限协作层目录
- dry-run runner 只允许读取 `state.json` 并输出建议文本
- 禁止在 Phase 3A 调用 Codex CLI、Claude Code CLI 或任何外部 agent
- 禁止实现自动循环、自动提交、自动状态推进
- 遇到 `DONE`、`BLOCKED`、`SAFETY_BLOCK` 必须停止并等待人工确认

## Phase 5 补充规则

- 允许存在受控单步执行器 `runner_step.py`，但仅限协作层目录
- 默认 dry-run，仅展示执行摘要，不调用任何 CLI
- 仅当显式传入 `--execute` 并经人工输入 `YES` 确认后才允许调用 CLI
- 当前 MVP 仅支持 `NEED_CLAUDE` 状态真实调用 Claude Code
- CLI 命令必须从环境变量读取（`CLAUDE_CODE_CMD`），缺失时必须清晰报错
- `DONE` / `BLOCKED` / `SAFETY_BLOCK` 必须拒绝执行，不得调用 CLI
- 禁止自动修改 `state.json` 等任何桥接文件
- 禁止自动 git add / commit / push
- 禁止自动循环、自动重试、自动调用多个 Agent
- 不允许以此进入 Phase 3B 或无人值守执行

## Phase 5.1B 补充规则

- 允许 `runner_step.py` 存在 `--copy` 模式，仅复制 prompt 到系统剪贴板
- `--copy` 模式仅使用 Windows 系统工具 `clip.exe`，不得调用任何外部 Agent
- `--copy` 模式不得自动打开 cc-haha、控制 GUI、模拟键盘鼠标、自动发送消息
- `--copy` 模式不得修改 `state.json` 等任何桥接文件
- `--copy` 模式不得执行 git add / commit / push
- `DONE` / `BLOCKED` / `SAFETY_BLOCK` 停止态下，`--copy` 只输出停止建议，不得复制执行型 prompt
- cc-haha 桌面版用户推荐使用 `--copy` 而非 `--execute`
