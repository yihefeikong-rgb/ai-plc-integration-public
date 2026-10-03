# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Windows 本地工业自动化 AI 工作台与**受控仿真**研发平台：自然语言 → LLM 生成 LadderSpec/SCL → CartGen/SimaticML → 编译下载到隔离 PLCSIM → snap7 只读回读 → 可选 Factory I/O。

它不是安全 PLC、急停回路替代品，也未经真实产线认证。

## 安全红线（优先于交付速度）

- 禁止 AI 操作急停回路、F-CPU 或安全 PLC 逻辑参数。
- 不得绕过认证、一次性确认令牌、互锁规则、影子仿真或 HMAC 审计链。令牌/密码/API Key 不得写入日志、提交或回复。
- 启动 TIA、PLCSIM、Factory I/O、真实 MCP 子进程、后端服务或任何可能读写控制目标的程序，**必须先获得用户对该次动态操作的明确授权**。
- 报告动态验证必须按证据层级区分：进程存在 → 项目已加载 → 下载完成 → CPU RUN → PLC 可读。不得合并成"已测试通过"，不得用 mock 成功替代现场成功。
- 固定环境：Python `D:\Python3\python.exe`（3.13）、TIA Portal V21、PLCSIM Advanced V8。

## 常用命令

### Python（后端 / 编排层 / 安全层）

```bash
# 默认离线测试（根级 pytest.ini 收集 tests + orchestrator/tests，
# 排除 integration/hardware/desktop/network/plcsim/real/tia/tiacommander 标记）
D:/Python3/python.exe -m pytest -p no:cacheprovider -q

# 单个测试文件 / 单个用例
D:/Python3/python.exe -m pytest tests/test_safety_validator.py -q
D:/Python3/python.exe -m pytest tests/test_safety_validator.py::test_name -q

# 只读环境门槛检查（不触发下载或 PLC 读写）
D:/Python3/python.exe scripts/preflight.py --json

# 后端 FastAPI（端口 8005，内部 orchestrator 是唯一 MCP 生命周期所有者）
start.bat
```

`ai-plc-assistant/backend/pytest.ini` 与根 `pytest.ini` 是**两套独立配置**（backend 用 `asyncio_mode=auto`）。两处 `tests` 包同名，必须分开运行，避免导入路径冲突。

### 前端（React / Vite / Electron）

```bash
cd ai-plc-assistant/frontend
npm ci
npm run dev              # Vite 5173 + Electron
npm run test             # vitest run（单元测试）
npm run test:e2e         # playwright
npm run build            # vite build
npm run dist             # vite build + electron-builder（NSIS 打包）
```

### 其他

```bash
python -m plc_gateway.server     # PLC Gateway（只读影子模式），根级 plc_gateway/ 是路径垫片
make build-v21                   # TiaWorker: dotnet build -p:TiaVersion=V21
```

注意 `.claude/settings.local.json` 配置了 PostToolUse 钩子：编辑 `.py` 会自动跑 black + ruff，编辑 `safety/` 或含急停语义路径会弹安全提醒。看到非预期 diff 属正常。

## 架构

### 分层与数据流

```text
Electron + React 工作台 (Vite 5173)
   │  127.0.0.1 HTTP，X-Local-API-Token 保护控制类端点
   ▼
FastAPI 后端 (ai-plc-assistant/backend, 端口 8005)  ── 知识库/搜索/会话/设置 (SQLite + ChromaDB)
   │
   ▼
Orchestrator (orchestrator/)  ── MCP 子进程连接池 + 工作流引擎 + 单一生命周期所有者锁
   ├── plc-mcp-bridge        S7 运行态 / TIA 工程态 / PLCSIM / Factory I/O / 标签 / 块
   ├── tia-mcp               FastMCP + C# TiaWorker (Openness) + .NET CartGen
   ├── plc-gateway           FastMCP 只读影子模式（Provider: TiaWorker / TiaCommander）
   └── opcua / modbus / mitsubishi / robot-mcp
   │
   ▼
安全层 (safety/ + mcp_common/) ── 互锁校验 → 影子仿真 → 审计 → 一次性确认 → 实际写入
   │
   ▼
TIA Portal V21 / PLCSIM Advanced / Factory I/O（仅人工验收时）
```

### 关键机制

- **`WorkflowContext.call()` 是唯一的工具调用入口**（`orchestrator/core.py`）。工具全名格式 `server.tool`；优先级 mock > MCP 池。写入走 `SafetyGate`，控制类动作写审计，结果经 `_unwrap_tool_result` 拒绝失败载荷。
- **写入工具必须显式登记参数契约**（`WRITE_TOOL_PARAMS`）：目标/值参数名逐工具声明（`s7_write.address`、`opcua_write.node_id`、modbus 整数 `address`、三菱 `addr`）。未登记 → fail-closed。
- **唯一控制目标**：`mcp-servers/tia-mcp/config.yaml` 的 `target` 节是 V21 版本、工程路径、PLCSIM 实例名、设备名、PLC IP（`192.168.0.1`）的**唯一来源**。入口统一走 `mcp_common/control_target.py`；IP/OPC UA 端点漂移会被拒绝，不得从文档、环境或用户输入旁路覆盖。
- **MCP 生命周期单一所有者**：后端启动时持 `McpOwnerLock`，第二个所有者失败关闭，避免重复拉起 stdio 子进程。
- **工作流级人工确认**：危险工作流（`nl_to_plcsim_pipeline`、`tia_multi_block_pipeline`）在入口消费一次性令牌（绑定 `_wf.<工作流名>`）；缺令牌时创建人工审批请求，审批后签发 5 分钟令牌。
- **PLC Gateway 处于迁移期**：根级 `plc_gateway/` 只是包路径垫片，实现位于 `mcp-servers/plc-gateway/`（目录连字符）。当前只读工具 + 影子比较，**不开放写工具**。

### 领域要点

- 匈牙利命名法：`b`=Bool、`n`=Int/Word、`i`=DInt、`r`=Real、`t`=Timer、`q`=输出、`s`=字符串。
- ChromaDB 路径：`ai-plc-assistant/backend/data/vector_db`（非 `data/chroma_db`）。
- PLCSIM 实例名 ≤ 8 字符；下载前 PLC 必须 STOP；TIA 一次只能开一个实例，Openness 操作在主线程。

## 不可破坏约束

完整清单见 `.plans/ai-plc-integration/docs/invariants.md`（INV-1…INV-12，违反即 BLOCK）。要点：不碰急停/F-CPU、所有写入过影子仿真、生产写入双人确认、HMAC 链式审计不可篡改、安全相关代码（`safety/`、写入、互锁）须独立 reviewer 审查。

## Git 与文档

- 远端：`origin` = 私有主仓 `ai-plc-integration`，`public` = 公开镜像 `ai-plc-integration-public`。推送 public 必须明确授权。
- 未经明确要求，不执行 `git add` / `commit` / `push` / `reset` / 强推 / 删分支；保留用户已有的未提交与未跟踪文件。
- 改变用户可见能力、架构入口、控制/安全/认证边界、依赖或默认测试范围的重大变更，必须在**同一提交**同步 `README.md` 与 `README_EN.md`。

## 背景文档

`README.md`（当前状态边界）· `CLAUDE.md` 本文件 · `.plans/ai-plc-integration/`（handoff / task_plan / progress / findings / decisions）· `AI_CONTEXT.md`（PLC 领域知识）· `ARCHITECTURE.md`。`CURRENT_STATUS.md`、`PROJECT_HANDOVER.md` 为历史快照，可能滞后，冲突时以代码、`config.yaml` 和实际运行证据为准。
