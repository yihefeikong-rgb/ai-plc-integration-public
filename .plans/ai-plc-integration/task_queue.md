# Task Queue — AI 接入 PLC

> **唯一入口**: 任何新任务必须先进入本队列，禁止口头临时加活。

## 队列规则
1. 新任务由 team-lead 追加到表尾。
2. 只有表头任务为 `IN_PROGRESS`；其余为 `PENDING`、`BLOCKED` 或 `DONE`。
3. 每个任务必须关联一个 `task_spec.md` 中的条目编号。
4. 任务状态变更必须由 team-lead 或 Documenter 更新。
5. 禁止直接跳过队列处理需求。

## 队列

| ID | 标题 | 状态 | 责任人 | 验收标准 | 关联 task_spec |
|----|------|------|--------|----------|----------------|
| T001 | 初始化 Team OS 工作流 | DONE | team-lead | task_queue.md / task_spec.md / CLAUDE.md / 角色文件已更新，且最小 slice 跑通 | TS001 |
| T002 | Phase 3 Python 层测试 + P1 修复 | DONE | developer | server.py 9 个工具 mock 测试通过、p3_flow 解析修复、gen_io_map/create_plc_tags 测试通过 | TS002 |
| T003 | TiaWorker C# 核心测试 | DONE | developer | 4+ 核心命令有测试、dotnet test 通过 | TS003 |
| T004 | 扩展 TIA MCP 工具映射 + FB501 自动调用 | DONE | developer | 新增工具可用、FB501 自动调用验证 | TS004 |
| T005 | 启动 Phase 5 统一编排层 | DONE | team-lead | Phase 5 范围明确、骨架/设计完成 | TS005 |
| T006 | P5 编排层启动引导（Bootstrap） | DONE | developer | 自动连接所有配置服务器 + 工作流自动注册 | TS006 |
| T007 | S7 读写安全工作流 | DONE | developer | 替代 edge-gateway 核心的采集→AI→安全→写入闭环 | TS007 |
| T008 | TIA 全流水线跨服务器工作流 | DONE | developer | 跨 plc-mcp-bridge + tia-mcp 的端到端流水线 | TS008 |
| T009 | desktop-mcp 接入 + 工具分类 | DONE | developer | desktop-mcp 配置补全 + 工具按用途分类 | TS009 |
| T010 | FastAPI 入口点 | DONE | developer | 编排层 HTTP API，暴露工作流执行/状态查询/工具列表 | TS010 |
| T011 | 编排层 API 集成到桌面应用 | DONE | developer | orchestrator 路由挂载到 ai-plc-assistant 后端 + 监控数据端点 | TS011 |
| T012 | 机器人 Pick&Place 编排工作流 | DONE | developer | 编排层 robot_pick_place 工作流 + 安全验证 | TS012 |
| T013 | robot-mcp 模拟后端模式 | DONE | developer | 无硬件模拟模式，可在本地模拟机器人全部 7 个工具 | TS013 |
| T014 | 机器人安全规则扩展 + SafetyGate 集成 | DONE | developer | interlock-rules 新增机器人规则 + 编排层 SafetyGate 机器人场景验证 | TS014 |
| T015 | 前端 API 层 + Dashboard 状态条 + Tab 注册 | DONE | developer | api.js 编排层函数 + Dashboard 服务器状态卡片 + App.jsx 注册新 Tab | TS015 |
| T016 | 编排面板（OrchestratorPanel） | DONE | developer | 工作流列表/执行/结果展示 + 工具/服务器列表 | TS016 |
| T017 | 机器人控制面板（RobotPanel） | DONE | developer | 模拟 Pick&Place 可视化 + 实时状态 + 手动控制 | TS017 |
---

## TS004 验证记录

TS004 已完成验证，包含以下交付物：

### 新增 MCP 工具（7 个）
1. `list_blocks` — 列出 TIA 项目中的程序块（FB/FC/DB/SFB/SFC）
2. `create_block` — 在 TIA 项目中创建空程序块
3. `export_block` — 导出 TIA 项目中的程序块为 SCL/DB 文件
4. `list_udts` — 列出项目中所有 UDT 数据类型
5. `go_online` — 建立与 PLC 的在线连接
6. `go_offline` — 断开与 PLC 的在线连接
7. `call_fb_in_ob1` — 在 OB1 中自动调用指定的 FB

### Bug 修复
- `layout_engine.py` 分支叠加 bug 修复（分支行 Y 坐标正确累加）

### 文件变更
- `mcp-servers/tia-mcp/server.py`：新增 7 个工具（+102 行）
- `mcp-servers/tia-mcp/layout_engine.py`：分支叠加 bug 修复（+3 行）

### 验证状态
- [x] server.py 语法验证通过（16 个 MCP 工具）
- [x] 新增工具功能验证通过（mock 测试）
- [x] progress.md 已更新
- [x] handoff.md 已更新
