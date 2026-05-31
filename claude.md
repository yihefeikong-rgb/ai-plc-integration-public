# AI 接入 PLC 与工业机器人 — Claude Code 项目指令

> **项目目标**：构建一个生产级的 AI Agent 系统，让 Claude/Cursor/GPT 等 AI 能够通过自然语言直接监控、控制西门子 PLC、三菱 PLC 和工业机器人，并具备自动生成西门子 PLC 代码的能力。
> 
> **技术栈**：MCP (Model Context Protocol) + Python + C#/.NET + Docker + OPC UA / Modbus / MC协议 + TIA Portal Openness
> 
> **实施周期**：10 周，5 个阶段，渐进式交付

---

## 📋 项目结构（你将要创建的目录）

```
ai-plc-integration/
├── .cursorrules              # Cursor IDE 规则（如用 Cursor）
├── claude.md               # 本文件 — 项目总纲
├── README.md               # 项目说明与快速开始
├── docker-compose.yml      # 全栈一键部署
├── Makefile                # 常用命令快捷入口
│
├── docs/                   # 技术文档
│   ├── phase-1-runtime.md      # 阶段1：运行态基础
│   ├── phase-2-control-loop.md # 阶段2：AI控制闭环
│   ├── phase-3-tia-engineering.md # 阶段3：西门子工程态
│   ├── phase-4-robot.md        # 阶段4：工业机器人
│   ├── phase-5-orchestration.md # 阶段5：统一编排
│   └── architecture.mmd        # 架构图 (Mermaid)
│
├── mcp-servers/            # MCP 服务器集合
│   ├── opcua-mcp/          # 西门子/通用 OPC UA MCP
│   ├── modbus-mcp/         # Modbus 设备 MCP
│   ├── mitsubishi-mcp/     # 三菱 MC 协议 MCP
│   ├── tia-mcp/            # TIA Portal Openness MCP（西门子工程态）
│   └── robot-mcp/          # 工业机器人 MCP
│
├── edge-gateway/           # 边缘网关
│   ├── Dockerfile
│   ├── src/
│   └── config/
│
├── plc-code-templates/     # AI 生成 PLC 代码的 Prompt 模板
│   ├── siemens-scl/
│   │   ├── motor-control.md
│   │   ├── conveyor.md
│   │   └── pid-controller.md
│   └── openplc-iec/
│
├── safety/                 # 安全策略与审计
│   ├── interlock-rules.yml
│   └── audit-logger.py
│
├── tests/                  # 测试套件
│   ├── integration/
│   └── unit/
│
└── scripts/                # 运维脚本
    ├── setup-edge.sh
    ├── deploy-mcp.sh
    └── backup-config.sh
```

---

## 🎯 核心原则（你必须遵守）

### 1. 安全优先
- **所有写入操作必须经过影子仿真验证**（PLCSIM / OpenPLC）
- **生产环境 AI 只有读取权限**，写入需人工确认（双人确认）
- **连续 3 次异常值自动熔断**，切断 AI 控制权限
- **所有 MCP 调用必须记录审计日志**，保留 1 年

### 2. 渐进交付
- **阶段不可跳**：必须先跑通运行态（读数据），再做控制闭环（写指令），最后工程态（生成代码）
- **每阶段必须有可演示的交付物**，才能进入下一阶段
- **先单品牌再混合**：西门子跑通后再加三菱，最后加机器人

### 3. 协议分层
- **西门子**：OPC UA（运行态）+ TIA Openness（工程态）
- **三菱**：MC 协议 3E/4E 帧（仅运行态，无工程态 API）
- **机器人**：ROS2 / PyRI / 现场总线（运行态）

### 4. 本地优先
- **LLM 优先本地部署**（Qwen3-Coder / DeepSeek-Coder），数据不出厂
- **云端仅用于非敏感数据**（如公开文档查询）
- **边缘网关必须能离线运行**

---

## 🚀 五阶段实施计划

### 阶段 1：运行态基础（Week 1-2）
**目标**：AI 能实时监控 PLC 数据

**关键任务**：
1. 搭建边缘网关（Docker 化）
2. 部署 OPC UA MCP Server（kukapay/opcua-mcp 或自研）
3. 自研三菱 MC 协议 MCP Server（无现成开源）
4. 在 Claude/Cursor 中配置 MCP，验证自然语言读数据

**交付物**：
- `mcp-servers/opcua-mcp/` — 可连接西门子 S7-1200/1500
- `mcp-servers/mitsubishi-mcp/` — 可连接三菱 FX5U/Q 系列
- 演示视频：AI 读取温度/压力/转速

**技术要点**：
```python
# OPC UA MCP 最小实现（参考）
from fastmcp import FastMCP
from asyncua import Client

mcp = FastMCP("opcua-plc")

@mcp.tool()
async def read_node(namespace: int, identifier: str) -> float:
    async with Client("opc.tcp://192.168.1.10:4840") as client:
        node = client.get_node(f"ns={namespace};s={identifier}")
        return await node.read_value()
```

---

### 阶段 2：AI 控制闭环（Week 3-4）
**目标**：AI 根据数据做决策并回写控制指令

**关键任务**：
1. 封装业务逻辑 MCP 工具（启动/停止/调速/复位）
2. 加入安全互锁（读取联锁状态位后才允许写入）
3. 部署本地 LLM（Ollama + Qwen3）
4. 部署时序数据库（InfluxDB）+ 看板（Grafana）

**交付物**：
- `mcp-servers/opcua-mcp/` 新增 write 工具（带互锁检查）
- `edge-gateway/` 含 InfluxDB + Grafana Docker Compose
- `safety/interlock-rules.yml` — 互锁规则配置

**安全规则示例**：
```yaml
# interlock-rules.yml
write_rules:
  - target: "DB1.MotorSpeed"
    max_value: 3000
    min_value: 0
    require_bits: ["DB1.SafetyOK", "DB1.EmergencyStopOff"]
    shadow_test: true  # 必须先写入 PLCSIM 验证

  - target: "DB1.HeaterPower"
    max_value: 100
    require_bits: ["DB1.TemperatureSensorOK"]
    cooldown_seconds: 5  # 两次写入间隔
```

---

### 阶段 3：西门子工程态（Week 5-7）
**目标**：AI 直接生成 PLC 程序并下载到 S7-1500

**关键任务**：
1. 搭建 TIA Portal Openness 环境（Windows 工程站）
2. 部署 TIA MCP 桥接（参考 tia-copilot-genai-bridge 架构）
3. 实现 AI → SCL 代码 → 创建 FB → 编译 → PLCSIM 验证 → 下载
4. 建立代码模板库（电机控制、传送带、PID 等）

**交付物**：
- `mcp-servers/tia-mcp/` — .NET 8 Host + .NET Framework 4.8 Worker
- `plc-code-templates/siemens-scl/` — Prompt 模板库
- 演示：自然语言生成电机正反转 FB，编译通过并下载

**TIA Openness 核心代码框架**：
```csharp
// TiaMcpHost/Program.cs 核心结构
using Siemens.Engineering;

public class TiaMcpServer 
{
    public async Task<string> GenerateBlock(string name, string sclCode)
    {
        using (var tia = new TiaPortal(TiaPortalMode.WithoutUserInterface))
        {
            var project = tia.Projects.Open(new FileInfo("Template.ap19"));
            var plc = project.Devices[0].GetService<PlcSoftware>();

            var fb = plc.BlockGroup.Blocks.Create(
                name, 
                PlcBlockType.FunctionBlock, 
                PlcProgrammingLanguage.SCL
            );
            fb.SourceCode.Text = sclCode;

            var compileResult = plc.GetService<ICompilable>().Compile();
            if (compileResult.State == CompileResultState.Success)
            {
                project.Save();
                return $"✅ {name} 编译成功，已保存";
            }
            return $"❌ 编译失败: {compileResult.ErrorCount} 个错误";
        }
    }
}
```

---

### 阶段 4：工业机器人接入（Week 8）
**目标**：ABB/UR 机器人纳入 AI 统一控制

**关键任务**：
1. 部署 PyRI 开源示教器（树莓派/工控机）
2. 自研 Robot MCP Server（关节控制/位姿读取/程序调用）
3. 实现 PLC-机器人联动（PLC 定位 → AI 触发机器人 → 完成信号回写）

**交付物**：
- `mcp-servers/robot-mcp/` — 支持 PyRI / ROS2 桥接
- 演示：传送带到位 → 机械手抓取 → 放回

---

### 阶段 5：统一编排与安全加固（Week 9-10）
**目标**：多品牌设备统一 Agent 调度 + 生产级安全

**关键任务**：
1. 部署 PolyMCP 统一网关或自研 MCP Hub
2. 实现自然语言解析 → 多设备指令分发
3. 安全加固：权限隔离、影子模式、审计日志、异常熔断
4. 编写完整测试套件与运维手册

**交付物**：
- `docker-compose.yml` — 全栈一键部署
- `safety/audit-logger.py` — 审计系统
- `tests/integration/` — 端到端测试
- 生产部署文档

---

## 🔧 技术规范

### MCP Server 开发规范
- 使用 **FastMCP** (Python) 或 **MCP SDK** (TypeScript)
- 每个工具必须有 **JSON Schema 描述**和**自然语言 docstring**
- 所有工具必须支持 `--json` 输出模式
- 错误处理：返回结构化错误 `{error: string, code: string, suggestion: string}`

### PLC 通信规范
- **西门子**：OPC UA 优先，S7 协议（python-snap7）备选
- **三菱**：MC 协议 3E 帧（ASCII）优先，4E 帧（Binary）备选
- **超时设置**：读取 5s，写入 10s，连接 30s
- **重试策略**：失败重试 3 次，指数退避

### 代码生成规范（西门子 SCL）
- 必须符合 **IEC 61131-3** 标准
- 必须包含：**急停互锁、故障处理、注释、版本信息**
- 变量命名：**匈牙利命名法**（如 `bEmergencyStop`, `rMotorSpeed`）
- 每个 FB 必须包含：**输入验证、输出限幅、状态机**

---

## 🛡️ 安全红线（绝对不可违反）

1. **禁止 AI 直接操作急停回路**（只能读取状态，不能写入）
2. **禁止 AI 修改安全 PLC（F-CPU）的任何参数**
3. **所有控制指令必须经过影子仿真验证**
4. **生产环境写入操作必须双人确认**（AI 建议 → 工程师确认 → 执行）
5. **异常值自动熔断**：连续 3 次写入超出合理范围，自动禁用 AI 控制
6. **审计日志不可篡改**：使用只追加模式写入独立存储

---

## 📚 参考资源

### GitHub 仓库
- `kukapay/opcua-mcp` — OPC UA MCP 服务器
- `alejoseb/ModbusMCP` — Modbus MCP 服务器
- `feelautom/tia-copilot-genai-bridge` — TIA Portal MCP 桥接（参考架构）
- `pyri-project/pyri-core` — 开源工业机器人示教器
- `thiagoralves/OpenPLC_v3` — 开源 PLC 运行时
- `beriberikix/awesome-mcp-hardware` — MCP 硬件项目大全

### 学术参考
- `AICPS/LLM_4_PLC` — UC Irvine 的 LLM 生成 PLC 代码研究
- `Luoji-zju/Agents4PLC_release` — 浙江大学的多 Agent PLC 代码生成

### 西门子官方
- TIA Portal Openness API 文档（需西门子账号）
- Industrial Copilot（西门子官方 AI 助手）

---

## ✅ 检查清单（每阶段完成时自查）

- [ ] 该阶段所有代码已提交 Git
- [ ] 已编写该阶段 README 和 API 文档
- [ ] 测试通过率 > 90%
- [ ] 安全审计日志已启用
- [ ] 已录制演示视频或截图
- [ ] 下一阶段的技术风险已评估

---

## 🎬 立即开始（今天的任务）

如果你的设备：
- **1 台西门子 S7-1200/1500 + 笔记本电脑**
  → 执行 `docs/phase-1-runtime.md` 中的"今日快速验证"章节

- **1 台三菱 FX5U + 笔记本电脑**
  → 执行 `docs/phase-1-runtime.md` 中的"三菱 MC 协议 MCP"章节

- **只有电脑无硬件**
  → 使用 OpenPLC Docker 仿真 + 虚拟 PLC 验证 MCP 连通性

---

> **记住**：先让 AI 能"看见"设备（读数据），再让它能"动手"（写指令），最后才让它能"思考"（生成代码）。安全永远是第一优先级。
