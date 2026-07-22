# AI 接入 PLC 审计整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。所有步骤使用复选框跟踪。

**Goal:** 在不接触真实 PLC 的前提下，先建立不可绕过的控制安全边界，再修复自动主链、数据安全、测试与 Bridge 可信度问题。

**Architecture:** 修复顺序必须从最终写入边界向上推进：硬件/模拟目标身份与写入授权 → MCP/编排控制面 → Pipeline 结果语义 → UI 与文档。任何一层未完成都不能用上层“通过”代替。

**Tech Stack:** Python/FastAPI、FastMCP、Orchestrator、S7/OPC UA/Modbus、TIA Worker/C#、React/Electron、SQLite/Chroma、pytest。

---

## 0. 执行护栏与进入条件

- 本计划对应 `audit_findings.md`；每项修复完成前不得把真实 PLC、F-CPU、安全回路或生产网络接入。
- 当前 `AGENTS.md` 的 Phase 1 只允许改协作层文件。实施本计划中涉及 `backend`、`frontend`、`mcp-servers`、`orchestrator`、`safety`、`tests` 的任务前，必须由用户明确扩大修改授权。
- 禁止运行根 `pytest`、归档 TIA/PLCSIM 测试、下载脚本、`start.bat` 或真实设备连接作为默认验证。
- 每个任务遵循：先写离线失败测试 → 运行确认失败 → 最小修复 → 运行目标测试 → 复核 Git diff。提交、推送和外部服务启动不在本计划的自动操作范围内。

## 修复顺序总览

| 阶段 | 覆盖问题 | 完成门槛 |
|---|---|---|
| 0 | P0-01、P0-02、P0-03、P0-04、P0-05 | 真实控制、真实下载、危险测试全部默认阻断 |
| 1 | P1-01 至 P1-06 | 主链能在隔离环境报告真实成功/失败，写入与审计 fail-closed |
| 2 | P1-07 至 P1-10、P2-01 至 P2-03 | 本机文件、密钥、LLM、知识库和测试数据被隔离 |
| 3 | P1-11 至 P1-13、P2-04 至 P2-06、P3-01 | Bridge、配置、入口、文档和启动行为一致 |
| 4 | 全部 | 仅在隔离 PLCSIM 完成受控动态验收；再评估是否允许模拟写入 |

## 2026-07-15 实施证据回填

> 本节记录当前代码与离线回归证据，不以单测替代动态 PLC 验收。原始复选框保留为逐条审查清单；尚未逐项人工代码复核前，不批量改为完成。

| 范围 | 当前状态 | 证据 |
|---|---|---|
| 阶段 0～3 | 已有实现和离线回归证据 | `c45ce8a fix: strengthen PLC control safety boundaries` 覆盖本计划各任务的目标模块；2026-07-15 根目录离线测试为 `306 passed, 41 deselected`。 |
| Task 4 收集安全测试 | 已实现，路径已校正 | 实际测试是 `tests/offline/test_pytest_collection_safety.py`，并验证默认收集排除下载、机器人和归档 TIA 测试。 |
| Task 12 知识库/设置安全测试 | 已实现，路径已校正 | 实际测试是 `ai-plc-assistant/backend/tests/test_storage_safety.py`，覆盖维度不匹配不删除集合、凭据不写入 JSON、原子保存和凭据库故障 fail-closed。 |
| Task 13 Bridge 证据门 | 已实现，路径已校正 | `bridge/test_ack_review.py`、`test_bridge_state.py`、`test_ws_task_runner.py` 覆盖审查产物哈希、人工审查人、原子状态锁、会话 CWD 与权限模式验证。 |
| 阶段 4 | 未开始，环境阻塞 | PLCSIM Advanced V8 许可证到期，尚无实例、下载、CPU RUN 或 snap7 回读证据。 |

下一步是逐条代码审查原始复选框并回填，不应在没有 PLCSIM 实例时声称动态验收完成。

### 任务级离线验证矩阵（2026-07-15）

| Task | 状态 | 已通过的直接证据 |
|---|---|---|
| 1：确认最终写入闸门 | 离线验证通过 | `tests/test_write_confirmation_gate.py`：一次性令牌、目标/操作者/过期校验，以及 S7、OPC UA、Modbus、三菱最终写入消费。 |
| 2：急停与机器人动作隔离 | 离线验证通过 | `mcp-servers/robot-mcp/test_estop_contract.py`：急停 fail-closed 与恢复后重新确认。 |
| 3：PLCSIM 目标身份 | 离线验证通过 | `mcp-servers/tia-mcp/test_target_identity.py`：唯一配置实例允许，缺失、歧义、漂移和自由 IP 拒绝。 |
| 4：默认测试无副作用 | 离线验证通过 | `tests/offline/test_pytest_collection_safety.py`：默认收集排除硬件、桌面和归档 TIA 测试。 |
| 5：本地控制与密钥边界 | 离线验证通过 | `ai-plc-assistant/backend/tests/test_local_control_auth.py`：会话令牌、确认令牌、工具 allowlist 和 HTTPS 提供商限制。 |
| 6：编排装配与工具契约 | 离线验证通过 | `orchestrator/tests/test_nl_to_plcsim_live_contract.py`：同一 pool/SafetyGate 注入、连接失败与参数漂移处理。 |
| 7：工具结果与假 PASS | 离线验证通过 | `orchestrator/tests/test_tool_result_contract.py`：错误、未知文本、超时、取消和部分失败均不可报告成功。 |
| 8：S7 地址语义与类型 | 离线验证通过 | `tests/test_s7_address_semantics.py`：显式映射、严格值转换和未映射地址拒绝。 |
| 9：LAD 语义硬阻断 | 离线验证通过 | `mcp-servers/tia-mcp/test_ladder_semantic_safety.py`：急停、互锁、定时器和类型拒绝样例。 |
| 10：下载、审计、重试 fail-closed | 离线验证通过 | `tests/test_control_operation_idempotency.py`、`tests/test_audit_fail_closed.py`：变更操作不盲重试、未知结果失败、审计不可用阻断。 |
| 11：文件、上传与 LLM 限制 | 离线验证通过 | `test_file_scope_limits.py`、`test_llm_safety_limits.py`：路径、ZIP、请求、RAG 与 fallback 边界。 |
| 12：知识库、设置与测试数据 | 离线验证通过 | `test_storage_safety.py`：维度迁移不删库、凭据库 fail-closed、原子保存。 |
| 13：Bridge 状态与审查证据 | 离线验证通过 | `test_ack_review.py`、`test_bridge_state.py`、`test_ws_task_runner.py`：产物哈希、人工审查、原子锁、CWD/权限元数据。 |
| 14：配置、入口与文档契约 | 离线验证通过 | `tests/test_entrypoint_path_contract.py`、`tests/test_config_target_contract.py`：唯一入口、唯一所有者、V21 目标契约。 |

> 关键回归须分为根目录、后端和 Bridge 等测试域执行。根目录与 `ai-plc-assistant/backend` 都含 `tests/conftest.py`，在同一 pytest 进程聚合会触发 `ImportPathMismatchError`；这不是功能失败。

## 阶段 0：先建立不可绕过的安全边界

### Task 1：把“确认”变成最终写入闸门

**关联发现：** AUD-P0-01、AUD-P1-03。  
**文件：**

- 修改：`safety/validator.py`、`orchestrator/safety_gate.py`、`orchestrator/core.py`
- 修改：`mcp-servers/plc-mcp-bridge/tools_s7.py`、`mcp-servers/opcua-mcp/server.py`、`mcp-servers/modbus-mcp/server.py`、`mcp-servers/mitsubishi-mcp/server.py`
- 新增测试：`tests/test_write_confirmation_gate.py`

- [ ] 为“需要确认”的结果定义不可执行状态，而不是仅附带布尔标记。
- [ ] 设计一次性确认令牌，绑定操作者身份、目标地址/标签、值、设备身份、短时有效期和审计 ID。
- [ ] 在每个最终写入工具执行前验证并消费令牌；缺失、过期、设备不匹配或重复使用均拒绝。
- [ ] 为 S7、OPC UA、Modbus、三菱写入分别写离线替身测试：无令牌拒绝、错误令牌拒绝、正确令牌只允许一次。
- [ ] 运行：`D:\Python3\python.exe -m pytest -p no:cacheprovider tests/test_write_confirmation_gate.py -q`。预期：全部通过，且不创建网络连接。

### Task 2：隔离急停与机器人真实动作

**关联发现：** AUD-P0-02。  
**文件：**

- 修改：`ai-plc-assistant/frontend/src/components/RobotPanel.jsx`
- 修改：`mcp-servers/robot-mcp/server.py`、`mcp-servers/robot-mcp/pnp_fc.scl`
- 新增测试：`mcp-servers/robot-mcp/test_estop_contract.py`

- [ ] 明确 RobotPanel 是“纯模拟”还是“真实控制”；若为纯模拟，移除“已关闭所有输出”等真实动作暗示。
- [ ] 将急停极性定义为唯一契约，并在 Python 后端、PLC 程序和测试中使用同一语义。
- [ ] 读取急停失败、未知或通信异常时，真实动作路径必须拒绝；模拟后端须显式选择。
- [ ] 用内存后端测试：急停有效、极性翻转、读取异常、恢复后重新确认四种情形。

### Task 3：把下载目标限制为可证明的 PLCSIM 实例

**关联发现：** AUD-P0-03、AUD-P1-12。  
**文件：**

- 修改：`mcp-servers/tia-mcp/download_to_plcsim.py`、`mcp-servers/tia-mcp/TiaWorker/Program.cs`、`mcp-servers/tia-mcp/server.py`
- 修改：`mcp-servers/tia-mcp/config.yaml` 与唯一配置加载路径
- 新增测试：`mcp-servers/tia-mcp/test_target_identity.py`

- [ ] 删除“第一个接口/设备/目标”的危险回退。
- [ ] 只接受经身份校验的 PLCSIM Advanced 实例；发现多个、零个或身份不匹配时均返回明确失败。
- [ ] 不接受自由 `target_ip` 作为下载目标；目标必须来自已验证的实例配置。
- [ ] 用纯替身 API 测试：正确实例允许、无实例拒绝、多个实例拒绝、非仿真目标拒绝。

### Task 4：让默认测试入口离线且无副作用

**关联发现：** AUD-P0-04、AUD-P1-10。  
**文件：**

- 修改：`pytest.ini`
- 移动或重命名：`mcp-servers/tia-mcp/archived/test_*.py` 的默认收集路径
- 修改：`tests/test_download_flow.py`、`tests/test_robot_mcp.py`
- 新增测试：`tests/offline/test_pytest_collection_safety.py`

- [ ] 默认 `pytest` 只收集明确离线的测试目录；归档、硬件、桌面和网络测试改为显式 marker。
- [ ] 为会启动 TIA、恢复实例或连接 OPC UA 的测试增加强制阻断条件和独立命令。
- [ ] 在无设备环境执行 `D:\Python3\python.exe -m pytest --collect-only -q`，验证收集结果不包含硬件测试。

### Task 5：封闭本地控制与密钥外传面

**关联发现：** AUD-P0-01、AUD-P0-05。  
**文件：**

- 修改：`ai-plc-assistant/backend/main.py`、`ai-plc-assistant/backend/routes/settings.py`
- 修改：`ai-plc-assistant/backend/routes/orchestrator.py`、`orchestrator/core.py`
- 新增测试：`ai-plc-assistant/backend/tests/test_local_control_auth.py`

- [ ] 移除 `null` Origin；明确开发和桌面运行的最小允许来源。
- [ ] 为设置、动态工作流、临时工作流和任何控制接口实施本地会话鉴权。
- [ ] 禁止任意 MCP 工具名；使用服务端 allowlist 与明确危险动作分类，不能靠工具名关键词猜测写入。
- [ ] 供应商 Base URL 使用 HTTPS 白名单；修改地址不能复用未确认的旧密钥。
- [ ] 用 FastAPI TestClient 和替身服务验证未认证、`null` Origin、非白名单 URL 和危险工具均被拒绝。

## 阶段 1：修复主链、写入语义与审计可信度

### Task 6：接通真实编排装配并统一工具契约

**关联发现：** AUD-P1-01。  
**文件：**

- 修改：`ai-plc-assistant/backend/main.py`、`orchestrator/bootstrap.py`、`orchestrator/api.py`
- 修改：`orchestrator/workflows/nl_to_plcsim_pipeline.py`、`mcp-servers/plc-mcp-bridge/tools_project.py`、`mcp-servers/plc-mcp-bridge/tools_pipeline.py`
- 新增测试：`orchestrator/tests/test_nl_to_plcsim_live_contract.py`

- [ ] 在唯一启动路径中将同一 pool 和 SafetyGate 注入全局引擎，并确保关闭同一 pool。
- [ ] 统一工作流参数与 MCP schema；不支持的参数必须在请求边界拒绝，而不是静默忽略。
- [ ] 用内存 MCP adapter 覆盖“连接成功、参数不匹配、连接失败”三种情形。

### Task 7：统一工具结果协议并消除假 PASS

**关联发现：** AUD-P1-02、AUD-P2-02。  
**文件：**

- 修改：`orchestrator/mcp_client.py`、`orchestrator/core.py`、`orchestrator/workflows/nl_to_plcsim_pipeline.py`
- 修改：`ai-plc-assistant/backend/routes/pipeline.py`、`ai-plc-assistant/frontend/src/components/OrchestratorPanel.jsx`
- 新增测试：`orchestrator/tests/test_tool_result_contract.py`

- [ ] 为成功、工具错误、非 JSON 文本、超时、取消定义唯一结构化结果。
- [ ] Workflow StepResult 只能由明确成功结果标记 `ok=True`。
- [ ] UI 只能在 HTTP 成功、业务成功和每步成功均满足时显示 PASS。
- [ ] 运行目标测试，覆盖 `{error: true}`、`❌ 文本`、空结果、部分成功。

### Task 8：建立写入地址语义映射与严格类型规则

**关联发现：** AUD-P1-03。  
**文件：**

- 修改：`safety/interlock-rules.yml`、`safety/validator.py`、`mcp-servers/plc-mcp-bridge/tools_s7.py`、`mcp-servers/plc-mcp-bridge/s7_adapter.py`
- 新增测试：`tests/test_s7_address_semantics.py`

- [ ] 对允许写入的原始地址建立显式语义映射；未映射地址默认拒绝。
- [ ] 使用严格布尔、整数、浮点转换；拒绝字符串伪布尔、NaN、Infinity 和越界值。
- [ ] 将现有 shadow 模块重命名或明确声明为静态预检，不能代替真实仿真。

### Task 9：把 LAD 语义验证接入导入前的硬阻断

**关联发现：** AUD-P1-04。  
**文件：**

- 修改：`mcp-servers/tia-mcp/config_loader.py`、`mcp-servers/tia-mcp/server.py`、`mcp-servers/tia-mcp/ladder_spec.schema.json`、`mcp-servers/tia-mcp/CartGen/Program.cs`
- 新增测试：`mcp-servers/tia-mcp/test_ladder_semantic_safety.py`

- [ ] 结构校验通过后必须执行语义安全校验，失败不得调用 CartGen 或导入 TIA。
- [ ] CartGen 遇到不支持类型、缺失定时器字段或 I/O 映射丢失时必须显式失败。
- [ ] 建立拒绝样例：缺急停、正反转无互锁、类型不支持、定时器字段不完整。

### Task 10：让下载、审计和重试 fail-closed

**关联发现：** AUD-P1-05、AUD-P1-06。  
**文件：**

- 修改：`mcp-servers/tia-mcp/download_to_plcsim.py`、`mcp_common/tiaworker_client.py`、`mcp_common/audit.py`、`orchestrator/core.py`
- 新增测试：`tests/test_control_operation_idempotency.py`、`tests/test_audit_fail_closed.py`

- [ ] 下载成功只能由明确的设备级成功状态决定；任何未知状态均失败。
- [ ] 导入、删除、下载等变更操作取消盲重试，改为只读对账。
- [ ] 生产控制环境缺审计密钥、审计存储不可写或审计身份缺失时拒绝动作。
- [ ] 审计参数脱敏，身份由认证上下文提供。

## 阶段 2：收紧数据、LLM、知识库与测试隔离

### Task 11：限制本机文件、上传和 LLM 消耗

**关联发现：** AUD-P1-07、AUD-P1-08、AUD-P2-01。  
**文件：**

- 修改：`ai-plc-assistant/backend/routes/search.py`、`ai-plc-assistant/backend/search/scanner.py`、`ai-plc-assistant/backend/routes/projects.py`
- 修改：`ai-plc-assistant/backend/routes/chat.py`、`ai-plc-assistant/backend/llm/service.py`、`ai-plc-assistant/backend/generator/workflow.py`
- 新增测试：`ai-plc-assistant/backend/tests/test_file_scope_limits.py`、`ai-plc-assistant/backend/tests/test_llm_safety_limits.py`

- [ ] 搜索仅允许受控项目根，返回内容和绝对路径需经授权裁剪。
- [ ] ZIP 上传使用流式处理并限制总大小、成员数、单文件大小和解压比。
- [ ] 对聊天设置认证、请求长度、并发、速率、模型和 token 预算；fallback 必须显式授权。
- [ ] 拒绝客户端 system 消息，把 RAG 资料当作不可信引用。
- [ ] 生成失败返回失败；示例程序必须显著标记且不可直接进入导入/下载流程。

### Task 12：保护知识库、设置和测试数据

**关联发现：** AUD-P1-09、AUD-P1-10、AUD-P2-03。  
**文件：**

- 修改：`ai-plc-assistant/backend/knowledge/engine.py`、`ai-plc-assistant/backend/storage/app_settings.py`
- 修改：`ai-plc-assistant/backend/tests/conftest.py`、`pytest.ini`
- 新增测试：`ai-plc-assistant/backend/tests/test_storage_safety.py`

- [ ] 知识库异常不得删除集合；迁移必须先备份并有明确确认。
- [ ] 密钥迁移到受限凭据存储或加密存储；文件写入采用原子替换。
- [ ] 后端测试在导入应用前强制使用临时数据库与设置文件，禁止清理真实相对路径数据。
- [ ] 在临时目录验证迁移失败、崩溃写入和测试清理均不影响真实目录。

## 阶段 3：收敛 Bridge、配置、启动与文档

### Task 13：让 Bridge 状态、会话和审查证据可验证

**关联发现：** AUD-P1-11、AUD-P2-04。  
**文件：**

- 修改：`.plans/ai-plc-integration/bridge/ws_task_runner.py`、`.plans/ai-plc-integration/bridge/ack_review.py`、`.plans/ai-plc-integration/bridge/runner_step.py`、`.plans/ai-plc-integration/bridge/supervised_batch.py`
- 修改：`.plans/ai-plc-integration/bridge/agent-protocol.md`、`requirements.txt`
- 测试：`.plans/ai-plc-integration/bridge/test_ack_review.py`、`.plans/ai-plc-integration/bridge/test_bridge_state.py`、`.plans/ai-plc-integration/bridge/test_ws_task_runner.py`

- [ ] 复用前从侧车读取真实会话 CWD/权限；读取失败即阻断。
- [ ] `ack_review` 仅接受 `NEED_CODEX_REVIEW`、有效 run_id、审查产物、审查人和可接受 stop rule 的组合。
- [ ] 结果文件保留可审查的受限正文或摘要，审查结论必须绑定其哈希/版本。
- [ ] 为共享 `state.json` 增加原子锁；状态枚举只保留一个来源。
- [ ] 固定 CLI 执行路径和 `cwd=PROJECT_ROOT`；补齐 `websocket-client` 依赖声明。

### Task 14：收敛唯一配置、启动入口和 API 文档

**关联发现：** AUD-P1-12、AUD-P1-13、AUD-P2-05、AUD-P2-06、AUD-P3-01。  
**文件：**

- 修改：`mcp-servers/tia-mcp/config.yaml`、对应配置加载器、`scripts/p3_flow.py`、`start.bat`
- 修改：`README.md`、`AGENTS.md`、`CURRENT_STATUS.md`、`PROJECT_HANDOVER.md`、`.plans/ai-plc-integration/docs/api-contracts.md`
- 新增测试：`tests/test_entrypoint_path_contract.py`、`tests/test_config_target_contract.py`

- [ ] 让 V21、`demo_V21.ap21`、`factoryio` 和隔离目标 IP 通过唯一配置源提供；冲突即阻断。
- [ ] 移除不存在的启动命令，修正 P3 项目根计算和批处理工作目录。
- [ ] 明确唯一 MCP 进程所有者，防止启动时重复拉起服务。
- [ ] 文档仅保留当前可验证入口；历史状态显式标为历史快照；API 文档同步真实响应结构。

## 阶段 4：隔离验收门槛

- [x] 所有离线单元测试通过，默认 `pytest --collect-only` 不包含硬件测试。（2026-07-15：`306 passed, 41 deselected`。）
- [x] 所有 P0/P1 测试覆盖拒绝路径、超时、错误结果、确认令牌、目标身份和审计失败。（2026-07-15：按测试域显式回归共 `128 passed`。）
- [ ] 在专用 PLCSIM 网络中验证：目标身份识别、无确认拒绝、确认后单次写入、下载失败不得报告成功、S7 回读证据完整。
- [ ] 只有取得“项目已加载、下载已完成、CPU/RUN、PLC 可读”四层独立证据后，才允许声明模拟链路验收成功。
- [ ] 真实 PLC 连接另行建立独立安全评审，不作为本计划自动下一步。

## 提交与外部动作规则

- 本计划不授权自动 `git add`、commit、push、启动服务、设备写入或权限提升。
- 每个任务完成后必须先由人工审阅 diff、测试证据和安全边界，再决定是否进入下一任务。
