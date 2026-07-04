# cc-haha 自动化接入可行性调研

> 生成日期：2026-06-24（修正版）
> 调研方式：GitHub 仓库只读分析（公开仓库 NanmiCoder/cc-haha）
> 目的：评估 cc-haha 可自动化入口，确定受控自动化最优路线
> 修正说明：第 2 版修正了端口发现机制和 WebSocket 执行链

---

## 一、cc-haha 架构摘要

### 三层架构

```
┌───────────────────────────────────────────────────────┐
│                  Desktop (Electron)                     │
│   React/Vite Renderer ←IPC→ Electron Main Process      │
│   ┌─────────────────────────────────────────────────┐ │
│   │            Sidecar（统一二进制 claude-sidecar）     │ │
│   │  server 模式     │  cli 模式  │  adapters 模式     │ │
│   │  动态端口         │  Commander  │  飞书/微信/Telegram │
│   └──────────────────┴───────────┴───────────────────┘ │
│                ↑ 通过 ElectronServerRuntime 启动         │
└───────────────────────────────────────────────────────┘
         ↑ IPC: runtimeGetServerUrl
┌────────┴──────────┐     ┌──────────────┐
│  Renderer (GUI)   │     │  外部 API 客户端  │
│  ipcRenderer.invoke│     │  未知端口需发现    │
│  (runtimeGetServer│     │                  │
│   Url) → URL      │     │                  │
└───────────────────┘     └──────────────────┘
```

### 关键文件

| 文件 | 用途 |
|------|------|
| `./bin/claude-haha` | CLI 入口点（Commander.js + Ink） |
| `desktop/sidecars/claude-sidecar.ts` | 统一 sidecar 二进制（server/cli/adapters 三模式） |
| `desktop/electron/main.ts` | Electron 主进程，通过 `ElectronServerRuntime` 启动 server |
| `desktop/electron/services/serverRuntime.ts` | **端口分配核心**：`reserveServerPort` 动态端口 + `getServerUrl()` |
| `desktop/electron/services/sidecarManager.ts` | 实际 spawn sidecar 进程，透传 `--host` `--port` |
| `desktop/electron/ipc/channels.ts` | `runtimeGetServerUrl` IPC 通道 |
| `src/server/router.ts` | 28 条 HTTP REST API 路由 |
| `src/server/ws/handler.ts` | WebSocket 连接处理器（消息路由+会话绑定） |
| `src/server/ws/events.ts` | **WebSocket 消息类型定义**（关键） |

---

## 二、自动化入口清单

### 入口 1：Sidecar Server API ⭐（推荐）

#### 端口发现机制（重要）

cc-haha 桌面端**不是**固定端口。`ElectronServerRuntime.startServer()` 使用以下优先级分配端口：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1（最高） | `h5Access.fixedPort` 配置 | 用户可在 cc-haha 设置中指定的固定端口，存于 `settings.json` |
| 2 | `desktop-server-state.json` → `lastPort` | 上一次运行的端口号，从 `desktop-server-state.json` 读取 |
| 3（兜底） | OS 随机分配 | `reserveLocalPort(0)` 绑定到端口 0，由操作系统分配 |

端口分配发生在 `reserveServerPort()` 函数中：
```
preferredPorts = [fixedPort, lastPort]  // 有序
for port in preferredPorts:
    if tryReserve(port): return port
return reserveLocalPort(0)  // 随机端口
```

**外部发现方式**（非 Electron 客户端）：

对于 Bridge runner 这类外部进程，无法直接调用 Electron IPC，需要通过以下方式发现端口：

1. **优先读取 sticky 文件**：`~/.claude/desktop-server-state.json` 中的 `lastPort` 字段（该文件在每次启动后由 `writeLastServerPort()` 写入）
2. **备选端口扫描**：在 `127.0.0.1` 上对常见端口范围 + lastPort ± 10 探测 `/health`
3. **用户配置覆盖**：如果用户配置了 `h5Access.fixedPort`，优先检测该端口

#### API 路由

| 方法 | 路径 | 用途 |
|------|------|------|
| GET/POST | `/api/sessions` | 会话管理（创建/列表） |
| GET/POST | `/api/tasks` | 任务管理 |
| GET | `/api/status` | 服务器状态 |
| GET | `/api/scheduled-tasks` | 定时任务（可选用于任务投递） |
| GET/POST | `/api/settings` | 配置管理 |
| GET | `/api/models` | 模型配置 |
| GET | `/api/agents` | Agent 管理 |
| WS | `/ws/{sessionId}` | **WebSocket 会话通道（执行链关键）** |
| WS | `/sdk/{sessionId}` | SDK 内部通道（需 token 认证） |

**端口总结**：不要假设固定 `3456`。正确的集成方式是：
1. 读取 sticky 文件发现端口
2. 或扫描 `/health` 探测
3. 或由用户在配置中显式指定

#### WebSocket 执行协议（关键）

这是驱动 Claude 执行的核心协议。**REST API 只用于建立会话，消息和权限交互全部走 WebSocket。**

**连接流程：**
```
1. POST /api/sessions → 创建会话，返回 sessionId
2. WS /ws/{sessionId} → 建立 WebSocket 连接
   Server → Client: { type: 'connected', sessionId }
3. Client → Server: { type: 'user_message', content: '任务描述...' }
4. Server → Client: { type: 'status', state: 'thinking' }
5. Server → Client: { type: 'content_start', blockType: 'text', ... }  (流式输出开始)
6. Server → Client: { type: 'content_delta', text: '...' }            (流式内容)
7. Server → Client: { type: 'tool_use_complete', toolName, input }    (工具调用)
8. 若需要权限:
   Server → Client: { type: 'permission_request', requestId, toolName, input }
   Client → Server: { type: 'permission_response', requestId, allowed: true }
9. Server → Client: { type: 'message_complete', usage: {input_tokens, output_tokens} }
10. Server → Client: { type: 'status', state: 'idle' }
```

**关键 WebSocket 消息类型：**

| 方向 | 类型 | 用途 |
|------|------|------|
| Client→Server | `user_message` | 发送用户文本+附件（**任务投递入口**） |
| Client→Server | `permission_response` | **权限审批响应**（allowed/denied） |
| Client→Server | `stop_generation` | 中断生成 |
| Client→Server | `ping` | 心跳保活 |
| Server→Client | `connected` | 连接确认 |
| Server→Client | `status` | 状态变化（thinking/idle/compacting 等） |
| Server→Client | `content_start/delta` | 流式文本输出 |
| Server→Client | `tool_use_complete` | 工具调用完成 |
| Server→Client | `permission_request` | 权限申请（**需客户端响应**） |
| Server→Client | `message_complete` | **一条消息执行完成**（含 token 用量） |
| Server→Client | `error` | 错误通知（CLI_ERROR/API_ERROR 等） |

**关键设计约束：**

- `user_message` 是**唯一**的投递入口。REST API 没有 `POST /api/chat` 这样的直接消息接口。
- `permission_request` 和 `permission_response` 是异步配对的。如果自动化不处理权限响应，Claude 会在 `permission_pending` 状态挂起。
- `message_complete` 不带最终结果文本，需要自己从 `content_start/delta` 流式事件中拼接。

### 入口 2：CLI 子进程

| 属性 | 值 |
|------|------|
| **启动命令** | `bun run ./bin/claude-haha [args]` |
| **交互方式** | stdio + 退出码 |
| **运行时依赖** | Bun |
| **优势** | 简单直接，不依赖 sidecar 进程 |
| **劣势** | 无 API 粒度控制，每次启动新进程，无法处理权限交互 |

### 入口 3：Desktop GUI 自动化

| 属性 | 值 |
|------|------|
| **方式** | Electron computer-use 模块 + IPC |
| **风险** | 高——脆性、慢、难以维护 |
| **不推荐理由** | cc-haha 已有完整 API，不需要走 GUI 自动化 |

---

## 三、三条路线对比

| 维度 | A. Sidecar API 自动化 | B. CLI 子进程 | C. GUI 桌面自动化 |
|------|----------------------|--------------|-----------------|
| **端口/入口** | 动态端口需发现 | 不依赖端口 | Electron IPC |
| **执行粒度** | 精细（WS 消息级） | 粗（整进程） | 最粗（屏幕级） |
| **权限处理** | ✅ WS 原生支持 | ❌ 无法处理 GUI 弹窗 | ✅ 可处理但复杂 |
| **可靠性** | 高（WS 有重连机制） | 中（进程管理复杂） | 低（GUI 变化影响） |
| **实现复杂度** | 中（WS 客户端） | 低（进程 spawn） | 高（截图+OCR+点击） |
| **适合场景** | **受控自动化 MVP** | 备选 | 不推荐 |

### 结论：为什么优先 API 自动化而不是 GUI 自动化

1. **cc-haha 已有完整 HTTP/WebSocket API** — WebSocket 是官方提供的 Claude 会话交互通道
2. **WebSocket 原生支持权限交互** — `permission_request`/`permission_response` 机制可直接处理 Claude 的工具权限审批
3. **API 比 GUI 更可靠** — 结构化 JSON 比 OCR 读取屏幕文本稳定一个数量级
4. **安全边界更清晰** — WS 通道绑定 `127.0.0.1`，不引入第三方面板或键盘模拟

---

## 四、风险分析

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| sticky port 文件路径未知 | 中 | 高 | 先探测常见路径，再回退扫描 |
| WebSocket 权限请求挂起 | 中 | 高 | 自动化需内置自动审批策略 |
| sidecar 二进制未编译 | 低 | 高 | 提示用户从桌面端启动 |
| cc-haha 版本更新 API/WS 变更 | 中 | 中 | 适配层隔离，锁版本号 |
| API 暴露到外部网络 | 低 | 高 | 强制绑定 127.0.0.1 |

---

## 五、已知局限

1. **WebSocket 协议无官方文档** — 需从源码反推消息格式，cc-haha 版本 `999.0.0-local` 可能变化
2. **权限交互不可跳过** — 首次 Claude 执行几乎必然触发 `permission_request`（如 MCP 工具访问）
3. **依赖桌面端运行** — sidecar 进程由 Electron 主进程启动，外部无法单独启动编译后的 sidecar
4. **sticky port 文件格式简单** — 仅为 `{"lastPort": port}`，但读取权限需与 cc-haha 用户一致
