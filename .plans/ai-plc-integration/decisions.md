# 架构决策记录 — AI 接入 PLC

> 原则：记录架构选择、取舍和原因。每个决策包含日期、背景、选项、选择、理由。

---

## D-001：选择 CCteam-creator 作为执行层

- **日期**：2026-06-22
- **背景**：项目已有 7 个顶层文档，任务跟踪靠 TODO.md，无复核机制，会话间上下文丢失严重
- **选项**：
  - A. 继续当前 ad-hoc 方式（不引入额外结构）
  - B. 引入 CCteam-creator 的 .plans/ + agent 分工 + 文件化流程
  - C. 迁移到 Reasonix 或其他工具
- **选择**：B — 引入 CCteam-creator 执行层
- **理由**：
  - 不依赖外部工具，纯文件系统驱动，任何 agent 都能接
  - 与现有 CLAUDE.md 机制兼容，增量接入而非推倒重来
  - 文件化流程天然适合 git 版本控制

## D-002：项目名使用 `ai-plc-integration`

- **日期**：2026-06-22
- **背景**：.plans/ 目录需要项目名，仓库实际名为 `ai-plc-integration`
- **选择**：`.plans/ai-plc-integration/`
- **理由**：与 GitHub 仓库名一致，避免混淆

## D-003：最小团队 4 角色

- **日期**：2026-06-22
- **背景**：CCteam-creator 支持 6 个角色，但当前项目规模不需要全配
- **选择**：team-lead + researcher + developer + reviewer（4 角色）
- **理由**：
  - 暂不需要独立 e2e-tester（Playwright 测试在 V1.x 才启动）
  - 暂不需要独立 custodian（代码清理频率低）
  - 4 角色已覆盖 generator-evaluator 分离 + 独立研究 + 任务分派

## D-004：不迁移现有文档，改为索引

- **日期**：2026-06-22
- **背景**：7 个顶层文档内容丰富，但重叠
- **选择**：保留现有文档不动，.plans/docs/ 作为索引和补充
- **理由**：
  - 避免大规模文档迁移引入风险
  - 现有文档已通过 git 历史追踪
  - .plans/docs/ 专注"agent 需要快速读取的真相"

## D-005：引入 Documenter 角色 + 扩展 Project Brain

- **日期**：2026-06-22
- **背景**：GPT 反馈指出项目核心问题是知识无法沉淀，需要独立 Documenter 角色和 handoff/tech_debt/risks 文件
- **选择**：
  - 新增 `Documenter` 角色（Sonnet / DS V4 Pro）
  - 创建 `handoff.md` 作为会话交接标准格式
  - 创建 `tech_debt.md` 记录技术债务
  - 创建 `risks.md` 记录项目/依赖/许可证/模型风险
  - 更新 `CLAUDE.md` 和 `AGENTS.md`，将 Project Brain 作为会话恢复第一入口
- **修正（同一会话）**：
  - 运行测试后发现 `ai-plc-assistant/backend/tests/` 已有 250 个测试，并非零测试
  - 修正 `findings.md` 和 `tech_debt.md` 中"AI PLC Assistant 零测试"为"后端测试有损坏用例"
- **理由**：
  - 文档更新不能依赖 developer 自觉，必须有独立角色负责
  - `handoff.md` 能让新会话在 5 分钟内恢复上下文
  - 技术债务和风险单独成册，避免散落在 TODO 和聊天记录中
  - Project Brain 先于 Agent Team 完善，后续换模型/换 CLI 不会丢失上下文