# AI 接入 PLC — 项目总结

> 最后更新: 2026-06-11（P4 robot-mcp 就绪，SCL 外部源阻塞）

---

## 实施进度

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| **1** | OPC UA / Modbus 运行态 + 三菱 MC 协议 MCP | ✅ 完成 |
| **2** | AI 控制闭环 + 安全互锁 | ✅ 完成（Grafana/Ollama 跳过） |
| **3** | TIA Portal 工程态 + LAD/SCL 生成 | ✅ **完成（V21 全链路：编译→下载→仿真→FIO）** |
| **4** | 工业机器人 | 🟡 开发中（robot-mcp 已就绪，SCL 外部源阻塞） |
| **5** | 统一编排 | ❌ 未开始 |

---

## 已知阻塞（历史）

### ~~PLCSIM Advanced V8.0 许可证问题 (2026-06-06 已解决)~~ ✅

~~- **现象**: `PowerOn()` 报 `Error Code: -30, LicenseNotFound`~~
~~- **原因**: PLCSIM Advanced 试用期可能已过（14天），或从 V5.0 升级后许可证不兼容~~
~~- **影响**: 无法通过 API 恢复/创建 PLCSIM 实例，端到端流水线阻塞~~
- **解决**: 用户已确认许可证恢复正常，`PowerOn()` 不再报 -30，端到端流水线可正常运行（2026-06-07）

---

## 测试覆盖

| 测试文件 | 数量 | 内容 |
|:---------|:----:|:-----|
| `tests/test_config_loader.py` | 22 | 环境变量、路径识别、Schema 校验 |
| `tests/test_edge_gateway.py` | 29 | 变化检测、阈值判定 |
| `tests/test_safety_audit.py` | 7 | 链式哈希、防篡改 |
| `tests/test_safety_validator.py` | 14 | 急停禁用、熔断、值跳变 |
| `tests/test_download_flow.py` | 21 | 下载流程、管理员检测、PLCSIM API |
| `tests/test_robot_mcp.py` | 7 | OPC UA 连接、I/O 映射、安全互锁 |
| `mcp-servers/mitsubishi-mcp/test_mc_protocol.py` | 54 | 帧结构、响应解析 |
| `mcp-servers/tia-mcp/test_cartgen.py` | 5 | 21 模板 + CartGen 编译 |
| **总计** | **156** | |

---

## 本次会话修复

| Bug | 文件 | 影响 |
|:----|:-----|:-----|
| `_kill_tia_processes()` 杀全部 Siemens 进程 | `tia_session.py` | 误杀 GUI TIA Portal + PLCSIM |
| 项目已打开时 `Open()` 冲突 | `tia_session.py` | 连接 TIA Portal 卡死 |
| 编译 State=Warning 被拒绝 | `download_to_plcsim.py` | 0 错误编译被判断失败 |
| 自己 new TiaPortal 和已打开 GUI 冲突 | `download_to_plcsim.py` | 连接卡死 |
| 没有超时机制 | `download_to_plcsim.py` | 卡住无法中断 |
| `is_bit_device("TN0")` 误判 | `mc_protocol.py` | TN/CN 被当成位设备 |

### 本次会话（2026-06-06）修复

| Bug | 文件 | 影响 |
|:----|:-----|:-----|
| `ensure_service_initialized()` 启动 GUI 后立即 taskkill | `tia_session.py` | 杀死 IPC 通道，headless 永远连不上 |
| headless 模式需要管理员权限 | `download_to_plcsim.py` | `TiaPortal(WithoutUserInterface)` 报"需要提升" |
| 编译用 headless 模式，非 admin 时报错 | `download_to_plcsim.py` | 编译永远失败，无法完成下载 |
| run_end2end.py 编译仍用 headless | `run_end2end.py` | 端到端脚本编译失败 |
| tasklist 在 Git Bash 中参数被转发 | 全部 `tasklist` 调用 | `/fi` 被转为 `C:/Program Files/Git/fi` |
| 非 admin 进程无法启动 TIA Portal | `download_to_plcsim.py`, `tia_session.py` | `subprocess.Popen` 报 WinError 740 |

### 本次会话（2026-06-06 第2次）修复

| Bug | 文件 | 影响 |
|:----|:-----|:-----|
| `run_p3_complete.bat` 是 LF+UTF-8 编码 | `run_p3_complete.bat` | cmd.exe 无法解析，显示乱码和"不是内部或外部命令" |
| emoji 在 GBK 控制台报 UnicodeEncodeError | `download_to_plcsim.py` 等 5 个文件 | 43 处 emoji 在有中文 Windows 控制台崩溃 |
| 缺少独立的 golden backup 脚本 | — | 批处理中无法通过单行 Python 调用 archive |

---

## 快速命令

```bash
# 测试（全部）
python -m pytest tests/ mcp-servers/mitsubishi-mcp/test_mc_protocol.py -v

# 测试（P3 下载流程）
python -m pytest tests/test_download_flow.py -v

# P3 端到端流水线（管理员身份运行！）
run_p3_complete.bat                    # 完整流水线
run_p3_complete.bat --no-compile       # 跳过编译，仅下载

# 或手动步骤（从管理员终端）
python mcp-servers/tia-mcp/download_to_plcsim.py --compile-first

# 一键启动（PLCSIM + TIA + Factory IO）
python start_all.py

# 边缘网关（AI 控制循环）
python run_gateway.py

# TIA MCP Server（需管理员权限）
cd mcp-servers/tia-mcp && python server.py

# PLCSIM 管理
python mcp-servers/tia-mcp/plcsim_api.py list
python mcp-servers/tia-mcp/plcsim_api.py restore factoryio ^
  "D:/PLC cheng xu/TIA PLC CHENG XU/demo/factory_io1_golden.zip" ^
  "D:/PLC cheng xu/TIA PLC CHENG XU/demo/plcsim_storage" 10.0.0.1
```

> **⚠ 重要提示**: TIA Portal Openness API（无论 headless 还是 GUI 模式）需要管理员权限。
> 请从"以管理员身份运行"的命令提示符或 PowerShell 中执行上述命令。

---

## ⚡ 关键约束

### 管理员权限（新发现！）
TIA Portal Openness API 的所有模式（`WithoutUserInterface` 和 `WithUserInterface`）都需要**管理员权限**。非 admin 进程调用 `TiaPortal()` 会报 "请求的操作需要提升"。
- Python 脚本入口已添加自提权检测（`ShellExecuteW runas`）
- 启动 TIA Portal GUI 也从 `subprocess.Popen` 改为 `ShellExecuteW runas`
- 所有 `tasklist` 调用改用 `cmd.exe /c` 避免 Git Bash 参数转发问题

### PLCSIM PowerOff 铁律
任何方式的 PowerOff 后实例无法再次启动，**必须重启电脑**。
更新程序时：TIA Portal 切 STOP → 下载 → 切回 RUN。

### 首次下载限制
首次下载硬件配置必须在 **TIA Portal GUI 手动完成**。
首次后可用 golden backup + API 自动化（已验证）。

### 实例名
当前统一使用 `factoryio`（无空格）：config.yaml、golden backup、场景文件均已一致。
（之前不一致的 `factory io1` 已在之前会话中修复）

---

## 目录所有权

| 目录 | 说明 |
|:-----|:-----|
| `docs/` | Phase 1-3 文档齐全 |
| `mcp-servers/tia-mcp/` | TIA Portal + CartGen + PLCSIM API |
| `mcp-servers/opcua-mcp/` | OPC UA 读写服务 |
| `mcp-servers/mitsubishi-mcp/` | 三菱 MC 协议（**已完成**） |
| `mcp-servers/robot-mcp/` | 机器人 MCP 服务端（P4 基础完成） |
| `edge-gateway/` | AI 控制循环 + 数据采集 |
| `safety/` | 审计 + 写入校验 + 互锁规则 |
| `tests/` | 97 测试 + 根目录 59 测试 |

---

## P4 当前状态（2026-06-07 — SCL 外部源语法踩坑）

### SCL 外部源文件语法限制（关键发现）
TIA Portal V21 的外部源文件解析器有严格的语法限制，与块编辑器内部不同：
- `TITLE` 值不加引号：`TITLE = Pick & Place Control`
- `{ S7_Optimized_Access := 'TRUE' }` 必须紧接 `TITLE` 后、`VERSION` 前
- **不支持 `AT %I` / `AT %Q`** — 引用 I/O 须用标签名 `"I0.8"`
- 单个 SCL 文件可包含 `FUNCTION_BLOCK` + `DATA_BLOCK` + `ORGANIZATION_BLOCK`

已验证可导入模板：
- `mcp-servers/tia-mcp/ConveyorControl_OB1.scl` — 不使用 AT，纯引用标签名称

### P4 资产就绪
- **robot-mcp 服务端**（7 MCP 工具 + 双协议后端）— 就绪
- **PLCSIM 部署** — 阻塞（需 TIA GUI 手动创建 I/O 标签表，然后在块编辑器粘贴 SCL，编译下载）
