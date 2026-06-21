# Team OS v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current single-model execution into a controller + forced-specialist workflow by hard-binding roles to files, inputs, outputs, and handoffs.

**Architecture:** The main conversation becomes a dispatcher that only splits tasks, assigns roles, and accepts deliverables. Four specialist agents (Researcher, Developer, Reviewer, Documenter) operate on `.plans/ai-plc-integration/` as the single source of truth. A new `task_queue.md` is the only entry point; `task_spec.md` is the per-task contract; `CLAUDE.md` and the agent files are updated to enforce boundaries with explicit stop conditions.

**Tech Stack:** Markdown, existing `.plans/ai-plc-integration/` layout, `CLAUDE.md`, `git`.

## Global Constraints
- No business logic or feature code is written during this setup.
- The existing `.plans/ai-plc-integration/` directory must be preserved and extended, not replaced.
- All changes must be committed to git after the final review.
- The main conversation must not write findings, code, or review conclusions itself.
- Every role file must explicitly state: allowed inputs, allowed outputs, and forbidden actions.

---

### Task 1: Create the single task entry point (`task_queue.md`)

**Files:**
- Create: `.plans/ai-plc-integration/task_queue.md`

**Interfaces:**
- Consumes: None.
- Produces: The canonical backlog. Team-lead appends new tasks here; agents read only the top active item.

- [ ] **Step 1: Create `task_queue.md`**

```markdown
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
```

- [ ] **Step 2: Verify file exists and table is parseable**

Run: `ls .plans/ai-plc-integration/task_queue.md`
Expected: File exists.

---

### Task 2: Create the per-task contract (`task_spec.md`)

**Files:**
- Create: `.plans/ai-plc-integration/task_spec.md`

**Interfaces:**
- Consumes: A task from `task_queue.md`.
- Produces: The detailed spec that Researcher, Developer, Reviewer consume.

- [ ] **Step 1: Create `task_spec.md` with the first slice template**

```markdown
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
```

- [ ] **Step 2: Verify the spec exists and references TS001 correctly**

Run: `grep -q "TS001" .plans/ai-plc-integration/task_spec.md`
Expected: Exit code 0.

---

### Task 3: Harden `CLAUDE.md` with Team OS controller rules

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Existing `CLAUDE.md`, user's Team OS requirements.
- Produces: Updated `CLAUDE.md` with explicit dispatcher-only rules.

- [ ] **Step 1: Append a new "Team OS 主控规则" section to `CLAUDE.md`**

```markdown
---

## Team OS 主控规则（强制）

### 主对话权限
主对话（team-lead）只允许做三件事：
1. **拆分任务**: 将需求拆分为 vertical slices，写入 `task_queue.md` 和 `task_spec.md`。
2. **调度角色**: 按 `Researcher → Developer → Reviewer → Documenter` 的顺序分派任务。
3. **验收产物**: 检查每个角色的输出是否落在其 allowed outputs 范围内。

### 主对话禁止
- 不能直接写研究结论（findings.md 只能由 Researcher/Documenter 更新）。
- 不能直接写业务代码、测试代码、或修改业务文件。
- 不能直接做详细代码审查或输出 PASS/FAIL。
- 不能直接修改 `progress.md` / `handoff.md` / `decisions.md` / `findings.md`（应由 Documenter 在对应阶段更新）。
- 不能直接回应业务问题；必须先写入任务队列，再分派给 Researcher。

### 强制分工触发条件
- 任何涉及多步骤的研究 → Researcher
- 任何代码/测试实现 → Developer
- 任何审查/打分/安全分析 → Reviewer
- 任何进度/文档/交接更新 → Documenter

### 单任务推进
- 同一时刻只允许一个 `IN_PROGRESS` 的 task_spec。
- 当前 slice 未通过 review 之前，不得开始新 slice。
- 并行只能发生在同一 slice 内的独立子任务（由 team-lead 显式声明）。

### 失败处理
- 角色失败时，team-lead 不得替该角色补产物。
- team-lead 应将失败原因写入 `findings.md`（通过 Documenter），然后重分配任务。

### 停止条件
- Team OS 初始化完成后，主对话必须输出 `Project Brain Initialized`，并等待人工确认。
- 在未获得人工确认前，不得进入业务功能开发。
```

- [ ] **Step 2: Verify the new section exists**

Run: `grep -q "Team OS 主控规则" CLAUDE.md`
Expected: Exit code 0.

---

### Task 4: Harden agent role files with explicit boundaries

**Files:**
- Modify: `.plans/ai-plc-integration/agents/team-lead.md`
- Modify: `.plans/ai-plc-integration/agents/researcher.md`
- Modify: `.plans/ai-plc-integration/agents/developer.md`
- Modify: `.plans/ai-plc-integration/agents/reviewer.md`
- Modify: `.plans/ai-plc-integration/agents/documenter.md`

**Interfaces:**
- Consumes: Existing role files.
- Produces: Role files with explicit inputs, outputs, and forbidden actions.

- [ ] **Step 1: Append "Team OS 边界" section to each role file**

For `team-lead.md`:

```markdown
## Team OS 边界

### 允许输入
- `task_queue.md`
- `task_spec.md`
- `findings.md`
- `progress.md`
- `decisions.md`

### 允许输出
- 更新 `task_queue.md`（状态、新增任务）
- 更新 `task_spec.md`（新 slice 规格）
- 通过 Documenter 间接更新 `progress.md` / `handoff.md`
- 分派指令（在对话中向其他 agent 发任务）

### 禁止事项
- 不直接写代码、测试、review 结论
- 不直接修改 `findings.md`、`decisions.md`、`docs/architecture.md`、`docs/api-contracts.md`
- 不替其他 agent 补输出
```

For `researcher.md`:

```markdown
## Team OS 边界

### 允许输入
- `task_spec.md`
- `findings.md`
- `docs/architecture.md`
- `docs/api-contracts.md`
- `docs/invariants.md`
- 代码库（只读）

### 允许输出
- 更新 `findings.md`
- 向 team-lead 提供研究结论

### 禁止事项
- 不修改任何业务代码或测试
- 不修改 `task_spec.md`、`task_queue.md`、角色文件
- 不输出未经验证的结论为事实
```

For `developer.md`:

```markdown
## Team OS 边界

### 允许输入
- `task_spec.md`
- `findings.md`
- `docs/architecture.md`
- `docs/api-contracts.md`
- `docs/invariants.md`
- `CLAUDE.md`

### 允许输出
- 业务代码
- 测试代码
- 更新 `docs/architecture.md`（架构变更时）
- 更新 `docs/api-contracts.md`（API 变更时）
- 更新 `decisions.md`（实现决策时）

### 禁止事项
- 不审查自己的代码
- 不修改 `task_queue.md`、`task_spec.md`、角色文件
- 不做需求范围外的重构
- 不修改 `progress.md`、`handoff.md`
```

For `reviewer.md`:

```markdown
## Team OS 边界

### 允许输入
- `task_spec.md`
- `findings.md`
- `docs/invariants.md`
- `docs/api-contracts.md`
- developer 的 git diff

### 允许输出
- 审查结论（输出到对话，由 Documenter 记录）
- 更新 `findings.md`（发现新风险时）
- 更新 `docs/invariants.md`（需要新增约束时）

### 禁止事项
- 不修改代码、测试、业务文件
- 不审查自己的代码
- 不输出无依据的 PASS
```

For `documenter.md`:

```markdown
## Team OS 边界

### 允许输入
- `task_queue.md`
- `task_spec.md`
- `findings.md`
- 所有 agent 的输出和结论

### 允许输出
- 更新 `progress.md`
- 更新 `handoff.md`
- 更新 `decisions.md`（记录已做出的决策）
- 更新 `tech_debt.md`、`risks.md`
- 同步 `docs/architecture.md` 和 `docs/api-contracts.md`（仅格式/一致性，不做架构变更）

### 禁止事项
- 不修改业务逻辑、代码、测试
- 不修改 `task_spec.md`、角色文件
- 不做架构或安全决策
```

- [ ] **Step 2: Verify all role files contain "Team OS 边界"**

Run: `grep -l "Team OS 边界" .plans/ai-plc-integration/agents/*.md | wc -l`
Expected: Output `5`.

---

### Task 5: Create the minimal vertical slice workflow

**Files:**
- Create: `.plans/ai-plc-integration/workflows/vertical-slice.md`

**Interfaces:**
- Consumes: `task_queue.md`, `task_spec.md`, agent role files.
- Produces: A reproducible workflow document that team-lead follows.

- [ ] **Step 1: Create the workflow file**

```markdown
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
```

- [ ] **Step 2: Verify the workflow file exists**

Run: `ls .plans/ai-plc-integration/workflows/vertical-slice.md`
Expected: File exists.

---

### Task 6: Update progress and handoff

**Files:**
- Modify: `.plans/ai-plc-integration/progress.md`
- Modify: `.plans/ai-plc-integration/handoff.md`

**Interfaces:**
- Consumes: Completion of Tasks 1-5.
- Produces: Updated progress tracking and session handoff.

- [ ] **Step 1: Append to `progress.md`**

```markdown
## 2026-06-22 — Team OS v1 初始化
- 完成 `task_queue.md` 与 `task_spec.md`
- 更新 `CLAUDE.md` 加入 Team OS 主控规则
- 固化 5 个角色文件的输入/输出/禁止事项
- 创建 `workflows/vertical-slice.md`
- 等待人工确认，不继续开发功能
```

- [ ] **Step 2: Update `handoff.md`**

```markdown
# Handoff — 2026-06-22

## 当前状态
Team OS v1 工作流已初始化完成，等待人工确认。

## 已完成
- task_queue.md / task_spec.md 已创建
- CLAUDE.md 已加入主对话控制器规则
- agents/*.md 已加入 Team OS 边界
- workflows/vertical-slice.md 已创建

## 待确认
- 是否继续开发业务功能？（当前禁止自动继续）

## 下一步（由 team-lead 在人工确认后执行）
- 将下一个业务需求拆分为 TS002 并加入 task_queue.md
- 按 Researcher → Developer → Reviewer → Documenter 流程执行
```

- [ ] **Step 3: Verify both files mention Team OS v1**

Run: `grep -q "Team OS v1" .plans/ai-plc-integration/progress.md && grep -q "Team OS v1" .plans/ai-plc-integration/handoff.md`
Expected: Exit code 0.

---

### Task 7: Final review and commit

**Files:**
- Use: `git`

**Interfaces:**
- Consumes: All modified files.
- Produces: A single commit documenting the Team OS setup.

- [ ] **Step 1: Stage all modified/new files**

Run:
```bash
git add .plans/ai-plc-integration/task_queue.md \
        .plans/ai-plc-integration/task_spec.md \
        .plans/ai-plc-integration/agents/*.md \
        .plans/ai-plc-integration/workflows/vertical-slice.md \
        .plans/ai-plc-integration/progress.md \
        .plans/ai-plc-integration/handoff.md \
        CLAUDE.md
```

- [ ] **Step 2: Commit with conventional message**

Run:
```bash
git commit -m "chore: initialize Team OS v1 workflow with role boundaries and task queue"
```

- [ ] **Step 3: Output completion message**

Main conversation must output:

```
Project Brain Initialized
```

Then wait for human confirmation before any further feature work.
