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

## 🚧 待解决

### TCP/IP 虚拟网卡配置
- **问题**: `VirtualSwitchMisconfigured` (-50) 错误
- **原因**: PLCSIM Advanced TCP/IP 模式需要 "Siemens PLCSIM Virtual Ethernet Adapter"
- **解决**: 在 PLCSIM Advanced GUI → Settings → 创建虚拟网卡
- **替代**: 当前在 Softbus 模式下运行，不影响 LAD 生成和导入

### Factory I/O 自动连接
- 需要 TCP/IP 模式 + `auto.cfg` 配置文件
- 文件位置: `Documents\Factory IO\auto.cfg`
- 格式: 指定场景 + PLC 类型 + IP 地址

### 三端一键启动脚本
- 目标: `python start_all.py` 启动 PLCSIM + TIA + Factory I/O
- 流程: restore_instance → start Factory I/O → start TIA Openness

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
# 查看 PLCSIM 实例
python plcsim_api.py list

# 从黄金备份恢复
python -c "from plcsim_api import restore_instance; restore_instance('plc1', 'golden.zip', './persist')"

# CartGen 测试
dotnet run --project CartGen/CartGen.csproj -- templates/电机正反转.json

# AI 生成自定义块
python generate_custom.py  # 改 DESCRIPTION 变量

# 启动 TIA MCP Server
python server.py
```

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
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
