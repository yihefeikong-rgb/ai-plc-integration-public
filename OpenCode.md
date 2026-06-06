# AI 接入 PLC 与工业机器人 — OpenCode 项目规则

> **项目目标**：构建一个生产级的 AI Agent 系统，让 AI 能够通过自然语言直接监控、控制西门子 PLC、三菱 PLC 和工业机器人，并具备自动生成西门子 PLC 代码的能力。
>
> **技术栈**：MCP (Model Context Protocol) + Python + C#/.NET + Docker + OPC UA / Modbus / MC协议 + TIA Portal Openness
>
> **实施周期**：10 周，5 个阶段，渐进式交付

---

## 目录
1. [项目结构](#项目结构)
2. [关键路径](#关键路径)
3. [PLCSIM Advanced V5.0 操作规则](#plcsim-advanced-v50-操作规则)
4. [Factory IO 连接配置](#factory-io-连接配置)
5. [CartGen + DeepSeek 代码生成](#cartgen--deepseek-代码生成)
6. [TIA Portal Openness API](#tia-portal-openness-api)
7. [模板库](#模板库)
8. [安全红线](#安全红线)
9. [GitHub 备份策略](#github-备份策略)
10. [三端自动化状态](#三端自动化状态)
11. [实施阶段](#实施阶段)
12. [行业规则（全局生效）](#行业规则全局生效)
13. [通用约束](#通用约束)

---

## 项目结构

```
ai-plc-integration/
├── README.md
├── docker-compose.yml
├── Makefile
├── docs/                    # 技术文档
│   ├── phase-1-runtime.md
│   ├── phase-2-control-loop.md
│   ├── phase-3-tia-engineering.md
│   ├── phase-4-robot.md
│   └── phase-5-orchestration.md
├── mcp-servers/
│   ├── opcua-mcp/           # 西门子/通用 OPC UA MCP（待建）
│   ├── modbus-mcp/          # Modbus 设备 MCP（待建）
│   ├── mitsubishi-mcp/      # 三菱 MC 协议 MCP（待建）
│   ├── tia-mcp/             # TIA Portal Openness MCP（已完成）
│   │   ├── CartGen/         # 梯形图生成器 (.NET 8)
│   │   ├── templates/       # 18 个中文名 PLC 模板
│   │   ├── gen_from_template.py
│   │   ├── generate_custom.py
│   │   ├── ladder_renderer.py
│   │   └── plcsim_api.py
│   └── robot-mcp/           # 工业机器人 MCP（待建）
├── edge-gateway/            # 边缘网关（待建）
├── plc-code-templates/      # AI 生成 PLC 代码的 Prompt 模板
├── safety/                  # 安全策略与审计（待建）
├── tests/                   # 测试套件
└── scripts/                 # 运维脚本
```

---

## 关键路径

| 项目 | 路径 |
|:----|:-----|
| **TIA Portal 安装目录** | `D:\TIA BEN TI\Portal V18\` |
| **Openness API DLL** | `D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll` |
| **Contract DLL** | `D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll` |
| **仿真/输出目录** | `D:\TIA FANG ZHEN\` |
| **TIA 项目文件** | `D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18` |
| **CartGen DLL** | `mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll` |
| **PLCSIM API 封装** | `mcp-servers/tia-mcp/plcsim_api.py` |
| **PLCSIM API DLL** | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\8.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll` |
| **SVG 渲染** | `mcp-servers/tia-mcp/ladder_renderer.py` |
| **DeepSeek 生成** | `mcp-servers/tia-mcp/generate_custom.py` |
| **模板目录** | `mcp-servers/tia-mcp/templates/` |
| **DeepSeek API Key** | 项目根目录 `.env` |
| **Reasonix 配置文件** | `%USERPROFILE%\.reasonix\config.json` |
| **Factory IO auto.cfg** | `C:\ProgramData\Real Games\Factory IO\auto.cfg` |
| **Factory IO config.cfg** | `%LOCALAPPDATA%\Real Games\Factory IO\config.cfg` |
| **Factory IO 场景文件** | `Documents\Factory IO\My Scenes\` |
| **Factory IO Unity 日志** | `%LOCALAPPDATA%\Real Games\Factory IO\Player.log` |
| **PLCSIM 持久化** | `Documents\Siemens\Simatic\Simulation\Runtime\Persistence` |

---

## PLCSIM Advanced V8.0 操作规则

### ⚠️ 核心问题（不可绕过）

**任何方式的 PowerOff 后，实例都无法再次启动（PowerOn → Booting → Off）。** 包括：
- API `instance.PowerOff()`
- API `instance.Stop()` + `instance.PowerOff()`
- GUI 点击电源按钮
- `taskkill /f` 杀进程

**推荐恢复方式：重启电脑。** 但在无法立即重启时，可尝试以下方法（成功率依次递增）：

| # | 方法 | 成功率 | 操作 |
|:-|:----|:------:|:-----|
| 1 | 杀进程 | ~40% | 任务管理器杀 `s7advplc.exe` + `SimRtMgmt.exe` |
| 2 | 重置 NPF 驱动 | ~50% | `net stop npf`，等待 5 秒，`net start npf`，重新 PowerOn |
| 3 | 删持久化文件 | ~50% | 清空 `Documents\Siemens\Simatic\Simulation\Runtime\Persistence` 下的 `.sim`/`.lock` 文件 |
| 4 | 组合拳 | 60-70% | 先杀进程，再删持久化文件，最后重置 NPF 驱动 |

根本原因：疑似授权检查 bug 或 NPF 驱动状态机问题。V5.0 通病，社区大量报告。升级到 V6.0 Update 2 可能解决。

### 正确的启动顺序（日常使用）

1. 重启电脑（必须）
2. 打开 PLCSIM Advanced V5.0 GUI
3. API 或 GUI 启动实例 `factoryio`
4. 打开 Factory IO（控制台设 `instance_name = 'factoryio'`）
5. 开始工作，直到下次重启前都**不要关实例**

### 不 PowerOff 的更新方式

保持 RUN 状态，需要更新程序时：
1. TIA Portal 直接在线下载到 RUN 中的 PLC
2. 或 TIA 先把实例切到 STOP，下载完再切回 RUN
3. **不需要动 PowerOff**

### 如果必须"重启"实例

用 `restore_instance()` 从黄金备份恢复，而不是 PowerOff → PowerOn。

### PLCSIM API 功能状态

| 功能 | 方法 | 状态 |
|:----|:-----|:----:|
| 创建空壳实例 | `create_instance()` | ✅ |
| 黄金备份 | `archive_instance()` | ✅ |
| 从备份恢复 | `restore_instance()` | ✅ 已验证 |
| 切换 TCP/IP | `switch_to_tcpip()` | ✅ 需虚拟网卡 |
| 停止/删除 | `stop_instance()` | ✅ |
| 后台保活 | `plcsim_keeper.py` | ✅ Softbus 模式 |
| 列出实例 | `get_instances()` | ✅ |
| 设置通信接口 | `instance.CommunicationInterface = TCPIP` | ✅ |
| 设置 IP | `instance.SetIPSuite(0, SIPSuite4(...))` | ✅ |
| 通电 | `instance.PowerOn()` | ✅（WarningAlreadyExists 安全） |
| 运行 | `instance.Run()` | ❌ **-52 IsEmpty** — 无硬件配置 |
| 断电 | `instance.PowerOff()` | ⚠️ 会导致实例不可恢复 |

> **PythonNET 3.0+ 注意**：调用 PLCSIM API 时，枚举参数必须用枚举类型，不能直接用 int 隐式转换。例如 `instance.Interface = TCPIP` 应写为 `instance.Interface = SimulationInterface.TCPIP`。

### TCP/IP 模式

- **Siemens PLCSIM Virtual Ethernet Adapter 已安装**（接口 ID=13）
- 切换前需调用 `SimulationRuntimeManager.ResetNetInterfaceBindings()`
- 已验证：`restore_instance("factory_io1", golden_zip, storage, ip="10.0.0.1", interface="tcpip")` → RUN ✅
- `plcsim_api.py` 默认 `interface` 已改为 `"tcpip"`

### 自动化核心限制（不可绕过）

首次下载硬件配置必须在 TIA Portal GUI 中手动完成。Openness API 的 DownloadProvider 不支持首次下载（Siemens 官方确认）。首次下载完成后，后续 API 完全可用。

---

## Factory IO 连接配置

### 当前连接状态

- **驱动**：Siemens S7-PLCSIM → S7-1500 (S7-PLCSIM Advanced)
- **实例名**：`factoryio`
- **连接方式**：Softbus（本地进程通信）
- **测试场景**：From A to B

| 地址 | 信号 | 说明 |
|:----|:-----|:-----|
| %I0.1 | Sensor | 箱子到位检测 |
| %I0.2 | Run | 系统运行信号 |
| %Q0.1 | Conveyor | 传送带电机 |

### auto.cfg

位置：`C:\ProgramData\Real Games\Factory IO\auto.cfg`

```
drivers.siemens_s7plcsim.instance_name = 'factoryio'
drivers.siemens_s7plcsim.auto_connect = True
drivers.siemens_s7plcsim.connection_timeout = 60
```

### 控制台命令（按 `\` 打开）

- `drivers.siemens_s7plcsim.instance_name = 'name'` — 设置实例名（**必须单引号**）
- `drivers.siemens_s7plcsim.auto_connect = True` — 自动连接
- `scene.load_from_path(r"path")` — 加载场景
- `drivers.siemens_s71200_s71500.ip_address = "ip"` — TCP/IP 连接 IP
- `ui.show_welcome_window = False` — 隐藏欢迎窗口

### 场景文件结构（.factoryio = XML）

关键 XML 节点：
```xml
<Drivers CurrentDriver="6144">
  <SiemensS7PLCSIM>
    <Properties UseWords="False" InstanceName="factoryio" />
  </SiemensS7PLCSIM>
</Drivers>
```

| 驱动 | XML 标签 | `CurrentDriver` 值 |
|:----|:---------|:------------------:|
| S7-PLCSIM (Softbus) | `SiemensS7PLCSIM` | 6144 |
| S7-1200/1500 TCP | `SiemensS71200S71500TCP` | 6144 |
| Modbus TCP Client | `ModbusTCPClient` | 6176 |
| OPC UA | `OPCClientDA` | — |

- `CurrentDriver` 值存储在 Unity 序列化状态中，与驱动名称无关，切换后自动更新
- `.factoryio` 文件中的 `<Screenshot>` 节点是 BASE64 编码的场景缩略图

**注意**：切换驱动必须在 GUI 中操作（F4 → 下拉菜单），auto.cfg 不能切换当前驱动。

### 关键教训

- **PLCSIM Advanced GUI 必须开着**，否则 Factory IO 报 -4 DoesNotExist
- **不要用 taskkill /f 杀仿真进程**，NPF 驱动状态卡死，必须重启电脑
- 应使用 API 正常停止：`stop → PowerOff → UnregisterInstance`
- 实例名必须匹配（控制台设 `instance_name = 'factoryio'`）

---

## CartGen + DeepSeek 代码生成

### DeepSeek API

- Key：写在项目根目录 `.env`
- 模型：`deepseek-chat`，`temperature=0.3`，`max_tokens=4000`
- Prompt 模板：`mcp-servers/tia-mcp/generate_custom.py` 中的 `_LAD_PROMPT_TEMPLATE`
- 输出：LadderSpec JSON

### CartGen 约束

- 路径：`mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll`
- 支持 **5 种元素**：`normally_open`, `normally_closed`, `coil`, `coil_set`, `coil_reset`
- **不支持 `parallelElements`**：SimaticML 的 OrPart 从 Powerrail 分叉，自保持需要电路中部汇合
- 自保持用 **Set/Reset 模式**代替并联分支
- 一个网络可以多个线圈串联

### 调用方式

```bash
# 自定义生成（改 DESCRIPTION + BLOCK_NAME，然后运行）
python mcp-servers/tia-mcp/generate_custom.py

# 从模板生成
python mcp-servers/tia-mcp/gen_from_template.py 模板名

# CartGen 直接转换 JSON → SimaticML XML
dotnet exec mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll
```

### 变量命名规范

- `iXxx` — 输入（如 `iStart`, `iStop`, `iSensor`）
- `oXxx` — 输出（如 `oMotor`, `oConveyor`）
- `mXxx` — 中间变量（如 `mRunning`, `mTimerDone`）
- 匈牙利命名法：`bEmergencyStop`, `rMotorSpeed`, `iCounter`

### 代码生成安全规则

- 所有输出必须有急停互锁（串联 `iStop` normally_closed）
- 正转/反转必须互锁
- 过载保护串联 `iOverload` normally_closed
- **不使用 parallelElements**（CartGen 不支持）
- 自保持用 Set/Reset 代替并联

### 工作流（gen-plc-block）

```
用户需求描述 → DeepSeek LadderSpec JSON → CartGen → SimaticML XML
  → 清洗 XML（去掉 MultilingualTextItem 空标签）
  → TIA Openness 导入 → 编译 → （可选 SVG 预览）
```

---

## TIA Portal Openness API

### PythonNET 导入方式

```python
import clr
clr.AddReference(r'D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll')
clr.AddReference(r'D:\TIA BEN TI\Portal V18\Bin\PublicAPI\Siemens.Engineering.Contract.dll')
from Siemens.Engineering import TiaPortal, TiaPortalMode, ImportOptions
from Siemens.Engineering.SW import SWImportOptions
from Siemens.Engineering.HW.Features import SoftwareContainer
from Siemens.Engineering.Compiler import ICompilable
from System.IO import FileInfo
```

### TIA MCP 核心能力

- 编译导入 SimaticML XML 块
- 通过 Openness API 自动化首次以外的手动下载
- CartGen 已通过 21 模板验证，0 警告 0 错误

---

## 模板库

18 个中文名模板，全部通过 CartGen 验证（0 错误 0 警告），放在 `mcp-servers/tia-mcp/templates/`：

### 电机控制类
| 模板 | 网络数 | 功能 |
|:----|:-----:|:-----|
| 电机正反转 | 6 | 正反转互锁、急停、过载 |
| 星三角启动 | 7 | 主星三角接触器切换 |
| 多电机顺序启动 | 8 | 三台电机顺序启停 |
| 单键启停 | 7 | 一个按钮控制启停 |

### 传送输送类
| 模板 | 网络数 | 功能 |
|:----|:-----:|:-----|
| 传送带控制 | 6 | 启停速度选择 |
| 输送带分拣 | 9 | 大小产品分拣推杆 |
| 小车往复3次 | 11 | 前进卸载后退装载循环 |

### 阀门泵类
| 模板 | 网络数 | 功能 |
|:----|:-----:|:-----|
| 阀门控制 | 8 | 开关阀反馈检测 |
| 水泵控制 | 9 | 手动自动液位切换 |
| 灌装机控制 | 10 | 瓶子灌装旋盖流程 |

### 建筑设施类
| 模板 | 网络数 | 功能 |
|:----|:-----:|:-----|
| 2层电梯 | 11 | 呼梯到站开关门 |
| 停车场道闸 | 7 | 来车抬闸满位显示 |
| 自动门控制 | 9 | 感应开关防夹保护 |
| 暖通空调风机 | 8 | 风机高低温切换过滤报警 |

### 报警/其他
| 模板 | 网络数 | 功能 |
|:----|:-----:|:-----|
| 报警灯控制 | 7 | 三色灯蜂鸣器锁存 |
| 8位抢答器 | 19 | 先按锁定指示蜂鸣复位 |
| 手动自动切换 | 10 | 手动自动双模式选择 |
| 气缸往复 | 6 | 限位自动往复 |

---

## 安全红线（绝对不可违反）

1. **禁止 AI 直接操作急停回路**（只能读取状态，不能写入）
2. **禁止 AI 修改安全 PLC（F-CPU）的任何参数**
3. **所有控制指令必须经过影子仿真验证**
4. **生产环境写入操作必须双人确认**（AI 建议 → 工程师确认 → 执行）
5. **异常值自动熔断**：连续 3 次写入超出合理范围，自动禁用 AI 控制
6. **审计日志不可篡改**：使用只追加模式写入独立存储

### 安全审核清单（PLC 代码审查）

- [ ] 是否包含急停互锁（串联 `normally_closed iStop`）
- [ ] 正转/反转是否互锁
- [ ] 过载保护是否串联 `normally_closed iOverload`
- [ ] 变量命名是否符合匈牙利命名法
- [ ] 是否包含输入验证、输出限幅、状态机
- [ ] API Key 是否从 `.env` 读取（不硬编码）
- [ ] 写入操作前是否调用了安全验证

### 协议超时规范

| 操作 | 超时 | 重试策略 |
|:----|:----:|:---------|
| 读取 | 5s | 3 次指数退避 |
| 写入 | 10s | 3 次指数退避 |
| 连接 | 30s | — |

---

## GitHub 备份策略

- **私有仓库（origin）**：`https://github.com/yihefeikong-rgb/ai-plc-integration`
- **公开仓库（public）**：`https://github.com/yihefeikong-rgb/ai-plc-integration-public`
- **更新时机**：每次有较大改动后，两个仓库都更新

```bash
git add -A && git commit -m "改动说明"
git push origin master
git push public master
```

### 回滚规则

如果改动后不能用，且仓库里的版本是可用的，就回滚：
```bash
git reset --hard origin/master
```

### 排除文件（不上传）
`.env`、`软件/*.exe/.msi`、`.reasonix/`、TIA Portal 项目文件（`*.ap18`、`*.bak`）

---

## 三端自动化状态

| 模块 | 状态 | 说明 |
|:----|:----:|:-----|
| **PLCSIM API** | ✅ | restore/archive/tcpip/keeper 全套通过 |
| **TIA MCP + CartGen** | ✅ | 21 模板 0 警告 0 错误 |
| **Factory IO 连接** | ✅ | Softbus 已通，S7-PLCSIM 驱动 + 实例名 factoryio |

### 待办
- 🟡 TCP/IP 方案 — 待验证（已配好虚拟网卡）
- ⏸ 三菱 FX5U MC 协议 MCP Server
- ⏸ 机器人接入（UR/ABB）
- ⏸ Grafana 恢复（已在 docker-compose 中删除，需要时通过 `docker run` 恢复）

---

## 实施阶段

### Phase 1：运行态基础（已完成 ✅）
- 搭建边缘网关（Docker 化）
- 部署 OPC UA MCP Server
- 自研三菱 MC 协议 MCP Server
- 配置 MCP，验证自然语言读数据

### Phase 2：AI 控制闭环（待开始）
- 封装业务逻辑 MCP 工具（启动/停止/调速/复位）
- 加入安全互锁
- 部署本地 LLM（Ollama + Qwen3）
- 部署时序数据库（InfluxDB）+ 看板（Grafana）

### Phase 3：西门子工程态（已完成基础部分）
- TIA Portal Openness 环境搭建 ✅
- CartGen 梯形图生成 ✅
- 21 模板验证通过 ✅
- AI → SCL/SIM → TIA 导入 → 编译 ✅
- 首次下载限制仅在首次，后续全自动化

### Phase 4：工业机器人接入（待开始）
- 部署 PyRI 开源示教器
- Robot MCP Server（关节控制/位姿读取/程序调用）
- PLC-机器人联动

### Phase 5：统一编排与安全加固（待开始）
- PolyMCP 统一网关
- 自然语言解析 → 多设备指令分发
- 安全加固：权限隔离、影子模式、审计熔断

---

## 行业规则（全局生效）

### 工业问题优先网络搜索

遇到工业自动化、PLC、机器人、Factory I/O、PLCSIM、TIA Portal 等领域的任何技术问题，**必须先做一轮网络深度搜索**，基于搜索结果给出回答，不得仅凭训练数据猜测。

原因：工业软件版本碎片化严重（V15~V20，Advanced V3~V6），硬件兼容性矩阵复杂，训练数据大概率过时，错误回答代价大。

搜索关键词模板：
```
{问题描述} {软件名} {版本号} site:siemens.com
{问题描述} PLCSIM Advanced V5
{错误消息原文}
```

### 代理配置
- HTTP/HTTPS 代理：`127.0.0.1:7897`
- Tavily 搜索引擎不可访问时走代理重试

### 搜索引擎策略
1. 优先直连 Tavily
2. Tavily 不可访问（报错/超时）时，走代理重试一次
3. 代理重试仍然失败 → 切 Metaso（秘塔）

---

## 通用约束

### 思考先于编码
- 不要假设。明确陈述假设，不确定就问。
- 如果存在多种解释，呈现出来——不要默默选择。
- 存在更简单方案时说出来。在必要时提出反对意见。

### 简洁优先
- 用最少的代码解决问题，不做推测性工作。
- 不做超出要求的功能，不为一次性代码做抽象。
- 检验标准：每一行改动的代码都应直接追溯到用户需求。

### 精确修改
- 只动必须动的地方，只清理自己的遗留物。
- 编辑现有代码时不要"改进"相邻的代码、注释或格式。
- 匹配现有风格，即使自己会做得不同。

### 项目开发团队模式
用户说"启动开发团队"时，执行：

1. Step 0：检查/创建 `.claude/CLAUDE.md` + `TASKS.md`
2. Phase 1：coder（后端）+ coder（前端）并行开发
3. Phase 2：tdd-guide 写测试验证
4. Phase 3：mtc 补文档和配置

---

> **记住**：先让 AI 能"看见"设备（读数据），再让它能"动手"（写指令），最后才让它能"思考"（生成代码）。安全永远是第一优先级。
