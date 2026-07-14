# Agent Protocol

## 参与角色

- Team Lead：决定是否开始一轮协作。
- Codex：准备任务包、整理结果、生成审查草案。
- Claude Code：根据任务包产出结果。
- Human Reviewer：检查产物，并通过 `ack_review.py` 作出最终 PASS 或 BLOCK。
- Documenter：同步状态与交接说明。

## 文件协议

### 模板文件（`templates/`，纳入 Git，内容固定）

1. `templates/task_packet.md` — 任务包空模板。
2. `templates/claude_result.md` — 执行结果空模板。
3. `templates/codex_review.md` — 审查结果空模板。
4. `templates/next_action.md` — 下一步动作空模板。

### 运行态文件（`runs/{run_id}/`，不纳入 Git）

1. `runs/{run_id}/task_packet.md` — 本轮实际任务包。
2. `runs/{run_id}/claude_result.md` — 本轮执行结果；其 SHA-256 写入 `state.json`。
3. `runs/{run_id}/codex_review.md` — 本轮审查草案或人工审查结论；最终确认时记录其 SHA-256。
4. `runs/{run_id}/next_action.md` — 人工确认后的下一步。

### 根目录状态文件

1. `state.json` — 唯一持久状态源，含当前 `run_id`。
2. `state.json.lock` — 运行时互斥锁，由 `bridge_state.py` 用独占创建和正常退出清理；出现遗留锁时必须先人工确认没有活动运行者，不能静默抢占。

`lock.json` 已移除，不能再作为锁或状态来源。

## 状态流

```text
NEED_CODEX_PLAN → NEED_CLAUDE → NEED_CODEX_REVIEW → DONE
                                      ├→ BLOCKED
                                      └→ SAFETY_BLOCK
```

允许的活动状态只有 `NEED_CODEX_PLAN`、`NEED_CLAUDE`、`NEED_CODEX_REVIEW`；停止状态只有 `DONE`、`BLOCKED`、`SAFETY_BLOCK`。状态枚举只在 `bridge_state.py` 中定义。

## 不可绕过的审查规则

1. 创建或复用 sidecar 会话后，必须回读其 CWD 和权限模式；不能验证即停止。
2. 结果文件和审查文件必须位于当前 `run_id` 的目录中，且不能是符号链接。
3. `ack_review.py` 只接受当前 `NEED_CODEX_REVIEW` 状态、匹配的 run ID、未被篡改的结果哈希、非空审查产物和 `human:<reviewer-id>` 审查人。
4. 只有 `stop_rule=NONE` 的运行可标记为 PASS；超时、权限拒绝、会话异常或元数据未验证必须 BLOCK。
5. 每次状态读改写都必须持有 `state.json.lock`，并以原子替换保存。
6. `supervised_batch.py` 仅在已完成的 `DONE + PASS + stop_rule=NONE` 运行后生成下一轮 dry-run 建议；它不执行任务。
