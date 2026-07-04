# Agent Protocol

## 参与角色

- Team Lead：决定是否开始一轮协作
- Codex：准备任务包、整理结果、执行人工审阅
- Claude Code：根据任务包产出结果
- Reviewer：在需要时给出独立人工审查意见
- Documenter：同步状态与交接说明

## 文件协议

### 模板文件（`templates/`，纳入 Git，内容固定）
1. `templates/task_packet.md` — 任务包空模板
2. `templates/claude_result.md` — 执行结果空模板
3. `templates/codex_review.md` — 审查结果空模板
4. `templates/next_action.md` — 下一步动作空模板

### 运行态文件（`runs/{run_id}/`，不纳入 Git）
1. `runs/{run_id}/task_packet.md` — 本轮实际任务包
2. `runs/{run_id}/claude_result.md` — 本轮执行结果
3. `runs/{run_id}/codex_review.md` — 本轮审查结论
4. `runs/{run_id}/next_action.md` — 本轮下一步

### 根目录状态文件
1. `state.json` — 当前状态源（含 `run_id` 字段指向本轮 runs/ 子目录）
2. `lock.json` — 占位锁，不启用自动加锁

## 状态流

`IDLE` → `RESEARCH` → `DEVELOP` → `REVIEW` → `DOCUMENT` → `DONE`

第一阶段只定义格式，不强制自动流转。
