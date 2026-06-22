# 技术债务 — AI 接入 PLC

> 原则：记录已知问题、临时方案和未来重构项。每项包含严重度、影响范围、预计处理时机。

---

## 严重度定义

| 严重度 | 含义 |
|--------|------|
| P0 | 阻塞发布，必须立即处理 |
| P1 | 当前迭代必须处理 |
| P2 | V1.x 迭代处理 |
| P3 | 可接受，未来再处理 |

---

## 已确认债务

### T-001：AI PLC Assistant 后端测试有损坏用例

- **严重度**：P1
- **影响**：`ai-plc-assistant/backend/tests/` 共有 250 个测试，237 pass，6 fail，7 error
- **失败/错误项**：
  - `test_api_chat_stream.py::TestChatStream::test_stream_basic`
  - `test_api_projects.py::TestProjects::test_list_after_create`
  - `test_knowledge_integration.py::TestRAGIntegration::test_chat_with_rag`
  - `test_sse_streaming.py` × 3
  - `test_parsers_knowledge.py` × 2（fixture `sample_txt_file` 缺失）
  - `test_parsers_search.py` × 5（fixture 缺失）
- **临时方案**：无，CI 无法通过
- **处理方案**：修复 fixture 缺失 + 定位并修复 6 个失败用例
- **跟踪**：`task_plan.md` Slice 2
- **状态**：✅ 已修复（250 passed / 0 failed / 0 error）

### T-002：梯形图 SVG 可视化已存在，生产稳定性待验证

- **严重度**：P2
- **影响**：`frontend/src/components/LadderVisualizer.jsx` 已实现 V2，但不确定是否经过实机/真实场景验证
- **临时方案**：已有 SVG 渲染组件
- **处理方案**：
  - 确认 LadderVisualizer 覆盖所有元素类型
  - 增加组件测试
  - 在实际项目中验证渲染正确性
- **跟踪**：`TODO.md` 高优先级（已完成实现）
- **状态**：待验证

### T-003：Electron 打包未验证

- **严重度**：P1
- **影响**：无法确认生产包可正常安装和运行
- **临时方案**：开发模式运行
- **处理方案**：运行 `npm run dist` 验证 NSIS 安装包
- **跟踪**：`TODO.md` 高优先级
- **状态**：待处理

### T-004：RAG 中文检索效果差

- **严重度**：P2
- **影响**：中文文档搜索准确率低
- **临时方案**：当前使用 BAAI/bge-small-zh-v1.5（从 all-MiniLM 升级）
- **处理方案**：评估是否升级到 BAAI/bge-m3 并重建 ChromaDB 索引
- **跟踪**：`TODO.md` 中优先级
- **状态**：待处理

### T-005：工程搜索中文不分词

- **严重度**：P2
- **影响**：FTS5 对中文搜索走 LIKE，性能和准确率差
- **临时方案**：当前 unicode61 tokenizer
- **处理方案**：引入 jieba 分词器 + 自定义 FTS5 tokenizer
- **跟踪**：`TODO.md` 中优先级
- **状态**：待处理

### T-006：TIA 下载后 ConveyorControl FB501 未在 OB1 调用

- **严重度**：P2
- **影响**：下载后传送带不响应
- **临时方案**：手动在 TIA 中调用 FB501
- **处理方案**：在自动下载流程中调用 FB501
- **跟踪**：`AGENTS.md` 已知 Bug
- **状态**：待处理

### T-007：顶层文档重叠

- **严重度**：P2
- **影响**：`CLAUDE.md`、`AGENTS.md`、`AI_CONTEXT.md`、`ARCHITECTURE.md`、`CURRENT_STATUS.md`、`TODO.md`、`PROJECT_HANDOVER.md` 内容重复且不同步
- **临时方案**：保留现有文档，`.plans/docs/` 作为索引和补充
- **处理方案**：逐步收敛为 `.plans/` 为单一真相源，顶层文档仅保留入口
- **跟踪**：`findings.md` 瓶颈 1
- **状态**：进行中

### T-008：前端组件测试缺失

- **严重度**：P1
- **影响**：React 组件无 vitest 测试，UI 重构风险高
- **临时方案**：依赖手工验证
- **处理方案**：建立 vitest 测试，覆盖 ChatArea、Sidebar、SettingsPanel、LadderVisualizer 等关键组件
- **跟踪**：`task_plan.md` Slice 4
- **状态**：待处理

### T-009：E2E 测试缺失

- **严重度**：P2
- **影响**：关键用户流程无自动化保障
- **临时方案**：无
- **处理方案**：引入 Playwright，覆盖登录/对话/导入/生成/导出主流程
- **跟踪**：`TODO.md` 中优先级
- **状态**：待处理

### T-010：会话上下文依赖聊天记录

- **严重度**：P1
- **影响**：新会话/新模型需要重新解释项目
- **临时方案**：人工每次复述背景
- **处理方案**：`handoff.md` + Documenter 角色，确保每次会话可恢复
- **跟踪**：本文件、`.plans/ai-plc-integration/handoff.md`
- **状态**：进行中

### T-011：未提交文件堆积

- **严重度**：P2
- **影响**：工作区中存在未提交改动，可能包含已完成但未入库的功能
- **临时方案**：保留在工作区
- **处理方案**：
  - 审查 `git status` 中列出的未提交文件
  - 分批提交或清理
- **跟踪**：`CURRENT_STATUS.md`
- **状态**：待处理

---

## 已归档债务

### ~~T-012：TiaCommander Beta 已过期~~

- **归档日期**：2026-06-22
- **状态**：已用自研 TiaWorker 替代，覆盖 90% 功能
- **结论**：不再作为活跃债务

### T-013：server_configs.py 硬编码绝对路径

- **严重度**：P1
- **影响**：`orchestrator/server_configs.py` 中 MCP 服务器启动路径硬编码为当前开发环境的绝对路径，换机/换用户后无法使用
- **临时方案**：当前仅 mock 模式测试通过，实际连接未验证
- **处理方案**：改为环境变量或配置文件驱动（如 `PLC_MCP_BRIDGE_PATH`、`TIA_MCP_PATH` 等），支持相对路径和 PATH 查找
- **跟踪**：`orchestrator/server_configs.py`
- **状态**：待处理

### T-014：mock 模式不经过 SafetyGate

- **严重度**：P2
- **影响**：`orchestrator/mcp_client.py` 在 mock 模式下跳过 SafetyGate 集成，写入操作不受安全拦截。虽然这是设计预期（mock 模式下无真实 PLC 连接），但需确保生产环境正确激活 SafetyGate
- **临时方案**：mock 模式为测试专用，生产环境通过 `core.py` 的 `_check_safety()` 方法拦截
- **处理方案**：在测试中增加 SafetyGate 集成测试（mock SafetyGate 边界验证），确保切换模式时不会遗漏安全拦截
- **跟踪**：`orchestrator/core.py`、`orchestrator/mcp_client.py`
- **状态**：待处理
