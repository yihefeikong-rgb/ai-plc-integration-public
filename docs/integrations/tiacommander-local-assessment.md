# TiaCommander 本地接入评估报告

> 日期：2026-07-22
> 状态：评估完成（已授权）
> 更新：2026-07-22 — 修正授权状态

## 基本信息

| 项目 | 值 |
|------|-----|
| 版本 | 2.30.3 |
| 许可证状态 | **已授权（有效期至 2099-12-31）** |
| 运行时 | .NET Framework 4.8 |
| 协议 | MCP 2024-11-05 (stdio) |
| 可执行文件路径 | `D:\claude code xiangmu\AI 接入PLC\mcp-servers\tiacommander-mcp\TiaCommander.exe` |
| 安装方式 | 便携版（portable），解压到项目仓库内 |

## TIA Portal 连接

| 项目 | 值 |
|------|-----|
| 自动检测到的 Siemens API | `D:\TIA BEN TI\Portal V18\PublicAPI\V18`（注册表） |
| 项目配置的 TIA 安装目录 | `D:\TIA BEN TI\Portal V21` |
| 项目目标版本 | V21 |
| 版本匹配 | **不匹配** — TiaCommander使用V18 API，项目目标为V21 |

> **注意**：TiaCommander 文档声明支持 V15.1–V21，但仅 V19 完整测试。
> V21 使用模块化 DLL（Base + Step7），V18 使用单一 DLL，两者结构不同。

## 许可证状态

- **状态：已授权**
- 授权缓存有效期至 2099-12-31
- 所有工具可用（16 工具 / 166 动作）
- 遥测上报了 license_key 和 machine_id 校验错误（不影响功能）

## MCP 配置状态

- `.mcp.json` 内容：`{"mcpServers": {}}` — **TiaCommander 未配置为项目 MCP 服务器**
- 通过 Claude Code 直接 stdio 启动并连接
- 已通过 Claude Code 初始化和工具列表交换

## 可用工具（完整授权，共 16 个）

根据日志记录的 tools/list 响应，可用工具包括：

| 工具 | 说明 |
|------|------|
| `session` | 会话管理：连接TIA、打开/保存/关闭项目、设备枚举 |
| `blocks_read` | 块读取：列表、详情、接口、XML、导出、一致性检查 |
| `blocks_write` | 块写入：创建、删除、导入、导出、网络操作 |
| `tags` | 标签管理 |
| `types` | UDT 管理 |
| `watch_tables` | Watch 表管理 |
| `libraries` | 项目库操作 |
| `hardware` | 硬件配置读取 |
| `cross_reference` | 交叉引用 |
| `project` | 项目归档、保存、导出 |
| `download_upload` | 下载、上传、扫描 |
| `diagnostics` | 连接配置、在线、状态 |
| `alarms` | 报警文本管理 |
| `text_lists` | 文本列表管理 |

## 关键发现

### 1. V18 vs V21 版本不匹配
TiaCommander 自动从注册表检测到 V18，但项目配置的目标是 V21。
- V21 使用模块化 DLL 结构（`Base.dll` + `Step7.dll`）
- V18 使用单一 DLL（`Siemens.Engineering.dll`）
- 如果 V21 的 Openness API 与 V18 不兼容，某些操作可能失败

### 2. 二进制文件在仓库中
TiaCommander 的完整二进制文件位于仓库目录 `tiacommander-mcp/` 下。
根据许可证条款，这可能需要确认是否允许。

### 3. 遥测上报
日志显示遥测会尝试上报 machine_id 和 license_key（虽然校验失败）。
需注意测试数据不含客户信息。

## 风险分析

| 风险 | 等级 | 说明 |
|------|------|------|
| V18/V21 版本不匹配 | 中 | 需验证 V21 Openness API 兼容性 |
| 二进制文件在仓库 | 中 | 需确认许可证允许重新分发 |
| 遥测数据上报 | 低 | 测试数据不含客户信息 |
| 许可证可撤销 | 中 | 专有软件，续期由厂商决定 |

## 建议

1. **验证 V21 兼容性**：由于 TiaCommander 使用 V18 API，先使用 V18 项目测试，再验证 V21 兼容性
2. **不要将二进制文件提交到仓库**：考虑将 TiaCommander 移至 `C:\TiaCommander\` 等仓库外位置
3. **继续使用 TiaWorker 作为主要后端**：TiaCommander 作为补充 Provider
4. **向作者确认许可证条款**：确保项目集成符合许可要求