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
| T001 | 初始化 Team OS 工作流 | IN_PROGRESS | team-lead | task_queue.md / task_spec.md / CLAUDE.md / 角色文件已更新，且最小 slice 跑通 | TS001 |