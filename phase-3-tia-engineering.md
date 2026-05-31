# 阶段 3：西门子工程态（Week 5-7）

> **目标**：AI 直接生成 PLC 程序（SCL 代码），通过 TIA Portal Openness API 自动创建 FB/FC，编译并下载到 S7-1500。
> **前提**：Windows 工程站，已安装 TIA Portal V17+ 并勾选 Openness 组件。

---

## TIA Portal Openness 环境配置

### 1. 安装与授权

1. 安装 TIA Portal V17/V18/V19（V19 推荐）
2. **必须勾选** "TIA Portal Openness" 组件（默认不安装）
3. 安装完成后，找到 DLL 文件：
   ```
   C:\Program Files\Siemens\Automation\Portal V19\PublicAPI\V19\
   Siemens.Engineering.dll
   Siemens.Engineering.Hmi.dll
   ```

### 2. Windows 用户组权限

1. 以管理员身份启动 TIA Portal
2. 选项 -> 设置 -> 常规 -> 专家设置
3. 勾选 **"通过外部程序启用 TIA Portal 的访问"**
4. 将当前 Windows 用户添加到 **"SIEMENS TIA Openness"** 用户组：
   ```cmd
   # 以管理员运行 CMD
   net localgroup "SIEMENS TIA Openness" %username% /add
   ```
5. **重启电脑**（必须）

### 3. 创建项目模板

在 TIA Portal 中创建一个空项目 `Template.ap19`，包含：
- 一台 S7-1500 CPU（如 6ES7 515-2AM02-0AB0）
- 基本硬件组态（电源、DI/DO 模块）
- 一个空的程序块文件夹

保存并关闭。此模板将被 Openness API 复制和修改。

---

## TIA MCP Server 架构

采用双进程设计解决 .NET 版本兼容性问题：

```
Claude/Cursor (MCP Client)
    |
    v  stdio / JSON-RPC
TiaMcpHost (.NET 8) —— MCP 协议处理、AI 交互
    |
    v  NamedPipe / TCP
TiaWorker (.NET Framework 4.8) —— 加载 Siemens.Engineering.dll
    |
    v  COM Interop
TIA Portal (无头模式) —— 创建块、编译、保存
```

---

## 核心代码框架

### TiaWorker（.NET Framework 4.8）

```csharp
// TiaWorker/Program.cs
using System;
using System.IO;
using Siemens.Engineering;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;

namespace TiaWorker
{
    class Program
    {
        static void Main(string[] args)
        {
            // 1. 以无头模式启动 TIA Portal
            using (TiaPortal tia = new TiaPortal(TiaPortalMode.WithoutUserInterface))
            {
                Console.WriteLine("TIA Portal 无头模式已启动");

                // 2. 打开模板项目
                var templatePath = @"C:\Projects\Template.ap19";
                var project = tia.Projects.Open(new FileInfo(templatePath));
                var plc = project.Devices[0].GetService<PlcSoftware>();

                Console.WriteLine($"项目已加载: {project.Name}");
                Console.WriteLine($"PLC: {plc.Name}");

                // 3. 等待 Host 的命令
                while (true)
                {
                    var cmd = Console.ReadLine();
                    if (cmd == "EXIT") break;

                    var parts = cmd.Split('|');
                    var action = parts[0];

                    try
                    {
                        switch (action)
                        {
                            case "CREATE_FB":
                                var fbName = parts[1];
                                var sclCode = parts[2];
                                var result = CreateFunctionBlock(plc, fbName, sclCode);
                                Console.WriteLine($"RESULT|{result}");
                                break;

                            case "COMPILE":
                                var compileResult = CompileProject(plc);
                                Console.WriteLine($"RESULT|{compileResult}");
                                break;

                            case "SAVE":
                                project.Save();
                                Console.WriteLine("RESULT|SAVED");
                                break;

                            case "LIST_BLOCKS":
                                var blocks = ListBlocks(plc);
                                Console.WriteLine($"RESULT|{blocks}");
                                break;
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"ERROR|{ex.Message}");
                    }
                }

                project.Close();
            }
        }

        static string CreateFunctionBlock(PlcSoftware plc, string name, string sclCode)
        {
            var blockGroup = plc.BlockGroup;

            // 检查是否已存在
            foreach (var existing in blockGroup.Blocks)
            {
                if (existing.Name == name)
                    return $"EXISTS|块 {name} 已存在";
            }

            // 创建 FB
            var fb = blockGroup.Blocks.Create(
                name, 
                PlcBlockType.FunctionBlock, 
                PlcProgrammingLanguage.SCL
            );

            // 写入 SCL 源代码
            fb.SourceCode.Text = sclCode;

            return $"CREATED|{name}";
        }

        static string CompileProject(PlcSoftware plc)
        {
            var compilable = plc.GetService<ICompilable>();
            var result = compilable.Compile();

            var state = result.State.ToString();
            var errors = result.ErrorCount;
            var warnings = result.WarningCount;

            return $"{state}|Errors:{errors}|Warnings:{warnings}";
        }

        static string ListBlocks(PlcSoftware plc)
        {
            var names = new System.Collections.Generic.List<string>();
            foreach (var block in plc.BlockGroup.Blocks)
            {
                names.Add($"{block.Name}({block.BlockType})");
            }
            return string.Join(",", names);
        }
    }
}
```

### TiaMcpHost（.NET 8 + FastMCP Python 桥接）

```python
# tia_mcp_host.py
from fastmcp import FastMCP
import subprocess
import json
import os

mcp = FastMCP("tia-portal")

# 启动 TiaWorker 进程
TIA_WORKER_PATH = r"C:\Projects\TiaWorker\bin\Release\TiaWorker.exe"
worker = None

def get_worker():
    global worker
    if worker is None or worker.poll() is not None:
        worker = subprocess.Popen(
            [TIA_WORKER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        # 等待启动确认
        startup = worker.stdout.readline().strip()
        print(f"TiaWorker 启动: {startup}")
    return worker

@mcp.tool()
def create_function_block(name: str, description: str) -> dict:
    """根据描述生成 SCL 功能块并写入 TIA Portal

    Args:
        name: FB 名称（如 MotorControl_FB）
        description: 功能描述，AI 将据此生成 SCL 代码
    """
    # 1. 调用本地 LLM 生成 SCL 代码
    scl_code = generate_scl_from_description(description, name)

    # 2. 发送命令到 TiaWorker
    w = get_worker()
    cmd = f"CREATE_FB|{name}|{scl_code.replace(chr(10), '\n')}"
    w.stdin.write(cmd + "\n")
    w.stdin.flush()

    result = w.stdout.readline().strip()

    if result.startswith("RESULT|CREATED"):
        return {"status": "created", "block": name, "code_preview": scl_code[:200]}
    elif result.startswith("RESULT|EXISTS"):
        return {"status": "exists", "message": result.split("|")[1]}
    else:
        return {"status": "error", "message": result}

@mcp.tool()
def compile_project() -> dict:
    """编译当前 TIA Portal 项目"""
    w = get_worker()
    w.stdin.write("COMPILE\n")
    w.stdin.flush()

    result = w.stdout.readline().strip()
    parts = result.replace("RESULT|", "").split("|")

    return {
        "state": parts[0],
        "errors": int(parts[1].split(":")[1]),
        "warnings": int(parts[2].split(":")[1])
    }

@mcp.tool()
def save_project() -> dict:
    """保存 TIA Portal 项目"""
    w = get_worker()
    w.stdin.write("SAVE\n")
    w.stdin.flush()

    result = w.stdout.readline().strip()
    return {"status": "saved" if "SAVED" in result else "error"}

@mcp.tool()
def list_blocks() -> dict:
    """列出当前项目中的所有程序块"""
    w = get_worker()
    w.stdin.write("LIST_BLOCKS\n")
    w.stdin.flush()

    result = w.stdout.readline().strip()
    blocks = result.replace("RESULT|", "").split(",")
    return {"blocks": blocks, "count": len(blocks)}

def generate_scl_from_description(description: str, fb_name: str) -> str:
    """调用本地 LLM 生成 SCL 代码（简化版，实际应调用 Ollama/Qwen3）"""
    # 这里应调用本地 LLM API
    # 以下为模板示例

    template = f"""FUNCTION_BLOCK "{fb_name}"
VERSION : 0.1

VAR_INPUT
    Start       : Bool;     // 启动信号
    Stop        : Bool;     // 停止信号
    SpeedSetpoint : Int;    // 速度设定值 (0-3000 RPM)
END_VAR

VAR_OUTPUT
    Running     : Bool;     // 运行状态
    ActualSpeed : Int;      // 实际转速
    Fault       : Bool;     // 故障状态
END_VAR

VAR
    rSpeedRamp  : Real;     // 速度斜坡
    tmrFault    : TON;      // 故障定时器
END_VAR

BEGIN
    // 急停互锁
    IF #Stop THEN
        #Running := FALSE;
        #ActualSpeed := 0;
        RETURN;
    END_IF;

    // 启动逻辑
    IF #Start AND NOT #Fault THEN
        #Running := TRUE;
    END_IF;

    // 速度斜坡（防冲击）
    IF #Running THEN
        #rSpeedRamp := #rSpeedRamp + (#SpeedSetpoint - #rSpeedRamp) * 0.1;
        #ActualSpeed := REAL_TO_INT(#rSpeedRamp);
    ELSE
        #rSpeedRamp := 0;
        #ActualSpeed := 0;
    END_IF;

    // 超速保护
    IF #ActualSpeed > 3200 THEN
        #Fault := TRUE;
        #Running := FALSE;
    END_IF;

    // 故障复位
    IF NOT #Start THEN
        #Fault := FALSE;
    END_IF;
END_FUNCTION_BLOCK
"""
    return template

if __name__ == "__main__":
    mcp.run(transport='stdio')
```

---

## SCL 代码生成 Prompt 模板

### 模板 1：电机正反转 FB

```markdown
# PLC 代码生成提示词：电机正反转控制

## 需求描述
{user_description}

## 输出要求
- 语言：SCL（Structured Control Language）
- 标准：IEC 61131-3
- 必须包含：
  1. 急停互锁（Emergency Stop）
  2. 正转/反转互锁（防止同时启动）
  3. 过载保护（Overload）
  4. 运行状态反馈
  5. 故障复位逻辑

## 变量命名规范
- 输入：iXxx（如 iStart, iStop）
- 输出：oXxx（如 oRunForward, oFault）
- 内部：rXxx（Real）, tmrXxx（Timer）, cntXxx（Counter）

## 代码结构
```scl
FUNCTION_BLOCK "MotorForwardReverse_FB"
VERSION : 0.1

VAR_INPUT
    iStartForward   : Bool;
    iStartReverse   : Bool;
    iStop           : Bool;     // 急停，常闭
    iOverload       : Bool;     // 过载信号，常闭
    iSpeedForward   : Int := 1500;   // 正转速度设定
    iSpeedReverse   : Int := 1500;   // 反转速度设定
END_VAR

VAR_OUTPUT
    oRunForward     : Bool;
    oRunReverse     : Bool;
    oFault          : Bool;
    oActualSpeed    : Int;
END_VAR

VAR
    rSpeedRamp      : Real;
    tmrOverload     : TON;      // 过载确认延时
END_VAR

BEGIN
    // [AI 生成的逻辑代码]
END_FUNCTION_BLOCK
```

## 安全规则
- 急停信号为 FALSE 时，必须立即切断所有输出
- 正转和反转输出绝对不允许同时为 TRUE
- 过载信号持续 2 秒后确认故障
- 故障发生后，必须等待 iStop 释放后才能复位
```

### 模板 2：传送带控制 FB

```markdown
# PLC 代码生成提示词：传送带控制

## 需求描述
{user_description}

## 输出要求
- 支持多段速度（低速/高速）
- 物料检测传感器联动
- 堵料报警（超时未检测到物料离开）
- 累计计数功能
- 与上位机通信状态（心跳）
```

---

## 编译与下载流程

```
自然语言需求
    |
    v
AI 生成 SCL 代码（本地 LLM）
    |
    v
TIA MCP Server 调用 Openness API
    |
    v
TiaWorker 创建 FB + 写入代码
    |
    v
自动编译
    ├── 成功 -> 保存项目 -> 可选 PLCSIM 验证 -> 人工确认 -> 下载到 PLC
    └── 失败 -> 返回错误信息 -> AI 修正代码 -> 重新编译
```

---

## 本周检查清单

- [ ] TIA Portal Openness 环境配置完成（DLL 引用、用户组、无头模式测试）
- [ ] TiaWorker 能独立启动并响应命令
- [ ] TiaMcpHost 能接收 MCP 调用并转发到 TiaWorker
- [ ] 自然语言 -> SCL 代码 -> 创建 FB -> 编译 全流程跑通
- [ ] 编译错误能正确反馈给 AI 进行修正
- [ ] PLCSIM Advanced 仿真验证通过
- [ ] 代码模板库至少包含 3 个标准 FB（电机、传送带、PID）
