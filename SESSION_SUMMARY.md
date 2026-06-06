# AI 接入 PLC — 项目总结

> 最后更新: 2026-06-06（第 2 次会话）

---

## 实施进度

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| **1** | OPC UA / Modbus 运行态 + 三菱 MC 协议 MCP | ✅ 完成 |
| **2** | AI 控制闭环 + 安全互锁 | ✅ 完成（Grafana/Ollama 跳过） |
| **3** | TIA Portal 工程态 + LAD/SCL 生成 | 🟡 **P3 闭环修复完成，待端到端下载验证** |
| **4** | 工业机器人 | ❌ 未开始 |
| **5** | 统一编排 | ❌ 未开始 |

---

## 测试覆盖

| 测试文件 | 数量 | 内容 |
|:---------|:----:|:-----|
| `tests/test_config_loader.py` | 22 | 环境变量、路径识别、Schema 校验 |
| `tests/test_edge_gateway.py` | 29 | 变化检测、阈值判定（**新增**） |
| `tests/test_safety_audit.py` | 7 | 链式哈希、防篡改 |
| `tests/test_safety_validator.py` | 14 | 急停禁用、熔断、值跳变 |
| `mcp-servers/mitsubishi-mcp/test_mc_protocol.py` | 54 | 帧结构、响应解析（**新增**） |
| `mcp-servers/tia-mcp/test_cartgen.py` | 5 | 21 模板 + CartGen 编译 |
| **总计** | **131** | |

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
| `mcp-servers/robot-mcp/` | 机器人（未开始） |
| `edge-gateway/` | AI 控制循环 + 数据采集 |
| `safety/` | 审计 + 写入校验 + 互锁规则 |
| `tests/` | 83 测试 + 根目录 48 测试 |
