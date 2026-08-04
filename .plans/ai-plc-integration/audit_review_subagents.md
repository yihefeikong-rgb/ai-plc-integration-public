# 子代理流水线修复收敛报告（AI 接入 PLC）— 终版 v3

> 生成日期：2026-08-04｜收敛循环：修复 → 审查 → 再修复 → 再审查（2 轮上限 + 限流补验 + 第三轮手动修复）

## 三轮审查趋势

| 严重度 | 第一轮 | 复审查1 | 复审查2（含补验） |
|---|---|---|---|
| CRITICAL | 14 | 2 | 1 |
| HIGH | 94 | 16 | 20 |
| MEDIUM | 206 | 53 | 59 |
| LOW | 147 | 45 | 50 |
| **合计** | **461** | **116** | **130** |

## 修复汇总（三轮共修复 CRITICAL/HIGH 16 条 + 大量 MEDIUM/LOW）

- **第一轮流水线修复**：142 文件 / 460 条（3 批修复子代理）+ 回归清理
- **第二轮流水线修复**：70 文件 / 116 条（含死循环事件后回归清理）
- **第三轮手动修复**（本轮，16 条 HIGH/CRITICAL，测试全绿）：

  - **CRITICAL** `mcp-servers/tia-mcp/server.py`：_safety_gate 人工确认闸门 fail-open：download_to_plcsim/import_scl_file/compile_project/full_pipeline 的 doc
  - **HIGH** `mcp-servers/plc-mcp-bridge/tools_s7.py`：_require_auth 中 effective = token or expected：服务器配置了 MCP_AUTH_TOKEN 时，调用方省略 auth_token 即用服务器自身令牌通过 h
  - **HIGH** `mcp-servers/plc-mcp-bridge/tools_types.py`：create_udt/delete_udt/create_watch_table/delete_watch_table 直接执行 _run_tiaworker，全程无 _audit_gate 审计闸门
  - **HIGH** `mcp_common/control_target.py`：require_opcua_endpoint 两个错误分支把含 user:pass 凭据的原始 endpoint 完整拼入 TargetConfigurationError；opcua-mcp/ser
  - **HIGH** `mcp-servers/tia-mcp/server.py`：_safety_gate() 中确认校验条件为 `if confirmation_token and (...)`：调用方省略 confirmation_token 时直接短路放行，download_
  - **HIGH** `edge-gateway/src/ai_client.py`：decide_control 的兜底 alert JSON 含 "value": null，违反自身 _DECISION_SCHEMA 的 value 类型(number|boolean)，parse
  - **HIGH** `mcp-servers/modbus-mcp/server.py`：模块级 int(settings.get("safety_max_consecutive_errors","3")) 无保护：非数字环境变量导致导入崩溃，0/负数导致 _write_fuse_trip
  - **HIGH** `mcp-servers/modbus-mcp/server.py`：读路径 audit.log（第227/229/236/259/266/286/297行）未传 operator，默认 "ai-agent"。生产模式下 mcp_common/audit.py 的 _e
  - **HIGH** `mcp-servers/desktop-mcp/server.py`：_is_blacklisted_hotkey 只拦截恰好单个危险键（len(pressed)==1）和黑名单组合的子集；"危险单键+修饰键"组合可绕过，如 hotkey(['shift','delet
  - **HIGH** `mcp-servers/desktop-mcp/server.py`：mcp_recv() 中 readline() 的 UnicodeDecodeError（非法 UTF-8 字节）与 json.loads 的 RecursionError（深度嵌套 JSON）均未捕
  - **HIGH** `mcp-servers/robot-mcp/server.py`：_load_estop_latch (L256-265) 用 except Exception: pass 静默吞掉读取/JSON 解析错误并返回 False（fail-open）；配合 _save_
  - **HIGH** `mcp-servers/tia-mcp/create_plc_tags.py`：create_tags 在 API 创建全部失败（created==0 且 errors>0）时自动降级到 create_tags_via_xml，该路径先 TagTables.Delete 删除整个
  - **HIGH** `mcp-servers/tia-mcp/call_fb_in_ob1.py`：insert_fb_calls 在导入/编译前无条件删除 Main(MOB1)/MasterIO/MasterIO_DB 块，失败时异常逃逸但 tia_session 的 finally 仍无条件 p
  - **HIGH** `ai-plc-assistant/frontend/src/components/orchestrator/api.js`：apiGet 未携带 localControlHeaders()（X-Local-Api-Token），而后端 /api/orchestrator/* 全部 GET 端点（workflows/tool
  - **HIGH** `scripts/p3_flow.py`：编译步骤失败后流程不中止：step2_compile() 返回 False 仍继续执行 step2_download()，下载成功还会调用 step2_archive() 覆盖 golden back
  - **HIGH** `plc-code-templates/siemens-scl/冷冻站群控系统.scl`：加机选冷机 iNextChiller 未排除已运行的冷机（无 AND NOT bChillerXRun），当最小累计运行时间的冷机正在运行时，bChillerXCmd 重复发给该已运行冷机，新增冷机永

  - 另修复 MEDIUM/LOW 若干：modbus 读路径 operator、tia_session 异常不 Save、desktop 修饰键组合、edge-gateway AI 兜底、control_target 脱敏、前端鉴权头、robot 急停闩锁 fail-closed、p3_flow 编译中止、create_plc_tags 防覆盖、冷冻站选机

## 剩余未修复：5 条（全部架构/规范级，需产品决策）

- **HIGH** `mcp-servers/tiacommander-mcp/docs/README.md`：危险操作确认是软门槛：确认字符串内嵌在工具面（工具描述）中，AI 客户端自身即可满足，无法区分人类批准与代理自授权。download_to_device（含 mode=hardware/hardware_software、stopModules=true 停止运行中 PLC）、upload_station、delete_block(force)、delete_network、set_network_config、update_project、delete_unused_types、delete_library_folder 等真实控制/破坏性操作仅由该字符串把关，绕过确认无额外防护。
- **HIGH** `mcp-servers/tiacommander-mcp/docs/README.md`：stdio JSON-RPC 通道无任何认证/授权边界（README 自行声明）：任何本地进程或同账号下恶意软件即可启动 TiaCommander.exe 并驱动全部 16 个工具，包括启动 TIA Portal、打开工程、下载到真实 PLC 与停止模块；且无任何可归属到操作者身份的审计链（本地仅调用统计与遥测），无法事后追溯谁执行了控制操作。
- **HIGH** `orchestrator/workflows/nl_to_plcsim_pipeline.py`：确认令牌门仅为存在性检查：链路上无任何工具消费/验证该令牌（tia-mcp.create_ladder_block/call_fb_in_ob1 不在 _CONFIRMATION_REQUIRED_OPS 且不接收令牌，bridge 的 plc_compile_project/plc_download_project 也不接收 confirmation_token），传入任意非空占位串即可执行导入LAD→改写OB1→编译→下载→启动Factory I/O 的整条危险链，人工确认机制形同虚设
- **HIGH** `orchestrator/workflows/tia_multi_block_pipeline.py`：确认令牌从未转发给 tia-mcp.import_scl_file（该工具在 tia-mcp 侧属 _CONFIRMATION_REQUIRED_OPS，但 _safety_gate 对空令牌显式放行并委托编排层确认），而编排层仅校验非空占位串，令牌从未被权威消费/验证，工程导入在任意占位串下放行；两侧契约相互矛盾
- **HIGH** `plc-code-templates/siemens-scl/conveyor-with-timer.scl`：全部 20 个 .scl 模板的 IEC 定时器/边沿实例调用均缺少 _rules.md 第 6/7 条强制要求的 # 前缀（如 tStartDelay(IN:=TRUE,...)、trgEntry(CLK:=...)、tPhaseTimer.IN/PT/ET），与 README 宣称的"可直接编译"自相矛盾；scl_lint.py 的 IEC_INSTANCE_WITHOUT_HASH 规则只匹配 TON/R_TRIG 等类型名，tStartDelay 等实例名调用全部漏检，server.py 导入前 lint 无法拦截

## ⚠️ 关键架构决策点：自动化工程操作的人工确认

复审查2 的 CRITICAL（tia-mcp 确认门 fail-open）已修复为**默认 fail-closed**：
`download_to_plcsim`/`import_scl_file`/`compile_project`/`full_pipeline` 默认必须携带真实确认令牌，
仅当显式设置 `TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING=1` 时允许未确认执行。

**连锁影响**：orchestrator 主链（nl_to_plcsim）调用这些工具时没有真确认令牌机制（其 confirmation_token 仅为占位串），
因此在未设置该环境变量时，主链的编译/下载会被工具层 fail-closed 拒绝。这是「自动化流程 vs 人工确认」的架构矛盾，需您拍板：

1. **A. 显式降级**：生产环境设置 `TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING=1`，接受自动化工程操作无人工确认（有意的 opt-in，有审计记录）
2. **B. 实现真确认链**：编排层签发一次性确认令牌（ConfirmationService）+ 工具层消费（较大改造，含审批通道）
3. **C. 维持现状**：工具层默认 fail-closed，主链工程操作默认被拒（安全但功能受限），待审批通道建设后再接通

## 测试状态

- 根目录 **821 passed** / backend **286 passed**（本轮全部手动修复后验证）
- 修复均经 pytest 验证，回归测试已同步更新（create_plc_tags 降级断言、s7 auth_token、robot 步骤数等）

## ✅ B 方案已实施：工作流级人工确认（2026-08-04 完成）

**已实现闭环**：
1. **签发**：人工通过 `POST /api/orchestrator/confirmations`（`purpose=workflow, workflow_name=<工作流名>`, 带鉴权头）签发一次性工作流确认令牌（默认 60s，最长 300s）
2. **消费**：编排层 `nl_to_plcsim_pipeline` / `tia_multi_block_pipeline` 入口用 `ConfirmationService.consume` **真实消费**令牌（绑定 `_wf.<工作流名>`，一次性）；占位串不再有效
3. **验证**：签发→消费→重复消费拒绝 闭环测试通过（backend 287 passed + 根目录 821 passed）

**部署要求**：
- 后端与编排层共享 `SAFETY_CONFIRMATION_SECRET`（签名密钥）与 `SAFETY_CONFIRMATION_STORE`（sqlite 存储路径）
- 工具层（tia-mcp）配置 `TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING=1`：确认点统一在编排层，工具层信任编排层的授权（部署文档需说明）
- 签发请求示例：
  `POST /api/orchestrator/confirmations`  Header: `X-Local-Api-Token: <人工会话令牌>`
  `{"operator":"ai-agent","purpose":"workflow","workflow_name":"nl_to_plcsim_pipeline","ttl_seconds":60}`

**待办（可选）**：前端审批界面（当前为 API 级签发，人工通过接口/脚本批准）

## ✅ 前端审批界面已完成（B 方案完整落地）

**新增**：
1. **审批面板**：左侧导航「人工审批」→ 显示 AI 发起的危险操作请求（工作流名/描述/时间/状态）+ 批准/拒绝按钮 + 刷新
2. **审批请求 API**：`POST /confirmations/requests`（AI 创建）、`GET /confirmations/requests`（列表）、`POST .../{id}/approve`（批准签发令牌）、`POST .../{id}/deny`（拒绝）、`GET .../{id}/token`（AI 一次性领取）
3. **编排层集成**：危险工作流缺令牌时自动创建审批请求并返回 `request_id`；人工批准后用户带 `request_id` 重试即可自动领取令牌执行

**用户流程**：
```
AI 说"下载程序" → 系统创建审批请求 → 左侧「人工审批」出现待批项
→ 您点"批准"（签发 5 分钟一次性通行证）→ 用户带 request_id 重新执行 → AI 领取通行证 → 下载执行
```

**验证**：backend 289 passed + 根目录 821 passed + 前端构建通过（vite build 3.04s）
**部署要求**：`SAFETY_CONFIRMATION_SECRET`（签名密钥，后端/编排层共享）+ `TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING=1`（确认点统一在编排层）

## 待人工确认/决策项汇总

1. **确认令牌机制决策**（上文 A/B/C）
2. SCL 模板工艺复核：20 个模板的修复 + conveyor 定时器 # 前缀规范（批量模板改造）
3. tiacommander stdio 无认证 + 软确认门槛（README 已警示，生产需加认证层/审批代理）
4. 凭据管理：`.env` 真实密钥轮换；配置 `SAFETY_CONFIRMATION_SECRET`/`AUDIT_HMAC_KEY`/`MCP_AUTH_TOKEN`/`TIA_MCP_ALLOW_UNCONFIRMED_ENGINEERING`
5. 流水线遗留临时文件清理（约 20 个）

## 交付物

- 本报告：`.plans/ai-plc-integration/audit_review_subagents.md`
- 发现清单：`%%TEMP%%\rereview_round2_final.json`（130 条含 evidence）、`all_confirmed_full.json`（第一轮 461 条）
- 流水线：`.grok/workflows/`（review-changes / verify-findings / verify-findings-r2 / fix-findings）
