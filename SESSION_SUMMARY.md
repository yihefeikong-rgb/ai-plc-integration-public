# AI 接入 PLC — 项目总结

> 最后更新: 2026-06-11（知识库搭建完成，13条知识入库）

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

## 2026-06-11 全量审查修复

### 审查范围
6 大领域 17 项检查（安全/代码质量/测试/架构/文档/P4）

### 修复统计

| 类别 | 项数 | 关键操作 |
|:-----|:----:|:---------|
| 安全修复 | 3 | 删除重复 `.env`；更换泄漏 API Key；`start_all.py` 加管理员检测+PID锁 |
| 审计日志统一 | 1 | 3 份 audit.py → `mcp_common/audit.py`；6 个调用文件改 import |
| 测试加固 | 3 | 重命名伪测试；conftest.py 5 标记体系；硬件依赖自动跳过 |
| 死代码清理 | 2 | 删除 11 文件（5 diag_tag_api + 4 废弃脚本 + 2 杂物） |
| 大文件拆分 | 1 | `plcsim_api.py` 902→5 文件（入口+instance/backup/network/common） |
| 路径配置迁移 | 1 | 硬编码路径移入 config.yaml；start_all/auto_full_pipeline 改用 cfg |
| robot 工具重命名 | 1 | 7 工具 纯动词→动词_名词；同步 deploy_pnp/测试/文档 |
| 文档同步 | 4 | SESSION/AGENTS/phase-3.md/README |

### 文件变更
- **49 files changed, 3345 insertions(+), 2251 deletions(-)**
- 新增: robot-mcp (7文件), plcsim 子模块 (4文件), P4 文档, 测试
- 删除: 5 diag_tag_api + 4 废弃脚本 + tia-mcp 残留

---

## 2026-06-11 知识库搭建（第二轮）

### personal-knowledge-db 集成
- 发现并连接 `personal-knowledge-db` MCP 服务器（SQLite + FTS5 + Embedding + RRF 混合搜索）
- 项目审查：遍历全部源码、文档、配置文件，识别 10 大知识领域
- 外部搜索：使用 Exa + Context7 搜索 TIA Openness、PLCSIM API、IEC 61131-3、MC 协议、OPC UA、FastMCP、PyModbus、安全标准等官方文档
- 批量入库：共 **13 条结构化工控知识** 写入 knowledge-db

### 入库内容（13条）
| 分类 | 内容 | 来源 |
|:-----|:-----|:-----|
| TIA Portal Openness | API 概述、对象模型、编译接口 | Siemens 官方文档 |
| PLCSIM Advanced V8.0 | API 工作流、IInstance 接口 | Siemens 手册 + 教程 |
| IEC 61131-3 SCL | 语法、适用场景、最佳实践 | IEC 标准 + 技术博客 |
| 三菱 MC 协议 | 3E 帧格式、软元件地址 | Mitsubishi 官方手册 |
| OPC UA + asyncua | 协议概述、Python 库用法 | asyncua 文档 |
| Factory I/O 集成 | 标准版 + Advanced 版设置 | Factory I/O 官方文档 |
| FastMCP 框架 | 三种原语、传输模式、模板 | FastMCP 官方教程 |
| Modbus TCP + PyModbus | 数据模型、功能码、帧格式 | PyModbus 官方文档 |
| 工业安全标准 | 急停电路、互锁规则、SIL/PL | IEC/ISO 标准文档 |
| PyRI 机器人 | 架构、I/O 映射、已知阻塞 | 开源项目参考 |
| 项目进度状态 | Phase 状态、阻塞、测试统计 | 本仓库 |
| MCP 服务器架构 | 6 个服务器详情 | 本仓库 |

### 敏感信息检查
- `.env` 中的 DEEPSEEK_API_KEY — ✅ 已被 `.gitignore` 忽略，未跟踪
- 硬编码 IP — 均为默认占位值（192.168.0.1/10.0.0.1），无真实设备 IP
- 无私钥、无 GitHub Token、无数据库连接串 — ✅ 安全

---

## 已知阻塞

### PLCSIM 相关
- ~~PLCSIM Advanced V8.0 许可证问题~~ ✅ 已解决
- PowerOff 后实例无法再次启动，必须重启电脑

### TIA Portal 相关
- 首次下载硬件配置必须在 TIA Portal GUI 手动完成
- 所有 Openness API 调用需要管理员权限
- 每次下载需重新扫描设备（西门子已知行为）

### P4 阻塞
- SCL 外部源文件不支持 `AT %I`/`AT %Q` 语法
- 需要在 TIA Portal GUI 中手工创建标签表 + 块编辑器粘贴 SCL
- robot-mcp 代码已就绪但未在真实环境运行验证

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
| **总计** | **156** | **151 passed, 5 skipped, 0 failed** |

---

## 快速命令

```bash
# 测试（全部离线）
"d:/python3/python.exe" -m pytest tests/ mcp-servers/mitsubishi-mcp/test_mc_protocol.py -v

# 一键启动（PLCSIM + Factory IO + TIA MCP）
python start_all.py
python start_all.py stop

# 完整自动化流水线（管理员身份运行）
python auto_full_pipeline.py

# TIA MCP Server（需管理员权限）
cd mcp-servers/tia-mcp && python server.py

# PLCSIM 管理
python mcp-servers/tia-mcp/plcsim_api.py list
python mcp-servers/tia-mcp/plcsim_api.py restore factoryio <zip> <storage_path> <ip>

# Robot MCP
python mcp-servers/robot-mcp/server.py
python mcp-servers/robot-mcp/verify_pick_and_place.py

# 边缘网关
python run_gateway.py
```

---

## 目录所有权

| 目录 | 说明 |
|:-----|:-----|
| `docs/` | Phase 1-4 文档齐全 |
| `mcp-servers/tia-mcp/` | TIA Portal + CartGen + PLCSIM API（已拆分5模块） |
| `mcp-servers/robot-mcp/` | 机器人 MCP 服务端（7 工具，P4 开发中） |
| `mcp-servers/opcua-mcp/` | OPC UA 读写服务 |
| `mcp-servers/modbus-mcp/` | Modbus 读写服务 |
| `mcp-servers/mitsubishi-mcp/` | 三菱 MC 协议（已完成） |
| `edge-gateway/` | AI 控制循环 + 数据采集 |
| `safety/` | 审计 + 写入校验 + 互锁规则 |
| `tests/` | 97 测试 + 根目录 59 测试 |
