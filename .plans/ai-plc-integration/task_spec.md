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

### 文档同步（Documenter）
- 更新 `progress.md`：Team OS v1 初始化完成。
- 更新 `handoff.md`：等待人工确认，不继续开发功能。