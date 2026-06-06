# AI 接入 PLC — 项目交接文档

> 生成: 2026-06-06（第 2 次更新）
> 当前分支: master
> 最后提交: `4b3716c` docs: P3 权限修复文档 + 下载流程测试

---

## 一、项目上下文

构建 AI Agent 系统，让 AI 通过自然语言监控/控制西门子 PLC、三菱 PLC，并自动生成西门子 PLC 代码。

**技术栈**: MCP + Python + C#/.NET + OPC UA / Modbus / MC协议 + TIA Portal Openness + PLCSIM Advanced V8.0

---

## 二、五阶段进度

| Phase | 内容 | 状态 |
|:------|:-----|:----:|
| **1** | OPC UA / Modbus 运行态 + 三菱 MC 协议 MCP | ✅ **完成** |
| **2** | AI 控制闭环 + 安全互锁 | ✅ **完成**（跳过 Grafana/Ollama）|
| **3** | TIA Portal 工程态 + LAD/SCL 代码生成 | 🟡 **进行中（95% — 权限问题已修复，待端到端验证）** |
| **4** | 工业机器人 | ❌ 未开始 |
| **5** | 统一编排 | ❌ 未开始 |

### Phase 3 详细状态

**已完成**:
- SCL 代码生成（18+ 模板，CartGen 编译通过）✅
- LAD 梯形图生成（LadderBuilder.cs）✅
- OB1 调用链生成 ✅
- config_loader Schema 校验 ✅
- **下载策略重构**（Python API → UI Automation → 手动，三级降级）✅
- **TiaWorker DownloadProvider 重写** ✅
- **plcsim_api.py V8.0 迁移** + Runtime Manager 自动启动 ✅
- **Golden restore 验证通过** ✅

**本次会话（2026-06-06 第2次）修复**:
- ✅ **batch 文件 CRLF 编码修复**: `run_p3_complete.bat` 从 LF+UTF-8 重写为 CRLF+纯英文，cmd.exe 正常解析
- ✅ **emoji GBK 崩溃修复**: `config_loader.py` 顶部添加 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`，所有脚本无需逐一修改
- ✅ 新增 `scripts/archive_golden.py` — 独立的 golden backup 更新脚本，供 .bat 调用
- ✅ `start_all.py` 统一实例名: `factory io1` → `factoryio`

**本次会话（第3次）修复**:
- ✅ **Factory I/O 启动**: `run_p3_complete.bat` 新增 Step [2/5] 启动 Factory I/O
- ✅ **新增 `scripts/launch_factory_io.py`**: 生成正确 auto.cfg（instance_name=factoryio），写入用户 Documents 和 ProgramData 两个位置
- ✅ **实例名统一**: `start_all.py` 中所有 `factory io1`（带空格）改为 `factoryio`（无空格）
- ✅ **auto.cfg 一致**: 之前 ProgramData 的 auto.cfg 用 `'factory io1'`，PLCSIM 实例名是 `factoryio`，Factory I/O 连不上仿真

**待解决**:
- 端到端下载验证 — 需以管理员身份运行 `run_p3_complete.bat` 或从管理员终端执行
- ConveyorControl 的 IO 偏移量（当前使用 %I0.0，config 配置 io_offset=10）
- V21 Openness 迁移（搁置，DLL 拆分问题太大）

---

## 三、关键文件与架构

### MCP Servers（5个）
```
mcp-servers/
├── opcua-mcp/          # OPC UA 读取 S7-1200/1500
├── modbus-mcp/         # Modbus 设备
├── mitsubishi-mcp/     # 三菱 MC 协议（mc_protocol.py）
├── tia-mcp/            # TIA Portal 工程态（核心）
└── desktop-mcp/        # 桌面自动化
```

### TIA MCP Server 核心文件
```
mcp-servers/tia-mcp/
├── server.py                 # FastMCP 服务（8个工具）
├── config.yaml               # 主配置（当前: V18 + advanced）
├── config_loader.py          # 配置加载器（YAML+环境变量）
├── tia_session.py            # TIA Portal 会话管理（headless/gui）
├── download_to_plcsim.py     # 下载策略（三级降级）
├── dl_plcsim_gui.py          # UI Automation 下载（uiautomation）
├── plcsim_api.py             # PLCSIM Advanced V8.0 API 封装
├── call_fb_in_ob1.py         # OB1 调用链生成
├── run_end2end.py            # 端到端5步自动化脚本
├── diagnose_download.py      # 下载能力诊断
├── TiaWorker/
│   ├── Program.cs            # C# TIA Worker（DownloadProvider 实现）
│   ├── LadderBuilder.cs      # LAD 梯形图生成
│   └── CartGen/              # LAD → SimaticML XML
└── plcsim_storage/           # PLCSIM 持久化存储
```

### 测试与安全
```
tests/                            # pytest 测试套件
├── test_config_loader.py (22)    # 配置加载
├── test_edge_gateway.py (29)     # 边缘网关
├── test_safety_audit.py (7)      # 安全审计
└── test_safety_validator.py (14) # 安全验证
mcp-servers/tia-mcp/
├── test_cartgen.py (5)           # LAD 模板
├── test_dl_plcsim_gui.py (20)   # UI Automation
├── test_restore.py               # Golden restore
├── test_tcpip_fix.py             # TCP/IP 修复
└── test_tcpip_restore.py         # TCP/IP + restore
mcp-servers/mitsubishi-mcp/
└── test_mc_protocol.py (54)      # 三菱协议
总计: ~151 测试用例

safety/
├── audit.py              # 链式哈希审计日志
└── interlock-rules.yml   # 写入互锁规则
```

---

## 四、当前环境配置

| 组件 | 路径 | 版本 |
|:-----|:-----|:-----|
| Python | `D:\Python3\python.exe` | 3.13.2 |
| TIA Portal | `D:\TIA BEN TI\Portal V18` | V18 |
| PLCSIM Advanced API | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\` | V8.0 |
| TIA 项目 | `D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18` | .ap18 |
| Golden 备份 | `D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip` | 149KB |
| Factory I/O | `D:\Factory IO` | 已装 |

**config.yaml 关键配置**:
```yaml
tia.version: "V18"
tia.install_dir: "D:\\TIA BEN TI\\Portal V18"
simulation.backend: "advanced"  # 已从 v18 改为 advanced
simulation.advanced.plc_ip: "10.0.0.1"
factory_io.driver_mode: "plcsim"  # Softbus 模式
```

---

## 五、快速命令

```bash
# 测试套件
"D:/Python3/python.exe" -m pytest tests/ mcp-servers/tia-mcp/test_cartgen.py tests/test_download_flow.py -v

# 下载流程测试
"D:/Python3/python.exe" -m pytest tests/test_download_flow.py -v

# P3 端到端流水线（一键批处理，自动提权）
#   注意：.bat 文件是纯英文 + CRLF 编码，cmd.exe 正常解析
run_p3_complete.bat

# 或手动步骤（从管理员终端）:
"D:/Python3/python.exe" mcp-servers/tia-mcp/download_to_plcsim.py --compile-first

# 查看 PLCSIM 实例
"D:/Python3/python.exe" mcp-servers/tia-mcp/plcsim_api.py list

# 从黄金备份恢复
"D:/Python3/python.exe" mcp-servers/tia-mcp/plcsim_api.py restore factoryio \
  "D:/PLC cheng xu/TIA PLC CHENG XU/demo/factory_io1_golden.zip" \
  "D:/PLC cheng xu/TIA PLC CHENG XU/demo/plcsim_storage" 10.0.0.1

# 下载到 PLCSIM（编译+下载）
"D:/Python3/python.exe" mcp-servers/tia-mcp/download_to_plcsim.py --compile-first

# UI Automation 下载
"D:/Python3/python.exe" mcp-servers/tia-mcp/dl_plcsim_gui.py "demo" --timeout 120

# 端到端流水线
"D:/Python3/python.exe" mcp-servers/tia-mcp/run_end2end.py

# 启动 TIA MCP Server
cd mcp-servers/tia-mcp && "D:/Python3/python.exe" server.py

# CartGen 测试
cd mcp-servers/tia-mcp/CartGen && dotnet run --project CartGen.csproj -- templates/电机正反转.json
```

---

## 六、关键发现与经验

### TIA Portal Openness — 管理员权限（新发现）
- `TiaPortal(WithoutUserInterface)` 和 `TiaPortal(WithUserInterface)` **都需要管理员权限**
- `ensure_service_initialized()` 启动 GUI 后**不能杀死** — headless 模式依赖同一 IPC 通道
- 启动 TIA Portal 也必须提权：`ShellExecuteW(None, "runas", ...)` 而非 `subprocess.Popen`
- Python 入口脚本应自提权：`_ensure_admin()` 检测 → `ShellExecuteW runas` → 退出

### PLCSIM Advanced V8.0
- Runtime Manager 必须运行才能 PowerOn（已修复：自动启动）
- CommunicationInterface PowerOn 后只读（golden 备份已含接口配置）
- ResetNetInterfaceBindings() V8.0 不再支持（已加 try/except）

### TIA Portal Openness
- headless 编译需要 Siemens 后台服务初始化，首次需开一次 GUI
- DownloadProvider.Download() 需要 WithUserInterface 模式（PLCSIM 虚拟网卡限制）
- 下载确认对话框无法完全静默（on_pre/on_post 回调只能部分自动化）

### V21 迁移障碍
- DLL 拆分：`Siemens.Engineering.dll` → `Base.dll` + `Step7.dll`
- Public Key Token 变更：`d29ec89bac048f84` → `29bfe5fdf4ba5d3b`
- 项目升级 4600:000103 错误（磁盘空间不足）

### Golden Backup 策略
- 首次下载必须 TIA Portal GUI 手动完成（硬件配置）
- 之后用 `archive_instance()` 创建 golden.zip
- 后续用 `restore_instance()` 恢复，无需再开 TIA Portal

---

## 七、遗留未提交文件

这些文件在工作目录中未跟踪，不属于 P3 核心改动：

| 文件 | 说明 | 建议 |
|:-----|:-----|:-----|
| `.claude/`, `.opencode/` | 用户 IDE 配置 | 不提交 |
| `AGENTS.md`, `OpenCode.md` | Agent 定义文件 | 按需提交 |
| `plc-mcp-kit/` | 自定义 MCP Kit 插件项目 | 可考虑提交 |
| `scripts/` | 运维脚本 | 可考虑提交 |
| `mcp-servers/tia-mcp/@AutomationLog.txt` | Siemens 临时日志 | **不提交** |
