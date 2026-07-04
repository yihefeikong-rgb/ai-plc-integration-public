# cc-haha 受控自动化方案设计

> 生成日期：2026-06-24（修正版）
> 基于 `cc_haha_automation_research.md` 调研结论
> 修正说明：第 2 版修正了 port 发现方案和执行链设计

---

## 一、推荐方案：Sidecar API + WebSocket 自动化（路线 A）

### 选择理由

1. cc-haha 已有完整 HTTP REST API（建会话）+ WebSocket（消息交互+权限审批），不需要走 GUI
2. WebSocket 原生支持 `permission_request`/`permission_response`，这是驱动 Claude 执行的必经通道
3. 结构化 JSON 协议比 GUI 截图稳定一个数量级
4. 安全边界清晰（绑定 `127.0.0.1`）

### 不推荐方案

| 方案 | 不推荐理由 |
|------|-----------|
| **B. CLI 子进程** | 无法处理 GUI 弹窗式的权限审批；进程生命周期管理复杂 |
| **C. GUI 桌面自动化** | 脆性、慢、cc-haha 已有 API 不需要走 GUI |

---

## 二、端口发现方案

> ⚠️ **重要修正**：不假设固定端口。cc-haha 桌面端使用 `ElectronServerRuntime.startServer()` 动态分配端口。

### 发现策略（优先级从高到低）

```
1. sticky port 文件
   路径: ~/.claude/desktop-server-state.json
   内容: {"lastPort": 3456}
   说明: 每次启动后由 ElectronServerRuntime.writeLastServerPort() 写入

2. 用户配置的固定端口
   来源: cc-haha settings.json → h5Access.fixedPort
   说明: 用户可在桌面端设置中指定固定端口

3. 端口扫描
   范围: stickyPort ± 10 + 常见端口 3456/3457/3458
   验证: GET /health → 200 { status: 'ok', timestamp }

4. 用户手动指定
   兜底: 允许用户在 bridge 配置中显式指定端口
```

### 集成点

```
外部进程 → 读取 sticky 文件 → 尝试 /health → 确认端口
         → 扫描失败 → 提示用户确认 cc-haha 桌面端是否运行
         → 确认成功 → 缓存端口供本会话使用
```

---

## 三、执行链设计（核心）

> ⚠️ **重要修正**：REST API 只用来建会话，**消息和权限交互全部走 WebSocket**。

### 完整的执行协议

```
步骤 1: REST → 创建会话
  POST /api/sessions
  Response: { id: "session-xxx", ... }

步骤 2: WS → 建立会话通道
  WS /ws/{sessionId}
  ← { type: 'connected', sessionId: "session-xxx" }

步骤 3: WS → 投递用户消息
  → { type: 'user_message', content: '任务描述...' }
  ← { type: 'status', state: 'thinking' }
  ← { type: 'content_start', blockType: 'text' }
  ← { type: 'content_delta', text: '...' }
  ← { type: 'tool_use_complete', toolName, input }

步骤 4: WS → 处理权限请求（如触发）
  ← { type: 'permission_request', requestId, toolName, input }
  → { type: 'permission_response', requestId, allowed: true }

  权限审批策略（受控自动化需要决策的环节）:
  - 安全方案: 自动审批，但只针对白名单工具（MCP 读取类）
  - 保守方案: 拦截权限请求，回退到人工确认
  - 推荐: 第一阶段先保守，标记 BLOCKED 等人审批

步骤 5: WS → 接收完成事件
  ← { type: 'message_complete', usage: {input_tokens, output_tokens} }
  ← { type: 'status', state: 'idle' }

步骤 6: 回填 bridge 文件
  - 拼接流式内容 → claude_result.md
  - 更新 state.json → NEED_CODEX_REVIEW
```

### 受控自动化 MVP 边界

```
REST 建会话 → WS 投消息 → 处理权限 → 收完成 → 回填 → 停在 NEED_CODEX_REVIEW
                                                          ↑ 人工刹车点
```

### 明确不进入自动化的环节

- ❌ 不自动执行 Codex Review
- ❌ 不自动提交 git
- ❌ 不自动启动下一轮任务
- ❌ 不自动审批所有权限（需配置白名单）
- ❌ 不自动重试失败的步骤

---

## 四、集成架构

```
┌────────────────────────────────────────────────────────┐
│                   Bridge Runner                          │
│  runner_step.py（受控单步执行器）                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Phase 6B MVP: cc-haha WS API 适配器              │  │
│  │  ┌──────────┐  ┌─────────────┐  ┌──────────┐    │  │
│  │  │ 发现端口  │→│ REST 建会话   │→│ WS 交互   │   │  │
│  │  │ sticky   │  │ POST /api/   │  │ send msg  │   │  │
│  │  │ /scan    │  │ sessions     │  │rcv status │   │  │
│  │  └──────────┘  └─────────────┘  │rcv perm   │   │  │
│  │                                  │rcv done   │   │  │
│  │                                  └────┬──────┘   │  │
│  │                                       │           │  │
│  │                              ┌────────▼───────┐  │  │
│  │                              │ 回填 bridge 文件 │  │  │
│  │                              │ claude_result   │  │  │
│  │                              │ state.json      │  │  │
│  │                              └────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
         ↑ 集成点：新增独立适配模块
         │ 不修改 runner_step.py 核心逻辑
         │ 不越过 SafetyGate / 不自动进入下一轮
```

### 状态转换

```
发现端口 ─→ REST 建会话 ─→ WS 投消息 ─→ 处理权限 ─→ 收完成 ─→ 回填 ─→ NEED_CODEX_REVIEW
  ↑           ↑             ↑             ↑           ↑         ↑         ↑
  探测失败     API 4xx      WS 断开      超时未决     错误      IO 异常    ⛔ 人工点
  → 回退      → 回退       → 重连        → 回退       → 记录    → 重试    → 停止
```

---

## 五、端口状态机

```
                    ┌─────────────────────┐
                    │    PORT_UNKNOWN      │
                    └─────────┬───────────┘
                              │ 执行发现策略
                    ┌─────────┴───────────┐
                    │                     │
            发现成功 ▼              发现失败 ▼
          ┌──────────────────┐  ┌──────────────────┐
          │  PORT_FOUND       │  │ PORT_NOT_FOUND    │
          │  缓存端口         │  │ 提示启动桌面端     │
          └────────┬─────────┘  └──────────────────┘
                   │ REST 建会话
                   ▼
          ┌──────────────────┐
          │  SESSION_CREATED  │
          │  → WS 连接        │
          └────────┬─────────┘
                   │ WS open
                   ▼
          ┌──────────────────┐
          │  WS_CONNECTED     │
          │  → send user_msg  │
          └────────┬─────────┘
                   │ 收到 message_complete
                   │ 或 error / 超时
          ┌────────┴─────────┐
          │                  │
      完成 ▼           失败/超时 ▼
  ┌──────────────┐  ┌──────────────┐
  │ NEED_CODEX_   │  │   BLOCKED    │
  │   REVIEW      │  │  回退人工    │
  └──────────────┘  └──────────────┘
```

---

## 六、失败回收路径

| 失败场景 | 检测方式 | 回收操作 | 回退路径 |
|----------|---------|---------|---------|
| **端口发现失败** | sticky 文件不存在 + 扫描不通 | 提示启动 cc-haha 桌面端 | 回退到 `runner_step.py --copy` |
| **REST 建会话失败** | HTTP 4xx/5xx | 记录错误，切 BLOCKED | 人工检查 sidecar 状态 |
| **WS 连接断开** | WebSocket onclose | 尝试重连 1 次 | 重连失败 → BLOCKED |
| **权限请求超时** | 5s 内无 `permission_response` | 自动拒绝（allowed: false） | 记录到 result 供人工判断 |
| **Claude 执行错误** | WS 收到 `{ type: 'error' }` | 记录错误码和消息 | 人工分析错误类型 |
| **message_complete 超时** | 5 min 无完成事件 | 发送 `stop_generation` | BLOCKED，保留部分结果 |
| **回填文件写入失败** | IO 异常 | 保留 WS 输出到日志 | 人工手动回填 |

### 核心原则

**所有失败路径最终都回退到人工闭环**。不存在"自动重试→自动修复→自动继续"的完整自动化链。

---

## 七、前置条件检查

| 检查项 | 检测方式 |
|--------|---------|
| cc-haha 桌面端运行中 | `GET /health` 返回 ok |
| sticky port 文件存在 | `~/.claude/desktop-server-state.json` |
| WebSocket 可达 | `WS /ws/health` 或等价探测 |
| 端口未被其他进程占用 | 专属端口确认 |

---

## 八、风险边界

### 不越过的红线

1. **不绕过 SafetyGate** — 自动化只负责投递和回填，不接触 PLC 写入路径
2. **不自动审批所有权限** — 第一阶段仅自动审批读取类工具，写入类权限请求回退人工
3. **不自动进入下一轮** — 严格停在 `NEED_CODEX_REVIEW`
4. **不修改 Bridge 框架文件** — API 适配层是独立模块
5. **不加锁/轮询/自动重试循环** — 所有循环有次数上限并回退人工

### 与第一阶段约束的兼容性

| 第一阶段禁令 | 本方案 |
|-------------|--------|
| 禁止 hooks | ✅ 不涉及 |
| 禁止自动循环 | ✅ 单次 WS 交互，非循环 |
| 禁止自动 retry | ✅ 最多 1 次重连，失败回退人工 |
| 禁止自动 git | ✅ 停在 review 前，不提交 |
| 禁止无人值守 | ✅ 每次停在 NEED_CODEX_REVIEW |
| 禁止修改业务代码 | ✅ 只涉及 bridge/ 协作层 |

---

## 九、下一步实施切片

### Slice 1：端口发现 + 健康探测

```
目标：验证 sidecar 端口发现机制，不做会话投递
范围：
  - 实现 sticky port 文件读取（~/.claude/desktop-server-state.json）
  - 实现 fallback 端口扫描（/health）
  - 输出 sidecar 状态（可用/不可用/端口/URL）
  - 纯只读，不写 bridge 文件（除探测日志）
绕过约束：
  - ✅ 不修改业务代码
  - ✅ 不修改 Bridge 框架
  - ✅ 纯只读操作
```

### Slice 2：REST 建会话 + WebSocket 建立

```
目标：建立完整 WS 连接通道，但只投递非任务消息
范围：
  - POST /api/sessions → 获取 sessionId
  - WS /ws/{sessionId} → 建立连接，验证 connected 事件
  - 发送 `user_message`（内容为"hello"等非业务消息）
  - 验证收到 message_complete
  - 不涉及真实 PLC 任务
验证：
  - 完整 WS 生命周期跑通
  - 确认权限请求格式和响应方式
```

### Slice 3：受控任务投递 MVP

```
目标：用真实 PLC 项目任务驱动一轮 Claude 执行并停在 Review
范围：
  - 读取 task_packet.md → 拼为 user_message
  - WS 投递 → 处理权限请求 → 收 message_complete
  - 流式结果拼接 → 回填 claude_result.md
  - state.json → NEED_CODEX_REVIEW
权限策略：
  - 第一阶段：自动审批读取类工具，写入类权限请求→BLOCKED
  - 第二阶段（人工决定）：扩展白名单或引入人工审批
```

### 推荐执行顺序

```
Slice 1 → Slice 2 → Slice 3
  天1       天1-2     天2-3
```

每个 Slice 可独立验证，独立回退。Slice 3 完成后 Phase 6B 终结。
