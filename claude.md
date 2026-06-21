# AI 接入 PLC — 项目指令

> **项目目标**：构建 AI Agent 系统 + 本地工业自动化 AI 工作台，让 AI 通过自然语言监控、控制西门子 PLC，并自动生成 PLC 代码。
>
> **技术栈**：MCP + Python + C#/.NET + Electron + React + FastAPI + Docker + S7协议 + TIA Portal Openness

---

## 运营规则（CCteam-creator 执行层）

### 任务推进原则
1. **先理解**：读 `.plans/ai-plc-integration/` 下的 `handoff.md` + `task_plan.md` + `progress.md` + `findings.md` + `docs/`
2. **再拆分**：将需求拆成 vertical slice（贯穿 schema→API→测试，可独立验收）
3. **再执行**：researcher 确认事实 → developer 实现 → reviewer 审查 → documenter 同步文档
4. **再复核**：reviewer 独立审查，developer 不能自审自批

### 文档同步原则
- 代码改动后必须同步 `docs/architecture.md`（架构变更）和 `docs/api-contracts.md`（API 变更）
- 新决策写入 `decisions.md`，新发现写入 `findings.md`
- 技术债务更新 `tech_debt.md`，风险更新 `risks.md`
- 每次会话结束更新 `handoff.md`
- 所有 agent 优先读 `.plans/` 文件，再开始工作
- **Undocumented APIs don't exist for other agents**

### 不可破坏约束 (invariants)
见 `.plans/ai-plc-integration/docs/invariants.md`（12 条硬边界）。最高优先级：
- 禁止 AI 操作急停回路
- 所有控制指令必须经过影子仿真
- 审计日志不可篡改（HMAC 链式哈希）
- 安全相关代码必须经过 reviewer 独立审查

### 失败处理原则
- 出现阻塞时先写入 `findings.md` 和 `progress.md`，再继续推进
- 每次失败 → 沉淀为护栏（更新 invariants 或 Known Pitfalls）
- 不回退到临场硬冲模式

### 复核机制
- **developer 和 reviewer 必须分离**，不能是同一 agent
- reviewer 按 5 维度打分（安全30% / 正确性25% / 文档一致性20% / Invariants15% / 代码质量10%）
- STRONG → 可合并 / ADEQUATE → 可合并附建议 / WEAK → BLOCK
- 安全维度任何违反 = 自动 WEAK

### 进度推进机制
- 每次完成一个 slice，必须更新 `progress.md`
- team-lead 负责验收每个 slice
- 进度过长时归档 `progress.md` 旧内容

### 团队配置

| 角色 | 百炼模型 | Claude 映射 | 职责 |
|------|---------|------------|------|
| Team Lead（主对话） | Kimi K2.7 Code | — | 项目规划、Agent调度、任务拆分、Slice规划 |
| Developer | DeepSeek V4 Pro | Sonnet | 编码、修Bug、重构、实现需求 |
| Researcher | DeepSeek V4 Flash | Haiku | 搜索、读文档、整理资料、摘要 |
| Reviewer/Architect | Qwen3.7-Max | Opus | 架构审查、代码Review、挑战方案、第二意见 |
| Documenter | DeepSeek V4 Pro | Sonnet | 维护 Project Brain，同步文档，填写 handoff |

模型映射：Haiku = DS-V4-Flash（便宜） / Sonnet = DS-V4-Pro（稳定编码/文档） / Opus = Qwen3.7-Max（架构审查）

详见 `.plans/ai-plc-integration/agents/` 下各角色文件。

### 会话恢复
1. 读取 `CLAUDE.md`（本文件，始终在上下文）
2. 读取 `.plans/ai-plc-integration/handoff.md` → 知道上次交接状态
3. 读取 `.plans/ai-plc-integration/task_plan.md` → 知道当前路线图
4. 读取 `.plans/ai-plc-integration/progress.md` → 知道上次做到哪
5. 读取 `.plans/ai-plc-integration/findings.md` → 知道已有结论
6. 读取 `.plans/ai-plc-integration/tech_debt.md` 和 `risks.md` → 知道债务和风险
7. 然后开始工作，不重复盘点

---

## 当前进度（2026-06-22）

| 模块 | 状态 |
|------|------|
| Phase 1: S7 运行态读写 | ✅ 完成 |
| Phase 2: AI 控制闭环 + 安全链 | ✅ 完成 |
| Phase 3: TIA 工程态 (TiaWorker) | ✅ 90% |
| AI PLC Assistant 桌面应用 V1.0 | ✅ 完成 |
| Phase 4: 工业机器人 | 未开始 |
| Phase 5: 统一编排 | 未开始 |
| 全仓审查修复 (63 A级) | ✅ 完成（58/58，2026-06-20） |
| CCteam-creator 执行层接入 | ✅ 完成（2026-06-22） |
| 测试覆盖 | ✅ 180 pass / 0 fail |

---

## 项目结构

```
ai-plc-integration/
├── ai-plc-assistant/          # ⭐ 桌面 AI 工作台（Electron+React+FastAPI）
│   ├── frontend/              # React + TailwindCSS + Lucide
│   ├── backend/               # FastAPI + ChromaDB + SQLite
│   ├── start.bat              # 一键启动
│   └── README.md
├── mcp-servers/               # MCP 服务器集合
│   ├── plc-mcp-bridge/        # S7 协议 + TIA 工程操作（65 工具）
│   ├── tia-mcp/               # TIA Portal Openness（TiaWorker C#）
│   ├── opcua-mcp/             # OPC UA（备用）
│   ├── modbus-mcp/            # Modbus（骨架）
│   └── mitsubishi-mcp/        # 三菱 MC 协议（骨架）
├── edge-gateway/              # 边缘网关（S7+Modbus 双协议采集）
├── safety/                    # 安全模块（互锁/影子仿真/审计/熔断）
├── plc-code-templates/        # PLC 代码模板
├── tests/                     # 测试套件
├── scripts/                   # 运维脚本
└── docs/                      # 阶段文档
```

---

## 核心原则

### 安全优先
- 所有写入操作经互锁检查 + 影子仿真验证
- 审计日志全覆盖（链式哈希）
- 连续异常自动熔断
- 禁止 AI 操作急停回路

### 开发环境
- OS: Windows 11
- Python: `D:\Python3\python.exe` (3.13.2)
- TIA Portal: V21
- PLCSIM: Advanced V8.0 (TCP/IP Single Adapter)
- PLC IP: 192.168.0.110 (Rack=0, Slot=1)

### AI PLC Assistant 配置
- 后端端口: 8005
- DeepSeek API 已配置
- 模型支持: DeepSeek / OpenAI / Kimi / Claude / 自定义
- 启动: `ai-plc-assistant/start.bat`

---

## 安全红线

### 运行安全
1. **禁止 AI 直接操作急停回路**
2. **禁止 AI 修改安全 PLC（F-CPU）参数**
3. **所有控制指令必须经过影子仿真**
4. **生产环境写入需双人确认**（操作人 + 确认人不是同一人）
5. **审计日志不可篡改**（HMAC 链式哈希）

### 配置安全
6. **安装 global git hooks 前必须显示预览并确认**（列出要安装的 hook 内容，获得用户明确同意）
7. **修改 ~/.claude/settings.json 前必须先备份并显示 diff 预览**（备份路径: ~/.claude/settings.json.bak）
