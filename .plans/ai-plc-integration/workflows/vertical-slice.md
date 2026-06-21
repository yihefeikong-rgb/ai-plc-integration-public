# Vertical Slice Workflow — AI 接入 PLC

> 本文件描述一个任务从入队到完成的完整流程。team-lead 必须按此流程执行，不得跳过步骤。

## 阶段 0: 入队
1. 用户提出需求。
2. team-lead 将需求拆分为 vertical slice。
3. team-lead 在 `task_queue.md` 追加任务，状态 `PENDING`。
4. team-lead 在 `task_spec.md` 创建对应条目（如 TS002）。

## 阶段 1: 研究
1. team-lead 将任务状态改为 `IN_PROGRESS`。
2. team-lead 分派 Researcher："请研究 TSxxx，输出 findings"。
3. Researcher 只读代码/文档，更新 `findings.md`。
4. Researcher 向 team-lead 报告：研究完成 / 需要补充信息 / 发现阻塞。

## 阶段 2: 开发
1. team-lead 确认 findings 足够后，分派 Developer："请按 TSxxx 实现，遵循 TDD"。
2. Developer 基于 `task_spec.md`、`findings.md`、docs 写代码和测试。
3. Developer 完成标准：测试通过、文档同步、无 invariant 违反。
4. Developer 向 team-lead 请求 Reviewer。

## 阶段 3: 审查
1. team-lead 分派 Reviewer："请审查本次变更，按 5 维度打分"。
2. Reviewer 只读 diff、task_spec、invariants、findings。
3. Reviewer 输出 STRONG / ADEQUATE / WEAK 结论及阻塞点。
4. 若为 WEAK，返回 Developer 修复；若为 STRONG/ADEQUATE，进入阶段 4。

## 阶段 4: 文档同步
1. team-lead 分派 Documenter："请同步本次 slice 的文档和进度"。
2. Documenter 更新 `progress.md`、`handoff.md`、相关 docs。
3. Documenter 报告完成。

## 阶段 5: 关闭
1. team-lead 将 `task_queue.md` 中该任务状态改为 `DONE`。
2. team-lead 输出 `Project Brain Initialized`（仅当 Team OS 初始化 slice 完成时）。
3. team-lead 等待人工确认，不继续开发功能。

## 强制检查点
- 每个阶段结束时，team-lead 必须确认：输出文件是否落在该角色的 allowed outputs 内？
- 任一阶段缺失 required output → 视为失败，不得进入下一阶段。
- 主对话不得代替任何角色补输出。