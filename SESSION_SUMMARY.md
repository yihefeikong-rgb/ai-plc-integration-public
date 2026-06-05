# AI 接入 PLC — 项目总结

> 最后更新: 2026-06-04

---

## 实施进度

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| **1** | OPC UA / Modbus 运行态 + 三菱 MC 协议 MCP | ✅ 完成 |
| **2** | AI 控制闭环 + 安全互锁 | ✅ 完成（Grafana/Ollama 跳过） |
| **3** | TIA Portal 工程态 + LAD 生成 | 🟡 代码链完成，端到端验证差下载一步 |
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

---

## 快速命令

```bash
# 测试
python -m pytest tests/ mcp-servers/mitsubishi-mcp/test_mc_protocol.py -v

# 一键启动
python start_all.py

# 边缘网关（AI 控制循环）
python run_gateway.py

# 三菱 MCP Server
cd mcp-servers/mitsubishi-mcp && python server.py

# TIA MCP Server
cd mcp-servers/tia-mcp && python server.py

# OB1 调用链 + 编译
python mcp-servers/tia-mcp/call_fb_in_ob1.py --all

# 下载到 PLCSIM（120s 超时）
python mcp-servers/tia-mcp/download_to_plcsim.py --compile-first --timeout 120
```

---

## ⚡ 关键约束

### PLCSIM PowerOff 铁律
任何方式的 PowerOff 后实例无法再次启动，**必须重启电脑**。
更新程序时：TIA Portal 切 STOP → 下载 → 切回 RUN。

### 首次下载限制
首次下载硬件配置必须在 **TIA Portal GUI 手动完成**。
首次后可用 golden backup + API 自动化（已验证）。

### 实例名不匹配
PLCSIM 实例名：`factory io1`（有空格）
Factory IO auto.cfg：`instance_name = 'factory io1'`（已修正）
两场景文件（`传送带测试.factoryio`、`测试.factoryio`）均已更新

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
