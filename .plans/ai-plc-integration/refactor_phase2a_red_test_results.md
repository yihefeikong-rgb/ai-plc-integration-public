# Phase 2A / 2B Pipeline 与 MCP 凭据结果

- 日期：2026-07-15
- 基线提交：`4db8f25f98090838e8020bdf4c2f724228358efa`
- 工作分支：`codex/phase2a-pipeline-auth`
- Git 状态：未暂存、未提交、未推送
- 真实硬件或桌面动作：无

## RED 证据

- Pipeline 元数据：新增契约测试在旧实现上 `1 failed`，错误包含 `不支持的工作流参数: authenticated_operator`，MCP 调用数为 0。
- MCP 凭据基础契约：旧实现 `9 failed`，覆盖元数据、参数复制、内部注入、覆盖拒绝和缺失失败关闭。
- Robot 认证默认值：旧实现 `2 failed`，确认服务端未从 `MCP_AUTH_TOKEN` 取得 CLI 默认令牌。
- stdio 子进程环境：旧实现 `4 failed, 1 passed`，确认认证环境变量未进入 SDK 子进程环境且无连接快照。
- 取消与异常边界：旧实现分别暴露快照残留、异常文本泄密和 disconnect/reconnect 资源交叉污染；每个问题均先由纯离线失败测试复现。
- 连接池跨实例生命周期：首次集成审查复现旧 adapter 尚未退出时同名新 adapter 已启动；池级 `disconnect_server` / `disconnect_all` 两条回归契约在旧实现上均失败（`2 failed`）。

## GREEN 实现

- `WorkflowExecutionMetadata` 将 `authenticated_operator` 从工作流业务输入分离；调用方输入被复制，非字符串 actor 归一为空，旧位置参数构造保持兼容。
- `ServerInfo` 只保存凭据环境变量名和参数名，不保存秘密值。
- `McpClientAdapter` 使用连接时凭据快照，在调用边界复制参数并注入；调用方覆盖和快照缺失均失败关闭。
- 认证 MCP 子进程环境以 SDK `get_default_environment()` 为基底，仅增加声明的认证变量；令牌不进入命令行。
- 认证服务器的外部异常只暴露组件与异常类型，不记录令牌；连接、断开、取消和并发重连由单适配器生命周期锁串行化。
- `McpConnectionPool` 使用池级生命周期锁串行化连接、单个断开和全部断开，旧实例完成清理前不会启动同名新实例。
- Robot MCP 的 `--auth-token` 默认值与 adapter 统一读取 `MCP_AUTH_TOKEN`。

## 主代理新鲜验证

- 根默认纯离线：`338 passed, 41 deselected, 13 warnings`
- 后端：`286 passed`
- 前端：`2 passed`
- Robot 模拟后端：`23 passed`
- `git diff --check`：通过

13 条 warning 均为既有 ChromaDB deprecation warning。首次并行运行根测试和后端测试时触发了预期的单一 MCP owner 锁冲突；锁文件由测试进程正常释放，随后串行复跑全部通过。

## 审查结论

- Task 1 规格审查：APPROVED
- Task 1 代码质量审查：APPROVED
- Task 2 规格审查：APPROVED
- Task 2 代码质量审查：APPROVED
- 首次最终集成审查：CHANGES_REQUIRED（发现连接池跨实例断开/重连竞态）
- 池级修复后最终集成复审：APPROVED（Critical / Important / Minor 均无）

## 证据边界

本轮只证明离线契约和模拟后端通过。未启动真实 MCP 子进程，未加载 TIA 项目，未下载到 PLCSIM，未证明 CPU RUN 或 PLC 可读，也未执行 Factory I/O/机器人真实动作。
