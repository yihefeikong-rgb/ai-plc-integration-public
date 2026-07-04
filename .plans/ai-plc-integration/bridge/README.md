# Bridge

本目录用于承载 CCB + Codex + Claude Code 的人工协作桥接文件。

## 第一阶段用途

- 提供最小状态文件
- 提供占位锁文件
- 提供任务包、结果、审阅、下一步动作模板

## 第一阶段明确不做

- 不启用自动锁
- 不启用自动编排
- 不启用 hooks
- 不启用无人值守执行
- 不写入任何具体业务任务

## 目录结构

```
bridge/
├── templates/          ← 固定模板（纳入 Git，内容不变）
│   ├── task_packet.md
│   ├── claude_result.md
│   ├── codex_review.md
│   ├── next_action.md
│   ├── handoff-template.md
│   └── status-template.md
├── runs/               ← 运行态产物（不纳入 Git，每轮一个子目录）
│   └── {run_id}/       ← run_id 格式：{YYYYMMDD}_{HHMMSS}_{ffffff}_{task_slug}
│       ├── task_packet.md
│       ├── claude_result.md
│       ├── codex_review.md
│       └── next_action.md
├── state.json          ← 当前状态快照（含 run_id 指向本轮 runs/ 子目录）
├── lock.json           ← 占位锁
├── README.md
├── agent-protocol.md
├── runner_readme.md
├── *.py                ← 桥接脚本
```

## 手动闭环执行步骤

以下描述 Codex ↔ Claude Code 人工协作闭环的完整流程。

### 1. Codex 准备任务包

- Codex 读取 `bridge/state.json`，获取当前 `run_id`
- 如为新任务，Codex 创建 `bridge/runs/{run_id}/` 子目录并写入 `task_packet.md`
- Codex 更新 `bridge/state.json`，设置 `run_id`、`stage` → `"NEED_CLAUDE"`、`owner` → `"claude_code"`

### 2. Claude Code 执行

- Claude Code 启动后先读取 `AGENTS.md`、`claude.md`、`state.json`
- 从 `state.json` 获取 `run_id`，读取 `bridge/runs/{run_id}/task_packet.md`
- 确认 `stage == "NEED_CLAUDE"` 且 `owner == "claude_code"` 后才允许继续
- Claude Code 严格按 `task_packet.md` 的 Scope 执行，不触碰禁止文件和禁止目录

### 3. Claude Code 回填结果

- Claude Code 将执行结果写入 `bridge/runs/{run_id}/claude_result.md`
- Claude Code 更新 `bridge/state.json`：
  - `stage` → `"NEED_CODEX_REVIEW"`
  - `owner` → `"codex"`
  - `last_actor` → `"claude_code"`
  - `run_id` 保持不变

### 4. Codex 审查

- Codex 读取 `bridge/runs/{run_id}/claude_result.md`，对比 `task_packet.md` 的验收标准
- Codex 写入 `bridge/runs/{run_id}/codex_review.md`，给出审查结论：PASS / CONDITIONAL PASS / BLOCK

### 5. 人工作出决定

- 人工读取 `bridge/runs/{run_id}/codex_review.md`
- 根据审查结论决定下一步：
  - **PASS** → 本轮闭环完成，可进入下一任务
  - **CONDITIONAL PASS** → 人工判断是否接受，接受则闭环完成，不接受则进入返工
  - **BLOCK** → 进入返工，从步骤 1 重新开始
- 人工写入 `bridge/runs/{run_id}/next_action.md`，记录下一步指令

### 流程图

```
Codex 创建 runs/{run_id}/task_packet.md + state.json → NEED_CLAUDE
    ↓
Claude Code 读取 runs/{run_id}/task_packet.md 并执行
    ↓
Claude Code 写入 runs/{run_id}/claude_result.md + state.json → NEED_CODEX_REVIEW
    ↓
Codex 审查 runs/{run_id}/ → 写入 codex_review.md
    ↓
人工读取 runs/{run_id}/codex_review.md → 决定 PASS / 返工 / BLOCK
    ↓
人工写入 runs/{run_id}/next_action.md → 闭环完成
```

### 关键约束

- 每个闭环只处理一个任务包（single slice）
- Claude Code 和 Codex 必须为不同的 agent，禁止自我审查
- 不启用 hooks、orchestrator、无人值守、自动轮询（第一阶段禁止）
- 所有状态变更通过 `state.json` 显式记录，不依赖记忆或环境变量

## 协作层文件纳入 Git 的说明

### templates/（纳入 Git）

| 文件 | 类型 | 理由 |
|------|------|------|
| `task_packet.md` | 空模板 | 章节标题固定，供人工/Codex 复制后填入内容 |
| `claude_result.md` | 空模板 | 章节标题固定 |
| `codex_review.md` | 空模板 | 章节标题固定 |
| `next_action.md` | 空模板 | 章节标题固定 |
| `handoff-template.md` | 固定模板 | 会话交接模板 |
| `status-template.md` | 固定模板 | 状态模板 |

### runs/（不纳入 Git，已在 .gitignore 排除）

每轮协作产出存入 `runs/{run_id}/` 子目录，run_id 格式 `{YYYYMMDD}_{HHMMSS}_{ffffff}_{task_slug}`。历史运行记录不进入版本控制。

### bridge/ 根目录（纳入 Git）

| 文件 | 类型 |
|------|------|
| `state.json` | 当前状态快照（含 run_id 指向本轮 runs/ 子目录） |
| `lock.json` | 占位锁 |
| `README.md` | 目录说明 |
| `agent-protocol.md` | Agent 通信协议 |
| `runner_readme.md` | Runner 使用文档 |
| `*.py` | 桥接脚本 |

### 提交前检查

在发起 Git commit 之前，必须执行 `git status`，确认：
- runs/ 目录不在暂存区
- 无 `.env`、API Key、密码等敏感文件
- 无大型二进制文件

## C-13: cc-haha sidecar 可用性探测

在前置检查或启动时使用 `check_sidecar.py` 确认 cc-haha 桌面端背后的本地 API 是否可达。

### 前置条件

- cc-haha 桌面端已启动（或 sidecar 进程已在运行）
- sidecar 端口动态分配（不假设固定端口）

### 运行命令

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/check_sidecar.py
```

### 端口发现优先级

| 层 | 方法 | 说明 |
|----|------|------|
| 1 | `~/.claude/desktop-server-state.json` → `lastPort` | sidecar 每次启动后写入（优先可信） |
| 2 | localhost TCP 扫描 + `/health` 验证 | Layer 1 失效时，探测常见端口和 lastPort 附近 |
| 3 | `CC_HAHA_PORT` / `CC_HAHA_URL` 环境变量 | 手工指定，仅在 1+2 都失败时生效 |

### 输出

- **JSON**（stdout）：结构化诊断（`found`/`source`/`port`/`health_ok`/`error`）
- **摘要**（stdout）：人眼可读结论
- **退出码**：`0` = 可用，`1` = 不可用

### 典型输出（成功）

```json
{"found": true, "source": "state-file", "port": 11313, "health_ok": true, ...}
```

### 典型输出（失败）

```json
{"found": false, "source": null, "port": null, "health_ok": null,
 "error": "三层发现均未找到 sidecar：..."}
```

### 约束

- 纯只读：不创建/修改任何文件
- 不假设端口固定为 `127.0.0.1:3456`
- 不假设 `desktop-server-state.json` 一定存在

## C-14: cc-haha 受控 WS 任务投递 MVP

在 C-13 确认 sidecar 可达后，使用 `ws_task_runner.py` 打通一轮受控的 Claude 任务投递。

### 执行链

```
POST /api/sessions ─→ WS /ws/{sessionId} ─→ user_message ─→ (permission_request?) ─→ message_complete
       (REST)              (WebSocket)         (投递任务)       (保守策略)              (收尾)
```

### 前置条件

- C-13 `check_sidecar.py` 确认 sidecar 可用
- `websocket-client` 库已安装（`pip install websocket-client`）

### 运行命令

```bash
# 直接传参
D:/Python3/python.exe ws_task_runner.py "生成一个三相电机正反转 SCL 程序"

# 从文件读取
D:/Python3/python.exe ws_task_runner.py --task-file task_packet.md

# 从 stdin 传入
echo "写一条中文问候语" | D:/Python3/python.exe ws_task_runner.py

# 设置超时
D:/Python3/python.exe ws_task_runner.py "复杂任务" --timeout 300

# 复用指定 cc-haha session，避免新开对话
D:/Python3/python.exe ws_task_runner.py "继续当前任务" --session-id <sessionId>

# 强制新建 cc-haha session（会在侧边栏出现新对话）
D:/Python3/python.exe ws_task_runner.py "新任务" --new-session
```

### 会话复用策略

`ws_task_runner.py` 默认优先复用 `state.json` 里的 `session_id`。只有以下情况才会新建 cc-haha session：

- `state.json` 中没有 `session_id`
- 人工显式传入 `--new-session`

每轮仍会创建新的 `runs/{run_id}/` 目录保存运行产物，但 Claude 对话本身会尽量沿用同一个 `session_id`，避免侧边栏堆积新对话，也避免上下文被拆散。

### 输出

| 产出 | 位置 | 说明 |
|------|------|------|
| JSON stdout | 终端 | 结构化执行结果 |
| `claude_result.md` | bridge/ | 任务结果、事件日志、权限记录 |
| `state.json` | bridge/ | 切换为 NEED_CODEX_REVIEW，并记录 `session_id` / `session_reused` |

### 权限策略（保守白名单）

| 类别 | 行为 |
|------|------|
| 项目根内只读工具 | 自动放行（当前最小覆盖 `Read` / `LS` / `Glob` / `Grep` 的路径型请求） |
| 项目根外读取 | 自动拒绝 |
| 写入、命令执行、未知工具、畸形输入 | 自动拒绝 |
| 权限请求处理后 | 记录权限请求，继续等待 `message_complete` 或错误/超时 |

白名单只按工具名和路径边界判断；所有不明确安全的请求仍保持拒绝。

### 会话权限模式

`ws_task_runner.py` 创建 session 时会显式传入：

```json
{
  "workDir": "D:\\claude code xiangmu\\AI 接入PLC",
  "permissionMode": "default"
}
```

这样可以覆盖桌面端当前用户设置里的全局权限模式，避免在 sidecar 处于 `bypassPermissions` 时让写操作直接落盘。

### 约束

- 不自动 review
- 不自动 git
- 不自动重试
- 不依赖 /api/tasks 或未证实的 WS/ws/health

## C-17: Codex Review 草案生成器

`codex_review_draft.py` 用于在 `NEED_CODEX_REVIEW` 状态下生成一份可人工复核的 `codex_review.md` 草案。

### 运行命令

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/codex_review_draft.py
```

### 当前行为

| 条件 | 草案结果 |
|------|----------|
| `claude_result.md` 为 `success`、`status: OK` 且包含 `message_complete` | `PASS DRAFT` |
| 会话完成但存在权限拒绝 | `CONDITIONAL PASS DRAFT` |
| 证据不足或结果失败 | `BLOCK DRAFT` |

### 安全边界

- 只读取 `state.json` 和当前 `runs/{run_id}/claude_result.md`
- 只写入当前 `runs/{run_id}/codex_review.md`
- 若 `codex_review.md` 已存在，默认停止，避免覆盖人工审查或已有结论
- 不修改 `state.json`
- 不推进到 `DONE`
- 不自动重试、不自动 git、不触碰业务代码

### 验证

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_codex_review_draft.py
```

## C-18: 统一 Stop Rule

`ws_task_runner.py` 会在每轮结果中写入 `## Stop Rule`，并同步到 `state.json.stop_rule` / `state.json.blocked_reason`。这用于统一判断 runner 为什么必须停住等待人工或 Codex 审查。

### 当前分类

| code | 触发条件 | 行为 |
|------|----------|------|
| `NONE` | 会话成功完成，未发现风险 | 记录为无停止原因 |
| `SIDECAR_UNAVAILABLE` | 三层发现均未找到健康 sidecar | 停止，等待人工恢复 cc-haha |
| `SESSION_CREATE_FAILED` | 新建 session 失败 | 停止，等待人工检查 sidecar/API |
| `CWD_DRIFT` | session `work_dir` 不是项目根 | 停止，避免在错误目录继续执行 |
| `WS_TIMEOUT` | WS 会话超时 | 停止，等待审查或人工重试 |
| `PERMISSION_DENIED` | 权限请求被拒绝 | 停止，等待确认拒绝是否符合预期 |
| `SESSION_FAILED` | WS 返回其他错误 | 停止，等待审查 |
| `SESSION_INCOMPLETE` | 未成功完成且无明确错误 | 停止，等待审查 |

### 边界

- C-18 不启用自动重试
- C-18 不自动推进 `DONE`
- C-18 不改变人工审查点，状态仍回到 `NEED_CODEX_REVIEW`
- `blocked_reason` 只在 `stop=true` 时写入；`NONE` 保持空阻塞原因

## C-19: 监督式连续运行门控

`supervised_batch.py` 用于在人工监督下检查一批低风险任务是否可以继续推进。它只做 dry-run 门控和下一条命令建议，不会自动调用 Claude、不循环、不修改 `state.json`。

### 运行命令

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/supervised_batch.py \
  --task-file .plans/ai-plc-integration/bridge/templates/supervised-tasks.example.txt
```

### 任务队列格式

- 一行一个低风险任务
- 空行忽略
- `#` 开头的注释行忽略
- 示例文件：`templates/supervised-tasks.example.txt`

### 监督门规则

| 条件 | 行为 |
|------|------|
| `state.json` 没有 `session_id` | 拒绝继续，避免新开 Claude 对话 |
| `stop_rule` 不是 `NONE` | 拒绝继续，必须人工处理上一轮风险 |
| `stage = NEED_CODEX_REVIEW` 且 `review_status != PASS` | 拒绝继续，等待人工/Codex 审查 |
| `stage = BLOCKED` / `SAFETY_BLOCK` | 拒绝继续 |
| 人工已 PASS、`stop_rule = NONE`、且存在 `session_id` | 输出下一条 `ws_task_runner.py --session-id ...` 命令 |
| 队列中所有任务都已确认完成 | 返回 `ALL_TASKS_DONE`，不输出下一条命令 |

### 队列推进方式

- `supervised_batch.py` 不修改任务队列文件
- `ack_review.py --decision PASS` 会从当前 run 的 `claude_result.md` 提取任务文本
- 已确认完成的任务写入 `state.json.supervised_completed_tasks`
- 下次 dry-run 时，`supervised_batch.py` 会跳过已完成任务，输出第一条未完成任务
- 如果所有任务都已完成，`supervised_batch.py` 返回 `ALL_TASKS_DONE`

### 明确不做

- 不自动执行下一条任务
- 不循环消费任务队列
- 不自动清空或修改任务队列
- 不自动修改 `state.json`
- 不自动批准权限
- 不自动 git
- 不启用 hooks 或无人值守运行

### 验证

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_supervised_batch.py
```

## 人工审查确认记录器

`ack_review.py` 用于把人工对当前 run 的最终裁决写入 `state.json` 和 `runs/{run_id}/next_action.md`。它不执行 Claude、不消费任务队列、不批准未来权限，只记录当前 run 的审查结论。

### 接受当前 run

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/ack_review.py \
  --run-id <current-run-id> \
  --decision PASS \
  --reason "说明为什么接受当前结果"
```

执行后：

- `stage` → `DONE`
- `review_status` → `PASS`
- 当前活动 `stop_rule` → `NONE`
- 原 stop rule 写入 `last_stop_rule`
- 当前 run 的任务文本写入 `supervised_completed_tasks`
- `blocked_reason` 清空
- 写入 `runs/{run_id}/next_action.md`

### 阻塞当前 run

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/ack_review.py \
  --run-id <current-run-id> \
  --decision BLOCK \
  --reason "说明为什么阻塞"
```

执行后：

- `stage` → `BLOCKED`
- `review_status` → `BLOCK`
- 保留当前 `stop_rule`
- `blocked_reason` 写入人工阻塞原因
- 写入 `runs/{run_id}/next_action.md`

### 安全边界

- 必须传入当前 `state.json.run_id`，不允许确认其他 run
- 必须写 `--reason`
- 不自动运行下一条任务
- 不修改任务队列
- 不触碰业务代码
- 不操作 Git

### 验证

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_ack_review.py
```

## C-14.2: 会话级工作目录绑定

C-14.2 修复 `POST /api/sessions` 建会话时未绑定项目根的问题。`ws_task_runner.py` 创建 session 时必须显式传入：

```json
{"workDir": "D:\\claude code xiangmu\\AI 接入PLC"}
```

### 依据

- cc-haha server 的 `POST /api/sessions` 接收字段为 `workDir`
- cc-haha desktop API 创建 session 时同样使用 `{ workDir: input }`
- sidecar 创建后的 session 详情应返回 `workDir`，且 `workDirExists = true`
- cc-haha `ConversationService` 使用该 `workDir` 作为 CLI 子进程 `cwd`，并同步覆盖 `CALLER_DIR` / `PWD`

### 验证

```bash
D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_ws_task_runner.py
D:/Python3/python.exe .plans/ai-plc-integration/bridge/check_sidecar.py
```

若 sidecar 可达，可创建一次最小 session 并检查 `/api/sessions/{sessionId}`：

```json
{
  "workDir": "D:\\claude code xiangmu\\AI 接入PLC",
  "workDirExists": true
}
```

### 边界

- C-14.2 只修复 session 级目录绑定
- C-16 已将权限策略升级为项目根内只读白名单，其余请求默认拒绝
- 不进入自动审查、自动重试、自动轮询或无人值守
- C-15 低风险多轮稳定化必须在 C-14.2 验证后再开始

## Phase 3A: dry-run runner

为减少人工传话但避免进入无人值守开发，Phase 3A 新增单步 dry-run runner：

- 入口文件：`runner_dry_run.py`
- 说明文件：`runner_readme.md`
- 默认行为：只读取 `state.json`，只向 stdout 输出下一步建议和可复制 prompt

### runner 边界

- 不调用 Codex CLI
- 不调用 Claude Code CLI
- 不调用任何外部 agent
- 不自动循环
- 不自动 git add / commit / push
- 不写入 `state.json`、`lock.json`、`task_packet.md`、`claude_result.md`、`codex_review.md`、`next_action.md`

### runner 支持状态

- `NEED_CODEX_PLAN`
- `NEED_CLAUDE`
- `NEED_CODEX_REVIEW`
- `DONE`
- `BLOCKED`
- `SAFETY_BLOCK`

### runner 停止条件

当 `stage` 为 `DONE`、`BLOCKED`、`SAFETY_BLOCK` 时：

- 只输出停止建议
- 不生成推进执行 prompt
- 必须等待人工确认
