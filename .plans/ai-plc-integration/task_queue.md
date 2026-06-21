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
| T003 | TiaWorker C# 核心测试 | IN_PROGRESS | developer | 4+ 核心命令有测试、dotnet test 通过 | TS003 |
| T004 | 扩展 TIA MCP 工具映射 + FB501 自动调用 | PENDING | developer | 新增工具可用、FB501 自动调用验证 | TS004 |
| T005 | 启动 Phase 5 统一编排层 | PENDING | team-lead | Phase 5 范围明确、骨架/设计完成 | TS005 |