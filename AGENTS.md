# AGENTS.md — AI 接入 PLC

首要指令文件是 **`OpenCode.md`**（项目根），包含完整的路径表、操作规则、模板库、安全红线。本文件仅补充 `OpenCode.md` 未覆盖的高频操作和架构细节。

## 快速命令

| 命令 | 操作 |
|------|------|
| `make test` | 运行 tests/ 下的 pytest |
| `make sim` | 启动 OpenPLC Docker 仿真 |
| `python start_all.py` | 一键启动 PLCSIM + Factory I/O + TIA MCP |
| `python start_all.py stop` | 停止所有 |
| `cd mcp-servers/tia-mcp && python server.py` | 启动 TIA MCP Server |
| `python run_gateway.py` | 启动边缘网关 (Modbus + InfluxDB + AI) |
| `python mcp-servers/tia-mcp/plcsim_api.py <cmd>` | PLCSIM 实例管理 CLI |
| `python mcp-servers/tia-mcp/plcsim_keeper.py` | 后台 PLCSIM 实例保活 |
| `python mcp-servers/tia-mcp/fix_tia_protection.py` | 修改 TIA Portal 项目保护设置 |

## 关键架构事实（代码库推断，OpenCode.md 未覆盖）

- **配置文件**：`mcp-servers/tia-mcp/config.yaml` 为主，支持 `${ENV_VAR}` 语法；项目根 `.env` 提供变量
- **项目根路径**：`config_loader.py:23` — `_PROJECT_ROOT = Path(__file__).parent.parent.parent`
- **TIA 通信链**：`server.py(FastMCP) → JSON 临时文件 → TiaWorker.exe(C# .NET Framework 4.8) → TIA Openness DLL`
- **LAD 生成链**：`自然语言 → DeepSeek → LadderSpec JSON → CartGen(.NET 8) → SimaticML XML → 导入 TIA`
- **TiaWorker.csproj** 目标 .NET Framework 4.8（编译到 `bin/`）；**CartGen.csproj** 目标 net8.0
- `start_all.py` 中 PLCSIM 内部实例名 `factory io1` 与 Factory IO 要求的 `factoryio` 不同

## 已知 Bug（OpenCode.md 未记录）

- **ConveyorControl FB501** 已在 TIA 项目中但**未在 OB1 中调用**，下载后传送带不会响应
- **TIA 每次下载需重新扫描设备**（西门子已知行为，非缺陷）
- `auto.cfg` 中 `auto_connect = True` 有时不生效，需在 Factory IO 控制台手动重设
- `AppData\Local\Temp` 常被 TIA/PLCSIM 缓存塞满，需定期清理（约 6.8GB）：`del %TEMP%\*.* /s /q`
- `mitsubishi-mcp/` 无硬件，`robot-mcp/` 未实现
- `start_all.py` 中 PLCSIM 内部实例名 `factory io1` 与 Factory IO 要求的 `factoryio` 不同（已在架构事实中注明，但与启动逻辑相关）

## PythonNET 注意事项

- **PythonNET 3.0+** 调用 PLCSIM API 时必须用枚举类型，不能用 int 隐式转换。正确写法：`instance.Interface = SimulationInterface.TCPIP` 而非 `instance.Interface = TCPIP`

## 已有指令文件（优先级从上到下）

- **`OpenCode.md`** — 完整项目规则（路径、操作指南、模板库、安全红线）
- **`claude.md`** — 项目总纲（五阶段计划、技术规范）
- **`AGENTS.md`** — 本文件，补充性快速参考
