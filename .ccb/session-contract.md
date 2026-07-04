# Session Contract

## 目标

在现有 `AI 接入PLC` 项目根目录内，为 Codex 与 Claude Code 提供一个可人工执行、可审阅、可恢复的协作闭环。

## 角色约定

- Codex：负责读取状态、准备任务包、执行文件改动、产出审阅请求
- Claude Code：负责基于任务包给出实现或结果说明
- Codex Review：负责回读结果、做人工审阅、决定下一步动作

## 第一阶段限制

- 只允许修改协作层文件
- 不进入业务代码目录
- 不启用 hooks、orchestrator、自动轮询、无人值守
- 不伪造未知配置文件

## 交接顺序

1. Codex 读取 `bridge/state.json`（含 `run_id`）
2. Codex 填写 `bridge/runs/{run_id}/task_packet.md`
3. Claude Code 回填 `bridge/runs/{run_id}/claude_result.md`
4. Codex 回填 `bridge/runs/{run_id}/codex_review.md`
5. Codex 更新 `bridge/runs/{run_id}/next_action.md`
6. 人工决定是否进入下一轮

## 成功标准

- 每一步都有文件落点
- 状态变化可在 `state.json` 中追踪
- 下一步动作可由人工直接执行
