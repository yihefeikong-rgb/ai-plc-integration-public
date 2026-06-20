# AI Context — PLC 领域知识 + 项目上下文

> 生成时间：2026-06-18
> 供新的 AI 工程师快速掌握 PLC 领域知识和项目特有经验

---

## 1. PLC 领域知识总结

### 1.1 西门子 PLC 基础

- **S7-1200**: 小型 PLC，适合分布式/小型应用
- **S7-1500**: 中型/大型 PLC，性能更强，适合复杂控制
- **编程语言**:
  - **SCL** (Structured Control Language): 类似 Pascal 的高级语言，本项目首选
  - **LAD** (Ladder Diagram): 梯形图，电工最熟悉的图形化语言
  - **FBD** (Function Block Diagram): 功能块图
  - **STL** (Statement List): 指令表，西门子独有（逐步淘汰中）

### 1.2 TIA Portal

- TIA Portal = Totally Integrated Automation Portal
- 版本: V21（本项目主力）
- TIA Portal Openness: COM 接口，允许外部程序操作 TIA Portal
- 项目文件格式: `.ap18` (V18)、`.ap19` (V19)、`.ap21` (V21)

### 1.3 PLC 编程关键概念

- **FB** (Function Block): 带背景数据块的功能块（有记忆）
- **FC** (Function): 无记忆的函数
- **OB** (Organization Block): 组织块，程序入口（OB1 = 主循环）
- **DB** (Data Block): 数据块（GlobalDB / InstanceDB / ArrayDB）
- **UDT** (User Defined Type): 用户自定义类型
- **Tag Table**: 标签表，定义 IO 地址与符号名的映射

### 1.4 SCL 语法要点

```pascal
FUNCTION_BLOCK "MyControl"
    VAR_INPUT
        bStart : Bool;           // 启动按钮 （匈牙利命名：b=bool）
        rSetpoint : Real;        // 设定值（r=real）
    END_VAR
    VAR_OUTPUT
        qMotor : Bool;           // 电机输出（q=输出）
    END_VAR
    VAR
        iCounter : Int;          // 计数器（i=int）
        timerOn : TIME;          // 定时器
    END_VAR

    // 逻辑代码
    IF bStart AND NOT qMotor THEN
        qMotor := TRUE;
    END_IF;
END_FUNCTION_BLOCK
```

### 1.5 匈牙利命名法（本项目使用）

| 前缀 | 类型 | 示例 |
|------|------|------|
| b | Bool | bStart, bEStop |
| n | Int/Word | nCounter |
| i | DInt | iErrorCode |
| r | Real | rSetpoint, rSpeed |
| t | Timer | tOnDelay |
| q | 输出 | qMotor, qValve |
| s | 字符串 | sRecipeName |

---

## 2. TIA Portal 相关经验

### 2.1 V21 当前环境

- **TIA Portal V21** 是项目主版本（已从 V18 迁移）
- Windows 11 兼容性: V21 官方支持 Windows 10/11
- Openness 接口需要管理员权限运行
- 模块化 DLL 加载（V21 新架构）

### 2.2 V18 → V21 差异（遇到的）

- V21 项目格式 `.ap21`（不同于 V18 的 `.ap18`）
- PLCSIM Advanced V8.0 兼容 V18/V19/V21
- Openness API 基本兼容，部分新增功能 V18 没有
- 本项目的 `.env` 配置同时包含 V18 和 V21 路径

### 2.3 常见坑

- **TIA Portal 一次只能打开一个实例**
- **Openness 操作必须在主线程执行**
- **块编译前必须先保存项目**
- **下载到 PLCSIM 前 PLC 必须在 STOP 状态**
- **PLCSIM 实例名不能超过 8 字符**
- **Golden backup 的 zip 文件不能手动修改**

---

## 3. Openness API 相关知识

### 3.1 TiaWorker (C#) 架构

```csharp
// 核心流程
TiaPortal tia = new TiaPortal(TiaPortalMode.WithoutGUI);
tia.OpenProject(projectPath);
Device device = tia.GetDevice("PLC_1");
Software software = device.GetSoftware();
PLCSystem system = software.GetPLCSystem();

// 创建 FB
Block block = system.CreateBlock(BlockType.FB, "MyBlock", "SCL");
block.SetText(sclCode);

// 编译
system.Compile();

// 下载
system.DownloadToPLCSIM();
```

### 3.2 LAD 生成（本项目实现）

- 从 JSON 模板读取结构化网络描述
- 通过 Openness 的 `LadderNetwork` API 逐元素创建
- 支持: normally_open/normally_closed/coil/coil_set/coil_reset
- 20 个 JSON 模板覆盖常见场景（星三角、传送带、报警灯等）

### 3.3 SCL 代码写入

- 最简单的方式：直接设置块的源代码文本
- 不需要逐语句构建
- 本项目生 SCL 源码后，通过 TiaWorker 写入 TIA Portal

---

## 4. S7 协议相关知识

### 4.1 python-snap7

- 通过 S7 协议直接读写西门子 PLC（不经过 TIA Portal）
- 支持 PLCSIM Advanced 和真机
- 端口: 102
- 连接: IP + Rack + Slot

### 4.2 地址映射

| S7 地址 | 说明 | snap7 参数 |
|---------|------|-----------|
| M0.0 | Merker 位 | read_area('MK', 0, 0, 1) |
| MB0 | Merker 字节 | read_area('MK', 0, 0, 1) |
| MW10 | Merker 字 | read_area('MK', 0, 10, 2) |
| MD20 | Merker 双字 | read_area('MK', 0, 20, 4) |
| I0.0 | 输入位 | read_area('PE', 0, 0, 1) |
| Q0.0 | 输出位 | read_area('PA', 0, 0, 1) |
| DB1.DBW10 | DB 块字 | db_read(1, 10, 2) |

### 4.3 安全写入策略

本项目在 plc-mcp-bridge 中实现了 5 层安全：
1. 写入值范围检查
2. 异常跳变检测（连续两次写入差值过大则拦截）
3. 连续异常自动熔断（熔断后需手动复位）
4. 影子仿真验证（先仿真看结果再实际写入）
5. 审计日志记录（链式哈希，不可篡改）

---

## 5. 梯形图模板体系

### 5.1 JSON 模板格式

```json
{
  "blockName": "ConveyorControl",
  "language": "LAD",
  "interface": {
    "inputs": [
      { "name": "bStart", "type": "Bool", "address": "%I0.0", "comment": "启动按钮" },
      { "name": "bStop", "type": "Bool", "address": "%I0.1", "comment": "停止按钮" }
    ],
    "outputs": [
      { "name": "qMotor", "type": "Bool", "address": "%Q0.0", "comment": "电机输出" }
    ],
    "local": [
      { "name": "bRun", "type": "Bool", "comment": "运行状态" }
    ]
  },
  "networks": [
    {
      "title": "启停控制",
      "comment": "启动保持和停止互锁",
      "elements": [
        { "type": "normally_open", "operand": "bStart" },
        { "type": "normally_closed", "operand": "bStop" },
        { "type": "coil", "operand": "qMotor" }
      ]
    }
  ]
}
```

### 5.2 现有模板清单（20 个）

| 文件名 | 场景 | 网络数 |
|--------|------|--------|
| 单键启停 | 单按钮启停控制 | 2 |
| 电机正反转 | 带互锁正反转 | 3 |
| 星三角启动 | 星三角降压启动 | 3 |
| 报警灯控制 | 三色报警灯 | 3 |
| 传送带控制 | 输送带启停 | 2 |
| 多电机顺序启动 | 顺序启动逆序停止 | 4 |
| 手动自动切换 | 手自动模式 | 3 |
| 水泵控制 | 液位控制 | 3 |
| 阀门控制 | 阀门开关控制 | 2 |
| 气缸往复 | 气动缸循环 | 3 |
| 自动门控制 | 感应门 | 3 |
| 暖通空调风机 | HVAC 风机 | 3 |
| 灌装机控制 | 灌装流程 | 4 |
| 输送带分拣 | 分拣控制 | 4 |
| 装配工作站 | 装配流程 | 5 |
| 码垛机控制 | 码垛流程 | 4 |
| 立体仓库控制 | 仓库管理 | 5 |
| 小车往复3次 | 往复运动 | 3 |
| 8位抢答器 | 抢答器 | 2 |
| 2层电梯 | 电梯控制 | 5 |
| 停车场道闸 | 道闸控制 | 3 |

### 5.3 模板设计思路

- **地址无关**: 模板使用符号名，实际地址由用户分配
- **中文注释**: 接口和网络注释用中文
- **由简到繁**: 从单键启停到立体仓库，逐步复杂
- **可组合**: 复杂模板由简单模式组合而成

---

## 6. Prompt 工程经验

### 6.1 有效的 Prompt 结构

```markdown
你是一名西门子PLC工程师。
请生成[功能]控制程序。

要求：
- 使用SCL语言
- [功能要求1]
- [功能要求2]
- 包含急停输入
- 包含启动/停止按钮

请生成完整的FB块，包含变量声明和逻辑代码。
```

### 6.2 关键发现

1. **明确说"使用SCL语言"** — 否则 LLM 会选 LAD
2. **要求"完整的FB块"** — LLM 会输出完整可粘贴代码
3. **匈牙利命名法** — 需要显式要求，默认 LLM 用驼峰
4. **安全编程原则** — 必须强调"互锁/急停/故障处理"
5. **变量模板** — 用 `{variable}` 占位符 + 默认值，用户可调

### 6.3 分类策略

| 分类 | 模板数 | 说明 |
|------|--------|------|
| 顺序控制 | 5 | 交通灯/包装机/步进/CIP/停车场 |
| 运动控制 | 3 | 电机正反转/电梯/立体仓库 |
| 过程控制 | 7 | PID/水泵/冷却塔/SBR/空调/VAV/冷站 |
| 通信 | 2 | Modbus/AGV |
| 信号处理 | 1 | 模拟量 |
| 系统功能 | 1 | 报警管理 |
| 辅助工具 | 2 | 代码解释/IO表生成 |

---

## 7. 已知 Bug

### B-001: 知识库文件名显示 tmp_xxx
- **状态**: ✅ 已修复（引擎传递 original_filename 参数）
- **根因**: `tempfile.NamedTemporaryFile` 生成临时文件名，导入时用临时名作为文档名
- **修复**: `engine.py` 和 `parsers.py` 增加 `original_filename` 参数

### B-002: ChromDB 路径混淆
- **状态**: ⚠️ 已纠正但容易再次踩坑
- **正确路径**: `data/vector_db`
- **常见错误**: 以为是 `data/chroma_db`

### B-003: 版本号不一致
- **状态**: ⚠️ 未修复
- **现象**: 前端 `package.json = 1.0.0`，后端 `main.py = 0.1.0`

### B-004: 梯形图SCL转换很弱
- **状态**: ⚠️ 已知
- **现象**: `_ladder_to_scl()` 函数只能处理最简单串联触点和线圈
- **建议**: SCL 代码应由 LLM 直接生成，不走后处理转换

### B-005: LLM 回退不通知用户
- **状态**: ⚠️ 已知
- **现象**: DeepSeek 不可用自动切到其他模型，用户看不到切换信息
- **修复**: 后端 SSE 返回 `model` 字段，前端展示切换提示

### B-006: 前端全量在 App.jsx
- **状态**: ✅ 已重构（提取 5 个 custom hooks）
- **原来**: 306 行的 App.jsx 包含所有状态管理
- **现在**: 115 行，仅负责编排

---

## 8. 后续优化方向

### 8.1 短期（V1.0 正式版前）

1. **SVG 梯形图可视化** — 最重要的 UX 改进
2. **Electron 打包测试** — 确保可分发
3. **后端 pytest** — 敢重构的前提
4. **版本号统一** — 小改但影响用户体验

### 8.2 中期（V1.x）

1. **RAG 中文检索升级** — bge-m3 嵌入模型
2. **工程搜索中文分词** — jieba + FTS5 自定义 tokenize
3. **多轮 RAG 对话** — 支持"追问"
4. **Playwright E2E** — 发布质量保障
5. **代码 Diff 视图** — 可视化 AI 修改

### 8.3 长期（V2.0）

1. **AI Agent 直连 PLC** — 运行态控制 + 监控 + 异常处理
2. **多 Agent 编排** — 复杂任务拆解
3. **TIA Openness 深度集成** — AI 直接写入 TIA Portal
4. **RBAC 权限** — 多用户支持
5. **团队协作** — 共享知识库、模板市场

---

## 9. 联系与背景

- **项目维护**: @yihefeixong-rgb
- **技术栈**: Python 3.13 + FastAPI + React + Electron + ChromaDB + SQLite
- **硬件环境**: Windows 11, TIA Portal V21, PLCSIM Advanced V8.0
- **开发周期**: Phase 1-3 约 3 周，AI PLC Assistant 约 2 周
