# 阶段 3：西门子工程态 — TIA Portal + LAD 生成

> 目标：AI 通过自然语言生成 PLC 梯形图 (LAD) 代码，自动导入 TIA Portal，
> 编译后下载到 PLCSIM Advanced 仿真，并连接 Factory I/O 可视化验证。

---

## ✅ 已完成

### PLCSIM Advanced API 封装
| 功能 | 方法 | 状态 |
|------|------|:----:|
| 创建空壳实例 | `create_instance()` | ✅ |
| 黄金备份 | `archive_instance()` | ✅ |
| 从备份恢复 | `restore_instance()` | ✅ 已验证 |
| 切换 TCP/IP | `switch_to_tcpip()` | ✅ 需虚拟网卡 |
| 实例管理 CLI | `python plcsim_api.py <cmd>` | ✅ |

### CartGen LAD 生成器
- **语言**: C# .NET 8.0
- **输入**: LadderSpec JSON
- **输出**: SimaticML XML（TIA Portal 原生格式）
- **支持元素**: normally_open, normally_closed, coil, coil_set, coil_reset
- **限制**: 不支持 parallelElements（并联分支），自保持用 Set/Reset 模式
- **模板库**: 18 个中文名 LAD 模板，全部通过验证

### 首次下载限制突破
```
之前: 必须 TIA Portal GUI 手动下载（不可绕过）
之后: ArchiveStorage → golden.zip → RetrieveStorage → 全自动化
```
- 黄金备份: `factory_io1_golden.zip`（146 KB）
- 流程: `RegisterInstance → StoragePath → RetrieveStorage → PowerOn → Run`

### TIA MCP Server
- **框架**: FastMCP 3.3.1
- **工具**: 8 个（list_devices / import_scl / compile / download / 
  generate_scl / generate_and_import / create_ladder_block / full_pipeline）
- **AI**: DeepSeek-chat API 连通
- **配置**: YAML + 环境变量 + .env 三层配置

---

## ✅ 已解决

### TCP/IP 虚拟网卡配置
- **状态**: ✅ 已解决 — `start_all.py` 和 `p3_flow.py` 自动检测并切换 TCP/IP 模式
- PLCSIM Advanced GUI → Settings 虚拟网卡创建后，API 自动选择 TCP/IP 模式
- `plcsim_api.py` 通过 `switch_to_tcpip()` 和 `ip` 参数实现
- 启动命令: `python start_all.py` 自动配置

### Factory I/O 自动连接
- **状态**: ✅ 已解决 — 通过 `auto.cfg` 自动配置
- 文件位置: `Documents\Factory IO\auto.cfg`
- 启动脚本: `python scripts/launch_factory_io.py` 自动生成 `auto.cfg`
- `start_all.py` 中内置 Factory I/O 自动启动流程

### 三端一键启动脚本
- **状态**: ✅ 已实现 — `python start_all.py`
- 流程: restore_instance → start Factory I/O → start TIA MCP Server
- 支持子命令: `--plcsim-only`, `--factory-only`, `--tia-only`, `--with-robot`

### P3 端到端编排器（纯子进程架构）
- **状态**: ✅ 已重构 — `python p3_flow.py`
- 纯编排器模式：不直接导入 clr/uiautomation，所有操作通过子进程调用
- 彻底解决 COM STA/MTA 线程模型冲突
- 支持:
  ```bash
  python p3_flow.py                       # 完整流程
  python p3_flow.py --download-only       # 仅编译+下载
  python p3_flow.py --skip-compile        # 不编译直接下载
  python p3_flow.py --golden-restore      # 快速恢复（跳过所有）
  ```

### 下载策略（5 级降级）
- **状态**: ✅ 已增强
- 降级链: TiaWorker(headless) → TiaWorker(GUI) → Python API(GUI) → UI Automation → 手动
- TiaWorker GUI 模式: `TiaWorker.exe download-gui`（WithUserInterface 附加到运行中 TIA Portal）
- 所有路径成功时自动更新 golden backup
- 快速恢复: `python download_to_plcsim.py --golden-restore`

---

## 📊 TIA MCP 工具链

```
自然语言描述
  ↓ DeepSeek API（temperature=0.3, max_tokens=4000）
LadderSpec JSON
  ↓ CartGen (.NET 8.0)
SimaticML XML
  ↓ _import_xml_into_tia() → tia_session()
TIA Portal 项目
  ↓ Compile (ICompilable)
  ↓ Download (DownloadProvider) → 后续下载
PLCSIM Advanced 仿真
  ↓ S7 协议 (TCP/IP)
Factory I/O 3D 可视化
```

### JSON → XML 转换示列

```json
{
  "blockName": "MotorControl",
  "blockNumber": 500,
  "interface": {
    "inputs": [
      {"name": "iStart", "type": "Bool", "comment": "启动按钮", "address": "%I0.0"},
      {"name": "iStop", "type": "Bool", "comment": "停止按钮", "address": "%I0.1"}
    ],
    "outputs": [
      {"name": "oRun", "type": "Bool", "comment": "电机运行", "address": "%Q0.0"}
    ]
  },
  "networks": [
    {
      "title": "电机控制",
      "elements": [
        {"type": "normally_open", "operand": "iStart"},
        {"type": "normally_closed", "operand": "iStop"},
        {"type": "coil_set", "operand": "oRun"}
      ]
    },
    {
      "elements": [
        {"type": "normally_closed", "operand": "iStop"},
        {"type": "coil_reset", "operand": "oRun"}
      ]
    }
  ]
}
```

---

## 🔧 快速命令

```bash
# PLCSIM 管理
python plcsim_api.py list                    # 查看实例
python plcsim_api.py restore factoryio golden.zip ./persist 192.168.0.1  # 从备份恢复
python plcsim_api.py archive factoryio golden.zip  # 创建黄金备份
python plcsim_api.py purge factoryio         # 强制清理残留

# P3 端到端
python p3_flow.py                            # 完整流程（PLCSIM→编译→下载→FIO）
python p3_flow.py --download-only            # 仅编译+下载
python p3_flow.py --skip-compile             # 不编译直接下载
python p3_flow.py --golden-restore           # 从 golden 快速恢复（跳过所有）

# 下载（含 5 级降级）
python download_to_plcsim.py                 # 自动选择最优方式
python download_to_plcsim.py --tiaworker-gui # 强制 TiaWorker GUI 模式
python download_to_plcsim.py --golden-restore # 从 golden 快速恢复
python download_to_plcsim.py --ui            # 强制 UI Automation

# CartGen 测试
dotnet run --project CartGen/CartGen.csproj -- templates/电机正反转.json

# AI 生成自定义块
python generate_custom.py  # 改 DESCRIPTION 变量

# 启动 TIA MCP Server
cd mcp-servers/tia-mcp && python server.py
```

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `p3_flow.py` | P3 端到端编排器（纯子进程，无 clr/uiautomation） |
| `mcp-servers/tia-mcp/download_to_plcsim.py` | 下载策略（5 级降级 + golden 自动更新） |
| `mcp-servers/tia-mcp/plcsim_api.py` | PLCSIM .NET API 封装（~550行） |
| `mcp-servers/tia-mcp/server.py` | FastMCP 服务（~565行） |
| `mcp-servers/tia-mcp/CartGen/Program.cs` | LAD 生成器（~120行） |
| `mcp-servers/tia-mcp/config_loader.py` | 统一配置加载 |
| `mcp-servers/tia-mcp/tia_session.py` | TIA Portal 会话管理 |
| `mcp-servers/tia-mcp/templates/` | 18 个 LAD 模板 |
| `mcp-servers/tia-mcp/lad_creator.py` | LAD 创建器 |
| `mcp-servers/tia-mcp/ladder_renderer.py` | SVG 渲染（可选） |
| `mcp-servers/tia-mcp/gen_io_map.py` | IO 映射生成 |
| `mcp-servers/tia-mcp/call_fb_in_ob1.py` | OB1 调用链生成 |

---

## 🧪 测试覆盖（2026-06-22 更新）

### 新增测试文件

| 测试文件 | 测试数 | 覆盖目标 | 引入时间 |
|---------|--------|---------|---------|
| `tests/test_server_tools.py` | 40 | server.py 9 个 MCP 工具 + 内部函数（_run_worker / _resolve_path / _check_auth / _safety_gate） | TS002 |
| `tests/test_p3_flow_parsing.py` | 12 | p3_flow.py 编译输出 JSON 解析（成功/失败/空/非法格式） | TS002 |
| `tests/test_gen_io_map.py` | 15 | gen_io_map.py（generate_io_map / CLI 入口） | TS002 |
| `tests/test_create_plc_tags.py` | 17 | create_plc_tags.py（_generate_tag_xml / create_tags / create_tags_from_json） | TS002 |

### 测试运行结果

```bash
# 新增测试：83 passed, 0 failed, 0 skipped
# 与预存测试共存：212 passed, 6 skipped, 0 failed
```

### 已知缺口

| 模块 | 测试状态 | 计划 |
|------|---------|------|
| `lad_ast.py` | 零测试 | TS004 |
| `ladder_renderer.py` | 零测试 | TS004 |
| `layout_engine.py` | 零测试 | TS004 |
| `call_fb_in_ob1.py` | 零测试 | TS004 |
| TiaWorker C# 核心命令 | 空壳测试 (`UnitTest1.cs`) | TS003 |

### 注意事项

1. **sys.modules 污染**：多个预存测试文件在模块级别修改 `sys.modules`，导致跨文件测试顺序依赖。运行全部测试时需要注意测试顺序。
2. **GBK 编码**：`test_gen_io_map.py` 的 CLI 测试在 Windows 控制台下产生 GBK 解码警告，可通过设置 `PYTHONIOENCODING=utf-8` 缓解。
