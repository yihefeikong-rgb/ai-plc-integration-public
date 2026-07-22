# AI 接入 PLC 全面审计：完整问题清单

> 审计日期：2026-07-13  
> 审计方式：静态只读审计 + 受限离线单元测试  
> 归档说明：本文件由用户在审计完成后授权创建；原审计过程本身未修改仓库。

## 范围、证据与限制

- 已审计主要入口、前后端、LLM/RAG、MCP、TIA/PLCSIM、PLC 写入、安全层、LAD 生成、测试体系、Bridge 和项目文档。
- 唯一实际运行的测试为 `tests/test_safety_validator.py`、`tests/test_safety_audit.py`、`orchestrator/tests/test_nl_to_plcsim_pipeline.py`：共 `25 passed`。这只证明离线校验和 Mock 工作流，不证明真实 TIA、PLCSIM、S7、OPC UA、Factory I/O 或下载链路。
- 未连接 PLC、TIA Portal、PLCSIM、Factory I/O、侧车或外部 API；任何“下载已完成”“PLC 可读”的结论均未在本次审计中验证。
- 路径均相对于项目根目录 `D:\claude code xiangmu\AI 接入PLC`。

## 问题统计

| 等级 | 数量 | 含义 |
|---|---:|---|
| P0 致命 | 5 | 可能引起设备危险动作、真实控制越权或严重密钥泄露 |
| P1 严重 | 13 | 核心链路不可用、关键安全/数据/权限边界可绕过 |
| P2 中等 | 6 | 稳定性、审查可信度、文档或用户提示问题 |
| P3 一般 | 1 | 低风险治理缺口 |

## P0 致命

### AUD-P0-01：写入没有真正的双人确认与权限闸门

- **领域**：工业控制安全、MCP、编排层。
- **位置**：`safety/validator.py:166-170`、`orchestrator/core.py:191-206`、`mcp-servers/plc-mcp-bridge/tools_s7.py:149-161`、`ai-plc-assistant/backend/routes/orchestrator.py:263-287`、`mcp-servers/tia-mcp/server.py:54-67`、`mcp-servers/robot-mcp/server.py:337-351`、`mcp-servers/opcua-mcp/server.py:50-58`。
- **证据与原因**：校验器只返回 `needs_confirmation=True`；各调用方只在 `allowed=False` 时阻断。动态工作流接受任意 MCP 工具/参数；多个控制 MCP 在空令牌时默认放行。
- **触发条件**：连接池正确接通，或控制 MCP 被独立调用。
- **实际影响**：单一 AI/本地调用可越过双人确认执行工程操作或设备写入；是否会触及真实设备取决于现场连接，但代码中没有可靠阻断。
- **处理方向**：以第二个已认证身份对精确 `{目标、值、设备身份、有效期}` 生成一次性确认令牌，并在最终写入点原子验证和消费；未配置认证时拒绝控制能力。
- **动态验证**：需要，仅限隔离 PLCSIM。**置信度：高。**

### AUD-P0-02：机器人急停存在 UI 假成功、极性矛盾与读取失败放行

- **领域**：机器人与功能安全。
- **位置**：`ai-plc-assistant/frontend/src/components/RobotPanel.jsx:54-63`、`mcp-servers/robot-mcp/server.py:221-274`、`mcp-servers/robot-mcp/pnp_fc.scl:12-25`。
- **证据与原因**：前端急停只修改 React 状态却提示输出已关闭；后端与 PLC 程序对 `I0.8` 的急停极性解释不一致；读取异常返回 `None` 后仍可能继续写入。
- **触发条件**：操作员将该 UI 当作真实急停入口，或真实后端遇到急停/通信异常。
- **实际影响**：物理设备可能未停止，但界面显示已停止；急停安全状态可能被反向解释。
- **处理方向**：真实急停只能依赖硬件安全回路；UI 必须明确标识纯模拟；安全读取无法证明安全时一律拒绝动作。
- **动态验证**：需要，仅限受控 PLCSIM/I-O。**置信度：高。**

### AUD-P0-03：TIA 下载目标可回退到首个接口/设备，无法证明是 PLCSIM

- **领域**：TIA 下载与目标身份安全。
- **位置**：`mcp-servers/tia-mcp/download_to_plcsim.py:156,180-239`、`mcp-servers/tia-mcp/TiaWorker/Program.cs:529,559,704,722`、`mcp-servers/tia-mcp/server.py:466-514`。
- **证据与原因**：仿真目标枚举失败会被吞掉，代码可取第一个设备、接口或目标；调用方允许提供自由 `target_ip`。
- **触发条件**：接口排序变化、PLCSIM 未找到、网络配置漂移或调用方给出非仿真 IP。
- **实际影响**：生成程序可能下载到非预期 PLC。
- **处理方向**：以 PLCSIM Advanced 实例身份/指纹强校验；匹配失败即拒绝；下载前强制预览与双人确认。
- **动态验证**：需要，仅限隔离 PLCSIM 适配器。**置信度：高。**

### AUD-P0-04：默认根 pytest 可能触发真实 TIA/PLCSIM/OPC UA 操作

- **领域**：测试安全。
- **位置**：`pytest.ini:2-4`、`mcp-servers/tia-mcp/archived/test_tcpip_fix.py:43-91`、`mcp-servers/tia-mcp/archived/test_tcpip_restore.py:18-32`、`tests/test_download_flow.py:57-75`、`tests/test_robot_mcp.py:31-59`。
- **证据与原因**：默认收集整个 `mcp-servers/tia-mcp`，仅排除 `integration`；归档测试未标记却会重置绑定、恢复实例、启动 TIA 或尝试 OPC UA 连接。
- **触发条件**：在根目录执行普通 `pytest`，或 CI/工具默认使用根测试配置。
- **实际影响**：可能污染工程环境、改变仿真实例或接触设备网络，不能作为安全质量门。
- **处理方向**：默认入口只允许纯离线测试；硬件、桌面、网络和归档测试须显式 marker 与独立命令。
- **动态验证**：修复后只能在无设备环境验证测试收集行为。**置信度：高。**

### AUD-P0-05：本地网页可改模型地址并使已保存密钥外传

- **领域**：应用安全、密钥保护。
- **位置**：`ai-plc-assistant/backend/main.py:95-102`、`ai-plc-assistant/backend/routes/settings.py:75-82`、`ai-plc-assistant/backend/storage/app_settings.py:72-86`、`ai-plc-assistant/backend/llm/service.py:49-55`。
- **证据与原因**：CORS 接受 `null` Origin；无认证设置接口可修改供应商 `base_url`，并复用已保存的 API Key。
- **触发条件**：用户打开恶意本地 HTML，或本机低权限进程访问回环 API。
- **实际影响**：攻击者可将请求重定向到自有服务器并获得有效模型密钥。
- **处理方向**：移除 `null` Origin；本地 API 使用启动时随机鉴权；供应商地址白名单和 HTTPS 校验。
- **动态验证**：需要，限隔离环境。**置信度：高。**

## P1 严重

### AUD-P1-01：NL→PLCSIM 主链未注入真实连接池且工具签名失配

- **领域**：主链架构与可用性。
- **位置**：`ai-plc-assistant/backend/main.py:67-73`、`orchestrator/bootstrap.py:49-91`、`orchestrator/core.py:263-319`、`orchestrator/workflows/nl_to_plcsim_pipeline.py:64-77`、`mcp-servers/plc-mcp-bridge/tools_project.py:8-27`、`mcp-servers/plc-mcp-bridge/tools_pipeline.py:12-45`。
- **证据与原因**：后端只将 pool 放进 `app.state`，没有 `engine.set_pool()`；工作流传入 `project_path/plc_ip`，目标工具不接受这些参数。
- **实际影响**：当前主链无法据此完成真实调用，任何端到端成功声明都不可信。
- **处理方向**：统一启动装配、引擎注入和 MCP 工具契约；先写隔离集成测试再连设备。
- **动态验证**：需要。**置信度：高。**

### AUD-P1-02：MCP 错误可能被工作流与 UI 误报为成功

- **领域**：结果语义、验收可信度。
- **位置**：`orchestrator/mcp_client.py:153-176`、`orchestrator/workflows/nl_to_plcsim_pipeline.py:11-19`、`orchestrator/core.py:321-328`、`ai-plc-assistant/backend/routes/pipeline.py:50-55`。
- **证据与原因**：`{error: true}` 或普通文本不被 `_is_ok()` 识别，步骤仍可能记录 `ok=True`，回读摘要只看步骤标记。
- **实际影响**：下载、连接或读取失败可能显示 PASS / `snap7_verified`。
- **处理方向**：统一结构化结果协议；任何工具错误、未知文本或缺失证据默认失败。
- **动态验证**：需要。**置信度：高。**

### AUD-P1-03：原始 S7 地址可绕开语义联锁，布尔转换不严格，影子仿真非真实仿真

- **领域**：运行态 PLC 写入安全。
- **位置**：`mcp-servers/plc-mcp-bridge/tools_s7.py:112-166`、`mcp-servers/plc-mcp-bridge/s7_adapter.py:195-286`、`safety/interlock-rules.yml:2`、`safety/shadow_simulator.py:1-7`。
- **证据与原因**：联锁规则使用语义名，工具验证原始地址；`bool("false")` 会为真；影子模块明确不模拟 PLC 扫描周期/真实逻辑。
- **实际影响**：范围、冷却、互锁可能不生效，且静态预检被误作写入许可。
- **处理方向**：建立唯一地址—语义映射；拒绝未映射写入；严格布尔/NaN/Inf 转换；改名为静态预检直到具备真实模型。
- **动态验证**：需要，PLCSIM 逐点。**置信度：高。**

### AUD-P1-04：LAD 语义安全校验未接入生成/导入，Schema 与 CartGen 语义不一致

- **领域**：PLC 代码生成。
- **位置**：`mcp-servers/tia-mcp/config_loader.py:238`、`mcp-servers/tia-mcp/server.py:589-618,734-737`、`mcp-servers/tia-mcp/ladder_spec.schema.json:93,119`、`mcp-servers/tia-mcp/CartGen/Program.cs:95-136`。
- **实际影响**：结构合法但缺急停、互锁或过载语义的 LAD 可能进入工程；支持类型可能静默降为 BOOLEAN。
- **处理方向**：语义校验设为硬阻断；生成前后断言类型、定时器和 I/O 映射保持一致。
- **动态验证**：需要。**置信度：高。**

### AUD-P1-05：下载失败和超时重试不能可靠反映真实结果

- **领域**：TIA/PLCSIM 操作可靠性。
- **位置**：`mcp-servers/tia-mcp/download_to_plcsim.py:241-259`、`mcp_common/tiaworker_client.py:84,114-155`、`mcp-servers/tia-mcp/TiaWorker/Program.cs:611-622`。
- **实际影响**：失败可返回零退出码，超时后可能重复执行导入、删除或下载。
- **处理方向**：只接受明确成功状态；变更类操作禁用自动重试，以操作 ID 和只读对账决定下一步。
- **动态验证**：需要，构造“动作完成但响应超时”场景。**置信度：高。**

### AUD-P1-06：审计链默认可伪造，审计失败不阻断高风险操作

- **领域**：审计、安全治理。
- **位置**：`mcp_common/audit.py:27-33`、`orchestrator/core.py:222-237`、`mcp-servers/modbus-mcp/server.py:95-124`、`mcp-servers/mitsubishi-mcp/server.py:87-111`。
- **实际影响**：默认 HMAC 密钥可预测；调用方可伪造 operator；审计失败后仍可能执行，并可能落盘敏感参数。
- **处理方向**：生产缺密钥即拒绝控制能力；身份来自认证上下文；高风险审计 fail-closed；参数脱敏。
- **动态验证**：需要。**置信度：高。**

### AUD-P1-07：无认证接口可索引任意目录和接收无上限 ZIP

- **领域**：本机文件安全、资源耗尽。
- **位置**：`ai-plc-assistant/backend/routes/search.py:62-86`、`ai-plc-assistant/backend/search/scanner.py:40-60`、`ai-plc-assistant/backend/search/indexer.py:153-186`、`ai-plc-assistant/backend/routes/projects.py:105-125`。
- **实际影响**：可读取/回显本机可读 PLC 类文件，或被 ZIP 炸弹、巨量成员耗尽资源。
- **处理方向**：项目根 allowlist、路径规范化、身份授权、流式上传和大小/成员数/解压比上限。
- **动态验证**：需要，临时目录。**置信度：高。**

### AUD-P1-08：LLM 调用可被滥用，失败时可返回可导出的示例 PLC 程序

- **领域**：LLM 成本、安全语义。
- **位置**：`ai-plc-assistant/backend/routes/chat.py:15-21`、`ai-plc-assistant/backend/llm/service.py:124-147`、`ai-plc-assistant/backend/generator/workflow.py:135-196`、`ai-plc-assistant/frontend/src/components/LadderGenerator.jsx:198-214`。
- **实际影响**：无预算、频率、并发和输入上限；模型失败可能生成与需求无关的 demo 逻辑并被导出。
- **处理方向**：鉴权、配额、明确 fallback 同意；生成失败必须失败，教学示例不能直接导入或下载。
- **动态验证**：需要。**置信度：高。**

### AUD-P1-09：知识库初始化可能删除已有集合

- **领域**：数据完整性。
- **位置**：`ai-plc-assistant/backend/knowledge/engine.py:68-98`。
- **实际影响**：模型切换、维度不匹配或瞬时异常可能删除用户知识库且无备份。
- **处理方向**：异常 fail-closed；仅在确认迁移时删除；先备份再迁移。
- **动态验证**：需要，临时数据目录。**置信度：高。**

### AUD-P1-10：测试体系既不完整，也有删除真实数据的路径

- **领域**：测试可信度、数据安全。
- **位置**：`pytest.ini:3`、`ai-plc-assistant/backend/pytest.ini:2`、`ai-plc-assistant/backend/tests/conftest.py:13-29,114-131`。
- **实际影响**：根测试遗漏后端、PLC Bridge、机器人和 Bridge；后端 fixture 可能清空真实项目、会话和消息。
- **处理方向**：导入应用前强制重定向到临时存储；建立“离线单元/集成硬件/Bridge”独立测试入口与总表。
- **动态验证**：需要，只能使用复制数据或临时目录。**置信度：高。**

### AUD-P1-11：Bridge 会话复用、审批和结果留存可形成假 PASS

- **领域**：Agent 协作、审查闭环。
- **位置**：`.plans/ai-plc-integration/bridge/ws_task_runner.py:275-293,530-643,683-690`、`.plans/ai-plc-integration/bridge/ack_review.py:104-125`、`.plans/ai-plc-integration/bridge/runner_step.py:125-184`。
- **实际影响**：复用会话不核验真实 CWD/权限；审批不要求有效审查产物；Claude 正文未保存；CLI 执行未固定项目 CWD。
- **处理方向**：侧车元数据回读、审批证据绑定、原始输出或摘要留存、固定命令与工作目录。
- **动态验证**：需要，假侧车和替身 CLI。**置信度：高。**

### AUD-P1-12：V18/V21、工程路径和 PLC IP 默认值冲突

- **领域**：配置与目标身份。
- **位置**：`mcp-servers/tia-mcp/config.yaml:8-15,54`、`mcp-servers/tia-mcp/pipeline.py:32-37`、`scripts/p3_flow.py:31-38`、`.plans/ai-plc-integration/current_chain_report.md:10-15`。
- **实际影响**：不同入口可指向 V18/`.1` 或 V21/`.110`，形成工程与目标漂移。
- **处理方向**：建立唯一配置源；连接和下载前强制比对版本、项目路径、实例名与目标身份。
- **动态验证**：需要，隔离配置。**置信度：高。**

### AUD-P1-13：主要启动入口缺失或路径错误

- **领域**：启动与运维。
- **位置**：`AGENTS.md:20-39`、`README.md:60`、`start.bat:11,29,40,48,53,58,63`、`scripts/p3_flow.py:24-29`。
- **实际影响**：文档推荐的根脚本不存在；批处理切换到父目录；P3 脚本拼出不存在的 `scripts/mcp-servers/tia-mcp`。
- **处理方向**：只保留存在、已验证、明确安全边界的入口；统一项目根计算。
- **动态验证**：需要，隔离启动环境。**置信度：高。**

## P2 中等

### AUD-P2-01：RAG 与客户端 system 消息可污染权威提示词

- **位置**：`ai-plc-assistant/backend/routes/chat.py:100-115`。
- **影响**：恶意知识库文档或调用方 system 消息可改变 PLC 代码建议。
- **处理方向**：拒绝外部 system role；将 RAG 作为不可信引用隔离；生成结果继续受静态校验和人工复核。
- **动态验证**：需要。**置信度：高。**

### AUD-P2-02：部分失败会被 UI 显示为成功

- **位置**：`orchestrator/core.py:484-503`、`ai-plc-assistant/frontend/src/components/OrchestratorPanel.jsx:597-603`、`ai-plc-assistant/frontend/src/api.js:59`、`ai-plc-assistant/frontend/src/components/Sidebar.jsx:128-133`。
- **影响**：操作员可能在实际失败后继续控制，或误以为知识库内容已删除。
- **处理方向**：成功态同时检查 HTTP、结构化 `ok/status` 和逐步骤结果；错误不可吞掉。
- **动态验证**：需要。**置信度：高。**

### AUD-P2-03：API Key 明文持久化且写入非原子

- **位置**：`ai-plc-assistant/backend/storage/app_settings.py:38-54,84-86`。
- **影响**：本机其他进程、备份或崩溃可能造成密钥泄露或设置损坏。
- **处理方向**：凭据库/加密存储、最小 ACL、原子替换和备份。
- **动态验证**：需要检查部署 ACL。**置信度：高。**

### AUD-P2-04：Bridge 无实际并发锁，状态机与依赖不一致

- **位置**：`.plans/ai-plc-integration/bridge/agent-protocol.md:25-33`、`.plans/ai-plc-integration/bridge/runner_dry_run.py:11-44`、`.plans/ai-plc-integration/bridge/ws_task_runner.py:195-232`、`requirements.txt:85`。
- **影响**：多个运行者可覆盖 `state.json`；fallback 因未定义变量静默失效；缺少 `websocket-client` 的受控依赖声明。
- **处理方向**：原子锁、单一状态枚举、完整依赖清单、非法状态组合测试。
- **动态验证**：需要，假侧车。**置信度：高。**

### AUD-P2-05：端口、API 契约和“当前状态”文档已分叉

- **位置**：`start.bat:15,47-49`、`ai-plc-assistant/frontend/vite.config.js:11-19`、`ai-plc-assistant/frontend/src/api.js:3-5`、`.plans/ai-plc-integration/docs/api-contracts.md:7-104`、`CURRENT_STATUS.md:1-43`。
- **影响**：前端可能连接错误端口；调用方可能按过期响应模型或过期完成度判断系统。
- **处理方向**：以运行实现/OpenAPI 为事实源；历史状态文档明确标记为快照。
- **动态验证**：需要，本地隔离 HTTP。**置信度：高。**

### AUD-P2-06：启动时可能重复拉起控制 MCP 子进程

- **位置**：`orchestrator/mcp_client.py:53-86`、`orchestrator/bootstrap.py:60-83`、`start.bat:37-64`。
- **影响**：编排层和批处理入口都可能拉起控制服务，造成资源争用或重复工程会话。
- **处理方向**：明确唯一进程所有者、健康检查和关闭顺序。
- **动态验证**：需要，隔离环境。**置信度：中。**

## P3 一般

### AUD-P3-01：首要指令文件缺失但仍被作为权威引用

- **位置**：`AGENTS.md:78-82`、`README.md:65-67`。
- **影响**：新会话无法按声明优先级读取规则，容易误用旧命令或越界。
- **处理方向**：删除失效引用，或恢复受控的权威文件。
- **动态验证**：不需要。**置信度：高。**

## 未验证事项

以下状态均不能因本文件而视为通过：TIA 是否已加载 V21 工程、PLCSIM 是否运行、下载是否完成、CPU 是否 RUN、snap7 是否可读、网络上是否存在真实 PLC、急停实际接线极性、服务是否对局域网暴露、历史“测试通过”是否可复现。
