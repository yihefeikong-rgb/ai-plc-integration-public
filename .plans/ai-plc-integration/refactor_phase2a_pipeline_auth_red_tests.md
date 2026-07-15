# Pipeline 输入边界与 MCP 凭据契约实施计划

> **状态：已完成。** 2026-07-15 先完成本文件规定的 RED 阶段；用户随后明确授权第二阶段 B 的最小生产实现，GREEN 结果见 `refactor_phase2a_red_test_results.md`。本文件保留为 TDD 证据，不得再次当作活动任务执行。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划只执行红测阶段，不修改生产代码。

**Goal:** 用两组纯离线失败测试固定 Pipeline 执行元数据边界和 MCP 内部凭据注入契约，防止后续重构继续被 mock 单测的绿色结果掩盖。

**Architecture:** `authenticated_operator` 属于编排执行上下文，不属于用户业务输入，但必须能随上下文抵达审计层。MCP 令牌属于传输层秘密，由 `McpClientAdapter` 在调用边界按服务器配置注入；工作流、API 请求和调用者参数都不能携带或覆盖令牌。

**Tech Stack:** Python 3.13、pytest、pytest-asyncio、MCP Python SDK、现有 `OrchestratorEngine` / `McpClientAdapter`。

---

## 任务边界

本轮执行者只能修改：

- `orchestrator/tests/test_nl_to_plcsim_live_contract.py`
- `orchestrator/tests/test_mcp_credentials_contract.py`（新建）
- `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`（新建）

不得修改任何生产代码。不得运行真实 MCP、TIA、PLCSIM、Factory I/O、后端服务或网络测试。不得执行 Git 暂存、提交和推送。

成功标准不是“测试全绿”，而是以下契约以稳定、可解释的方式失败：

1. Pipeline 接收到 API 注入的 `authenticated_operator` 后不应把它识别为非法业务字段。
2. 已声明需要凭据的 MCP 服务器，调用时应由 adapter 注入令牌。
3. 调用者不能通过工具参数自带或覆盖 `auth_token`。
4. 所需凭据缺失时必须在调用 MCP session 前失败关闭。

---

### Task 1：固定 Pipeline 执行元数据契约

**Files:**

- Modify: `orchestrator/tests/test_nl_to_plcsim_live_contract.py`
- Production reference only: `orchestrator/workflows/nl_to_plcsim_pipeline.py:9-49`
- Production reference only: `ai-plc-assistant/backend/routes/pipeline.py:86-93`

- [ ] **Step 1：在现有契约测试文件末尾加入失败测试**

```python
@pytest.mark.asyncio
async def test_nl_to_plcsim_accepts_authenticated_actor_as_execution_metadata():
    engine = OrchestratorEngine(registry=Registry())
    pool = ContractPool()
    engine.set_pool(pool)
    engine.set_safety_gate(AllowSafetyGate())
    register_nl_to_plcsim_pipeline_workflow(engine)

    result = await engine.run_async(
        "nl_to_plcsim_pipeline",
        input={
            "description": "电机启停",
            "block_name": "MotorControl",
            "authenticated_operator": "local-session:test-actor",
        },
    )

    assert result.ok is True
    assert result.error == ""
    assert pool.calls == ContractPool.expected_calls
```

- [ ] **Step 2：只运行该测试并确认失败原因精确**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:/Python3/python.exe -m pytest -p no:cacheprovider orchestrator/tests/test_nl_to_plcsim_live_contract.py::test_nl_to_plcsim_accepts_authenticated_actor_as_execution_metadata -q
```

Expected: `FAIL`，且失败结果中的错误必须包含：

```text
不支持的工作流参数: authenticated_operator
```

同时 `pool.calls` 必须为空，证明失败发生在第一个 MCP 调用之前。

- [ ] **Step 3：记录根因，不修改生产代码**

在结果文件中记录：业务字段白名单与执行元数据共用同一 `ctx.input`，导致后端安全注入反而使工作流不可执行。建议后续生产实现采用独立的 `WorkflowExecutionMetadata` 或 `WorkflowContext.actor`，不要简单把 `authenticated_operator` 加入用户字段白名单。

---

### Task 2：固定 MCP 凭据注入契约

**Files:**

- Create: `orchestrator/tests/test_mcp_credentials_contract.py`
- Production reference only: `orchestrator/registry.py:81-90`
- Production reference only: `orchestrator/mcp_client.py:67-74,144-173`
- Production reference only: `orchestrator/server_configs.py:25-70`

- [ ] **Step 1：新建测试文件并写入以下完整内容**

```python
"""MCP 凭据必须由传输边界注入，调用者不得携带或覆盖秘密。"""

from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, TextContent

from orchestrator.mcp_client import McpClientAdapter
from orchestrator.registry import ServerInfo


def _successful_session() -> AsyncMock:
    session = AsyncMock()
    session.call_tool = AsyncMock(
        return_value=CallToolResult(
            content=[TextContent(type="text", text='{"ok": true}')],
            isError=False,
        )
    )
    return session


def _connected_adapter(server: ServerInfo) -> tuple[McpClientAdapter, AsyncMock]:
    adapter = McpClientAdapter(server)
    session = _successful_session()
    adapter._session = session
    adapter._connected = True
    return adapter, session


@pytest.mark.asyncio
async def test_adapter_injects_server_credential_without_mutating_caller_arguments(
    monkeypatch,
):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "internal-secret")
    server = ServerInfo(
        name="tia-mcp",
        credential_env="TIA_MCP_AUTH_TOKEN",
        credential_argument="auth_token",
    )
    adapter, session = _connected_adapter(server)
    caller_arguments = {"description": "电机启停", "block_name": "MotorControl"}

    result = await adapter.call_tool("create_ladder_block", caller_arguments)

    assert result.ok is True
    assert caller_arguments == {
        "description": "电机启停",
        "block_name": "MotorControl",
    }
    session.call_tool.assert_awaited_once_with(
        name="create_ladder_block",
        arguments={
            "description": "电机启停",
            "block_name": "MotorControl",
            "auth_token": "internal-secret",
        },
    )


@pytest.mark.asyncio
async def test_adapter_rejects_caller_supplied_credential(monkeypatch):
    monkeypatch.setenv("TIA_MCP_AUTH_TOKEN", "internal-secret")
    server = ServerInfo(
        name="tia-mcp",
        credential_env="TIA_MCP_AUTH_TOKEN",
        credential_argument="auth_token",
    )
    adapter, session = _connected_adapter(server)

    result = await adapter.call_tool(
        "create_ladder_block",
        {"description": "电机启停", "auth_token": "caller-controlled"},
    )

    assert result.ok is False
    assert result.kind == "credential_override"
    session.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_adapter_fails_closed_before_session_call_when_credential_is_missing(
    monkeypatch,
):
    monkeypatch.delenv("TIA_MCP_AUTH_TOKEN", raising=False)
    server = ServerInfo(
        name="tia-mcp",
        credential_env="TIA_MCP_AUTH_TOKEN",
        credential_argument="auth_token",
    )
    adapter, session = _connected_adapter(server)

    result = await adapter.call_tool(
        "create_ladder_block",
        {"description": "电机启停"},
    )

    assert result.ok is False
    assert result.kind == "credential_missing"
    session.call_tool.assert_not_awaited()
```

- [ ] **Step 2：运行凭据契约测试并确认是设计缺口导致失败**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:/Python3/python.exe -m pytest -p no:cacheprovider orchestrator/tests/test_mcp_credentials_contract.py -q
```

Expected: `FAIL`。当前首个明确失败应为 `ServerInfo.__init__()` 不接受 `credential_env`，证明服务器配置尚无凭据元数据；不得通过删除测试字段或让工作流显式传 token 来规避。

- [ ] **Step 3：检查测试中没有泄漏真实秘密**

Run:

```powershell
rg -n "internal-secret|caller-controlled" orchestrator/tests/test_mcp_credentials_contract.py
```

Expected: 只命中测试固定字符串；不得读取、打印或复制本机真实 `.env` 内容。

---

### Task 3：验证既有离线基线未被测试文件之外的改动影响

**Files:**

- Create: `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`

- [ ] **Step 1：确认改动范围**

Run:

```powershell
git status --short
git diff -- AGENTS.md orchestrator/tests/test_nl_to_plcsim_live_contract.py orchestrator/tests/test_mcp_credentials_contract.py .plans/ai-plc-integration/refactor_phase2a_red_test_results.md
```

Expected: 除用户原有未跟踪文件外，只出现本计划明确授权的文件。发现其他文件变化立即停止，不得清理用户改动。

- [ ] **Step 2：运行原有测试，排除测试编写造成的导入副作用**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:/Python3/python.exe -m pytest -p no:cacheprovider -q --ignore=orchestrator/tests/test_mcp_credentials_contract.py -k "not test_nl_to_plcsim_accepts_authenticated_actor_as_execution_metadata"
```

Expected: 原有基线保持 `306 passed, 41 deselected`；新增红测被明确排除。

- [ ] **Step 3：写入结果文件**

结果文件必须包含：

```markdown
# Phase 2A Red Test Results

- Baseline commit: 4db8f25f98090838e8020bdf4c2f724228358efa
- Production files changed: none
- Existing offline baseline: 306 passed, 41 deselected
- Pipeline metadata contract: RED — `不支持的工作流参数: authenticated_operator`，且 MCP 调用数为 0
- MCP credential contract: RED — `ServerInfo.__init__()` 不接受 `credential_env`，凭据元数据尚不存在
- Hardware or desktop actions: none
- Requested next state: NEED_CODEX_REVIEW
```

- [ ] **Step 4：停止并交回审查**

不得修改生产代码，不得继续执行绿色实现，不得提交或推送。向 Codex 提供：改动文件列表、两组红测输出、原有基线输出和任何与计划不一致之处。

---

## 后续绿色实现方向（本轮禁止执行）

下一轮经 Codex 审查和用户再次授权后，才允许规划生产修改：

1. 将 actor 从用户业务输入中分离为不可由请求覆盖的执行元数据。
2. 为 `ServerInfo` 增加最小凭据元数据，但不存储秘密值。
3. 在 `McpClientAdapter.call_tool()` 内复制参数、拒绝调用方自带凭据、从环境读取并注入秘密。
4. 日志与审计只记录凭据已配置状态，绝不记录令牌值。
5. 所有注册工作流继续以无 `auth_token` 的参数调用 MCP。

本计划不授权上述生产实现。
