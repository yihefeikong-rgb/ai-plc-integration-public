# Runner Dry-Run

## 目标

`runner_dry_run.py` 是 Phase 3A 的单步 dry-run runner，只读取 `state.json`，根据当前 `stage` 生成下一步建议和可复制 prompt。

## 当前边界

- 只读 `state.json`
- 只输出到 stdout
- 不写任何桥接文件
- 不调用 Codex CLI
- 不调用 Claude Code CLI
- 不调用任何外部 agent
- 不自动循环
- 不自动 git add / commit / push

## 支持状态

- `NEED_CODEX_PLAN`
- `NEED_CLAUDE`
- `NEED_CODEX_REVIEW`
- `DONE`
- `BLOCKED`
- `SAFETY_BLOCK`

## 行为说明

- `NEED_CODEX_PLAN`：输出给 Codex 的规划提示词
- `NEED_CLAUDE`：输出给 Claude Code 的执行提示词
- `NEED_CODEX_REVIEW`：输出给 Codex 的审查提示词
- `DONE` / `BLOCKED` / `SAFETY_BLOCK`：只输出停止建议，不生成推进 prompt

## 使用方式

```bash
python .plans/ai-plc-integration/bridge/runner_dry_run.py
```

## 后续演进

后续如果需要减少人工复制，可以在新阶段单独讨论：

- 是否允许写入独立输出文件
- 是否允许引入锁检查
- 是否允许调用外部 CLI

这些能力不属于 Phase 3A。

## 真实使用流程

以下描述一次完整的低风险实战闭环，从 Codex 规划到人工确认 DONE。

### 步骤 1：Codex 规划任务

- Codex 读取 `state.json`（含 `run_id`）
- Codex 填写 `bridge/runs/{run_id}/task_packet.md`
- Codex 将 `state.json` 更新为：
  - `stage: NEED_CLAUDE`
  - `owner: claude_code`
  - `last_actor: codex`

### 步骤 2：人工运行 runner 获取 prompt

```bash
python .plans/ai-plc-integration/bridge/runner_dry_run.py
```

runner 读取当前 `state.json`（此时应为 `NEED_CLAUDE`），输出：
- `Mode: DRY-RUN`（确认是 dry-run 模式）
- `Current Stage`（确认状态正确）
- `Suggested Recipient: claude_code`
- `Next Step Suggestion`（包含执行要求的可复制 prompt）

人工将 prompt 复制并交给 Claude Code 执行。

### 步骤 3：Claude Code 执行

- Claude Code 按 `bridge/runs/{run_id}/task_packet.md` 的 Scope 和 Out of Scope 执行
- 修改完成后，Claude Code 回填 `bridge/runs/{run_id}/claude_result.md`，写明：
  - 实际修改了哪些文件
  - 是否触碰禁止目录
  - 是否完成验收标准
- Claude Code 将 `state.json` 更新为：
  - `stage: NEED_CODEX_REVIEW`
  - `owner: codex`
  - `last_actor: claude_code`

### 步骤 4：人工再次运行 runner 获取审查 prompt

```bash
python .plans/ai-plc-integration/bridge/runner_dry_run.py
```

此时 runner 读取到 `NEED_CODEX_REVIEW`，输出给 Codex 的审查 prompt。人工将 prompt 交给 Codex。

### 步骤 5：Codex Review

- Codex 对照 `bridge/runs/{run_id}/task_packet.md` 的验收标准审查 `bridge/runs/{run_id}/claude_result.md`
- Codex 填写 `bridge/runs/{run_id}/codex_review.md`，给出结论：`PASS` / `CONDITIONAL PASS` / `BLOCK`
- Codex 填写 `bridge/runs/{run_id}/next_action.md`，记录下一步指令

### 步骤 6：人工确认 DONE

- 人工读取 `codex_review.md` 和 `next_action.md`
- 如果 PASS：人工将 `state.json` 更新为 `DONE`，本轮闭环完成
- 如果 BLOCK：人工决定返工或终止
- 人工确认后可选进入下一轮任务

### runner 在该流程中的角色

在整个流程中，`runner_dry_run.py` 只做三件事：

1. **读取** `state.json` — 不修改它
2. **识别**当前 stage — 判断是活跃态还是停止态
3. **输出**建议 prompt — 到 stdout，供人工复制使用

**runner 不会做的事情：**
- ✅ 不调用 Codex CLI / Claude Code CLI / 任何外部 agent
- ✅ 不自动循环（每次只推进一个 state）
- ✅ 不修改 `state.json`、`task_packet.md`、`claude_result.md` 等桥接文件
- ✅ 不自动 git add / commit / push
- ✅ 不实现 `--execute` 或类似自动执行入口

### 停止态行为

当 `state.json` 中的 `stage` 为以下值时，runner 只输出停止建议，不生成推进 prompt：

- **DONE**：本轮完成，等待人工决定是否进入下一轮
- **BLOCKED**：本轮阻塞，等待人工判断返工、改范围或终止
- **SAFETY_BLOCK**：安全红线触发，禁止继续推进，必须人工复核

此时人工必须介入决策，不能依赖 runner 自动恢复。

## Phase 5: 受控单步自动化 MVP

`runner_step.py` 是 Phase 5 的实验性单步执行器，在保留人工控制的前提下减少人工传话步骤。

### runner_step 与 runner_dry_run 的区别

| 特性 | `runner_dry_run.py` | `runner_step.py` |
|------|---------------------|------------------|
| 默认模式 | dry-run（只读） | dry-run（只展示摘要） |
| 是否可调用 CLI | 否 | 是，但受控 |
| 是否需 YES 确认 | N/A | 是（--execute 时必须） |
| 停止态保护 | 输出停止建议 | **拒绝执行** |

### 使用方式

**dry-run 模式（默认）：**
```bash
python .plans/ai-plc-integration/bridge/runner_step.py
```
输出执行摘要：当前 stage、owner、目标 Agent、命令来源、prompt 摘要。**不调用任何 CLI。**

**复制模式（cc-haha GUI 兼容）：**
```bash
python .plans/ai-plc-integration/bridge/runner_step.py --copy
```
将当前 stage 对应的 prompt 复制到 Windows 剪贴板，方便粘贴到 cc-haha 桌面版或其他 GUI 工具中使用。不调用 Agent、不控制 GUI、不模拟键盘鼠标。

**执行模式：**
```bash
python .plans/ai-plc-integration/bridge/runner_step.py --execute
```
1. 先展示完整执行摘要
2. 要求人工输入 `YES` 确认
3. 仅在确认后执行 CLI 调用
4. 执行后显示 exit code

### 环境变量

`runner_step.py` 依赖环境变量确定 CLI 命令，不会猜测命令路径：

- `CLAUDE_CODE_CMD` — Claude Code 的可执行命令（例如 `claude`、`claude.exe`、`/path/to/claude`）
- `CODEX_CMD` — Codex CLI 的可执行命令（Phase 5 MVP 暂未支持）

缺失时必须清晰报错，不会自动 fallback 到猜测路径。

### cc-haha 桌面版推荐

如果使用 cc-haha 桌面版（当前用户环境），推荐使用 `--copy` 模式替代 `--execute`：

- 运行 `python runner_step.py --copy` 将 prompt 复制到剪贴板
- 手动粘贴到 cc-haha 中执行
- 不要强行配置 `CLAUDE_CODE_CMD` 使用 `--execute`，避免与桌面版冲突

### 当前支持范围

| 状态 | 行为 |
|------|------|
| `NEED_CLAUDE` | dry-run 展示摘要；`--execute` 可真实调用 Claude Code |
| `NEED_CODEX_PLAN` | dry-run 展示 prompt；`--execute` 提示"暂不支持 Codex CLI" |
| `NEED_CODEX_REVIEW` | dry-run 展示 prompt；`--execute` 提示"暂不支持 Codex CLI" |
| `DONE` / `BLOCKED` / `SAFETY_BLOCK` | **拒绝执行**（停止态保护） |

### 安全保护

1. **停止态保护**：`DONE` / `BLOCKED` / `SAFETY_BLOCK` 下直接拒绝执行，不做任何 CLI 调用
2. **YES 确认**：`--execute` 时必须在执行前输入 `YES`，否则取消
3. **环境变量校验**：缺失 `CLAUDE_CODE_CMD` 时清晰报错，不猜测路径
4. **超时保护**：CLI 执行超过 3600 秒自动终止
5. **不写桥接文件**：不自动修改 `state.json`、`lock.json`、`task_packet.md`、`claude_result.md`、`codex_review.md`、`next_action.md`
6. **不操作 Git**：不自动 git add / commit / push
7. **不循环**：每次只推进一个 state，不自动重试，不自动调用多个 Agent

### Phase 5 边界

- 不是 Phase 3B（不进入无人值守、自动编排）
- 不是自动执行器（每一步仍需人工介入确认）
- 不是 CLI 调用器（有限定支持的范围和状态）
