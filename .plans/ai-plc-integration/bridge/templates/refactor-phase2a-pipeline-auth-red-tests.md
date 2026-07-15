# 给重构模型的 Phase 2A 任务包

> **已完成/停用：** 本任务包已于 2026-07-15 完成 RED→GREEN 和 Codex 双重审查。不要重复执行；实际结果见 `../../refactor_phase2a_red_test_results.md`。

请在仓库根目录 `D:\claude code xiangmu\AI 接入PLC` 工作。

先完整阅读：

1. `AGENTS.md`
2. `.plans/ai-plc-integration/refactor_phase2a_pipeline_auth_red_tests.md`
3. `.plans/ai-plc-integration/docs/invariants.md`

只执行计划中的 Phase 2A 红测任务。你只能修改计划明确列出的两个测试文件和结果文件；不得修改任何生产代码，不得运行真实 MCP、TIA、PLCSIM、Factory I/O、后端或桌面程序，不得执行 Git 暂存、提交或推送。

目标是稳定复现两个契约缺口，不是让测试通过：

- API 注入的 `authenticated_operator` 被 Pipeline 错当成非法业务字段。
- MCP adapter 尚无内部凭据注入、调用方覆盖拒绝和凭据缺失失败关闭契约。

完成后写入 `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`，报告实际失败输出，并停止在 `NEED_CODEX_REVIEW`，等待 Codex 审查。不要继续生产实现。
