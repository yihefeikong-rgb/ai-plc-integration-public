# ASCII-LAD-V2 规范

> 版本: 2.1.0  
> 状态: **草稿**  
> 用途: AI 生成梯形图程序的标准化中间表示语言  
> 设计原则: 可解析、可渲染、可导出、可训练

---

## 目录

1. [概述](#1-概述)
2. [文件结构](#2-文件结构)
3. [变量表](#3-变量表)
4. [Network 结构](#4-network-结构)
5. [元素语法](#5-元素语法)
6. [Branch 标准](#6-branch-标准)
7. [完整示例](#7-完整示例)
8. [语法速查表](#8-语法速查表)
9. [V2 范围与限制](#9-v2-范围与限制)

---

## 1. 概述

### 1.1 什么是 ASCII-LAD-V2

ASCII-LAD-V2 是一种纯文本格式，用于表示 IEC 61131-3 梯形图（Ladder Diagram）程序。
它是 AI 与渲染层之间的**中间表示**，不是显示格式，不是存储格式，不是导出格式。

```
AI (LLM)
  │ 生成 ASCII-LAD-V2 文本
  ▼
ASCII-LAD-V2
  │ Parser 解析为结构化 LadderModel
  ▼
LadderModel (内存对象)
  ├──→ 前端 React 渲染
  ├──→ 导出 SCL/XML
  └──→ 将来导出 SVG/PDF
```

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| 可解析 | 严格语法，一行正则或一个状态机即可解析 |
| 可渲染 | 包含坐标所需全部信息，前端直接渲染 |
| 可导出 | 可无损映射到 SCL/PLCopen XML/TIA |
| 可训练 | LLM 能学会的有限语法，不自由发挥 |

### 1.3 非目标（V2 不做）

- 不直接渲染 SVG（Parser → LadderModel → 渲染器）
- 不支持嵌套 Branch（仅单层 Branch）
- 不定义物理布局坐标（那是渲染器的事）
- 不处理中文变量名（变量名统一用英文/匈牙利命名法）

---

## 2. 文件结构

### 2.1 文件头

每个 ASCII-LAD-V2 文件必须以版本声明开头：

```
ASCII-LAD-V2
```

后续版本升级时：

```
ASCII-LAD-V2.1
ASCII-LAD-V3
```

解析器根据版本号决定兼容性。

### 2.2 整体结构

```
ASCII-LAD-V2                             ← 版本头

Variables:                               ← 变量表（可选）
I0.0    Start    BOOL
I0.1    Stop     BOOL
Q0.0    Motor    BOOL

Network 1                                ← Network
Title: 电机启动自锁                       ← 标题（可选）

Comment:                                 ← 注释（可选）
启动后保持运行直到按下停止按钮

|----[ Start ]----[/ Stop ]----( Motor )

Network 2
Title: 运行指示

|----[ Motor ]----( Q0.1 Lamp )
```

---

## 3. 变量表

### 3.1 格式

```
Variables:

<地址>    <符号名>    <数据类型>    [注释]
```

每行三个字段，空格/制表符分隔：

| 字段 | 必填 | 说明 |
|------|------|------|
| 地址 | 是 | PLC 地址，如 I0.0, Q0.0, M0.0, MW10, DB1.DBW0 |
| 符号名 | 是 | 匈牙利命名法（bStart, qMotor, rSpeed） |
| 数据类型 | 是 | BOOL, BYTE, WORD, DWORD, INT, DINT, REAL, TIME, STRING |
| 注释 | 否 | 中文注释 |

### 3.2 示例

```
Variables:
I0.0    bStart     BOOL    启动按钮
I0.1    bStop      BOOL    停止按钮
I0.2    bEStop     BOOL    急停按钮
Q0.0    qMotor     BOOL    电机输出
MW10    iCounter   INT     当前计数值
```

### 3.3 规则

- **禁止**自然语言变量描述（如"电机启动按钮"代替符号名）
- **禁止**无地址声明（所有变量必须关联地址）
- **推荐**匈牙利命名法前缀

### 3.4 变量命名约定

| 前缀 | 适用范围 | 示例 |
|------|---------|------|
| `b` | 内部 BOOL（M 区） | `bFault`, `bRun` |
| `q` | 物理输出（Q 区） | `qMotor`, `qLamp` |
| `i` / `n` | INT 类型 | `iCounter`, `nStep` |
| `r` | REAL 类型 | `rSpeed`, `rTemp` |
| `t` | 定时器实例 | `tonDelay`, `tofCool` |
| `c` | 计数器实例 | `ctuBatch`, `ctdParts` |

**注意**：内部运行标志应使用 `M` 区地址 + `b` 前缀（如 `M0.0 bRun`），
不应使用 `Q` 区地址（`Q` 仅用于物理输出）。

---

## 4. Network 结构

### 4.1 格式

```
Network <编号>
Title: <标题>

Comment:
<注释文本>

<梯形图内容>
```

| 部分 | 必填 | 说明 |
|------|------|------|
| `Network <编号>` | 是 | 编号从 1 开始递增 |
| `Title:` | 否 | 该网络的功能描述 |
| `Comment:` | 否 | 多行注释（到下一个 Network 或文件尾结束） |
| 梯形图内容 | 是 | 由元素和导线构成的电路图 |

### 4.2 规则

- Network 编号必须从 1 开始连续递增
- 每个 Network 至少包含一行梯形图
- Title 和 Comment 不得包含空白行
- 两个 Network 之间必须有空白行分隔

### 4.3 示例

```
Network 1
Title: 电机启动自锁

Comment:
当按下启动按钮时电机启动
按下停止按钮或急停时停止
防抖处理：200ms 延时

|----[ bStart ]----[ bStop ]----( qMotor )

Network 2
Title: 运行指示

Comment:
电机运行时点亮运行指示灯

|----[ qMotor ]----( qLamp )
```

---

## 5. 元素语法

### 5.1 常开触点 (Normally Open)

```
[ <操作数> ]
```

| 部分 | 说明 |
|------|------|
| `[` | 左边界，必须 |
| 空格 | 左边界后必须有空格 |
| 操作数 | 符号名或地址 |
| 空格 | 操作数后必须有空格 |
| `]` | 右边界，必须 |

示例：

```
[ bStart ]
[ qMotor ]
[ I0.0 ]
```

### 5.2 常闭触点 (Normally Closed)

```
[/ <操作数> ]
```

| 部分 | 说明 |
|------|------|
| `[/` | 左边界（斜杠紧贴左括号） |
| 空格 | 必须 |
| 操作数 | 符号名或地址 |
| 空格 | 必须 |
| `]` | 右边界 |

示例：

```
[/ bStop ]
[/ bEStop ]
[/ M0.0 ]
```

### 5.3 线圈 (Coil)

```
( <操作数> )
```

| 部分 | 说明 |
|------|------|
| `(` | 左边界 |
| 空格 | 必须 |
| 操作数 | 符号名或地址 |
| 空格 | 必须 |
| `)` | 右边界 |

示例：

```
( qMotor )
( I0.0 )    ← 允许，但不推荐（线圈通常接输出）
```

### 5.4 置位线圈 (Set Coil)

```
(S <操作数>)
```

| 部分 | 说明 |
|------|------|
| `(S` | 左边界 |
| 空格 | 必须 |
| 操作数 | 符号名 |
| `)` | 右边界 |

示例：

```
(S qLatch)
```

### 5.5 复位线圈 (Reset Coil)

```
(R <操作数>)
```

| 部分 | 说明 |
|------|------|
| `(R` | 左边界 |
| 空格 | 必须 |
| 操作数 | 符号名 |
| `)` | 右边界 |

示例：

```
(R qLatch)
```

### 5.6 TON 定时器

```
[TON <名称> PT=<时长>]
```

| 部分 | 说明 |
|------|------|
| `[TON` | 左边界 |
| 空格 | 必须 |
| 名称 | 定时器名称 |
| 空格 | 必须 |
| PT= | 预设时间前缀 |
| 时长 | 数字 + 单位（s/ms） |
| `]` | 右边界 |

单位：`s` = 秒，`ms` = 毫秒

示例：

```
[TON T1 PT=5s]
[TON T2 PT=500ms]
```

语义：当 TON 的梯级为 TRUE 时开始计时，计时达到 PT 后输出变为 TRUE。

### 5.7 TOF 定时器

```
[TOF <名称> PT=<时长>]
```

示例：

```
[TOF T1 PT=3s]
```

语义：当 TOF 的梯级从 TRUE 变为 FALSE 时开始计时，计时达到 PT 后输出变为 FALSE。

### 5.8 TP 脉冲定时器

```
[TP <名称> PT=<时长>]
```

示例：

```
[TP T1 PT=1s]
```

语义：当 TP 的梯级从 FALSE 变为 TRUE 时输出一个持续 PT 时长的脉冲。

### 5.9 CTU 加计数器

```
[CTU <名称> PV=<预设值>]
```

示例：

```
[CTU C1 PV=10]
```

语义：每次梯级从 FALSE 变为 TRUE 时计数值加 1，达到 PV 时输出为 TRUE。

### 5.10 CTD 减计数器

```
[CTD <名称> PV=<预设值>]
```

示例：

```
[CTD C1 PV=5]
```

语义：每次梯级从 FALSE 变为 TRUE 时计数值减 1，达到 0 时输出为 TRUE。

### 5.11 MOVE 赋值

```
[MOVE IN=<源> OUT=<目标>]
```

| 部分 | 说明 |
|------|------|
| `[MOVE` | 左边界 |
| `IN=` | 源参数前缀 |
| 源 | 源变量或立即数 |
| 空格 | 分隔 |
| `OUT=` | 目标参数前缀 |
| 目标 | 目标变量 |
| `]` | 右边界 |

示例：

```
[MOVE IN=Speed OUT=MotorSpeed]
[MOVE IN=0 OUT=wCounterCV]
```

> V2.1 变更：从 `[MOVE src -> dst]` 改为 `[MOVE IN=src OUT=dst]`，
> 与 TON/CTU 的 `KEY=VALUE` 风格统一，简化 Parser。

### 5.12 比较器

```
[CMP <操作> <A> <B>]
```

比较操作枚举：

| 操作 | 含义 |
|------|------|
| EQ | A == B |
| NE | A <> B |
| GT | A > B |
| GE | A >= B |
| LT | A < B |
| LE | A <= B |

示例：

```
[CMP GT iCounter 10]
[CMP EQ iMode 3]
[CMP LE rTemp 100.0]
```

### 5.13 功能块调用

FB 调用：

```
[FB <名称>]
```

FC 调用：

```
[FC <名称>]
```

示例：

```
[FB MotorCtrl]
[FC CalculateSpeed]
```

> V2 限制：FB/FC 调用不带参数映射。参数传递在 V3 中定义。

### 5.14 水平导线

```
----
```

四个 ASCII 短横线，表示元素之间的电气连接。

### 5.15 左电源轨

```
|----
```

竖线表示左电源轨（L+），紧跟 `----` 引出到第一个元素。

### 5.16 功能块输出映射

TON/TOF/TP/CTU/CTD 在梯级中是**内联功能块**。它们的输出隐含在梯级流中：

- 梯级中 `[TON T1 PT=5s]` 之后的元素接收的是 **T1.Q**（定时完成信号）
- 梯级中 `[CTU C1 PV=10]` 之后的元素接收的是 **C1.Q**（计数到达信号）

如果其他 Network 需要引用这些输出，必须在 Variables 中显式声明映射变量：

```
Variables:
T1      tonDelay   TON     启动延时
M0.2    bT1Q       BOOL    T1.Q 定时器输出
C1      ctuBatch   CTU     批次计数器
M0.3    bC1Q       BOOL    C1.Q 计数到达
MW10    wC1CV      INT     C1.CV 当前计数值
```

**隐式输出表**：

| 功能块 | 输出 | 含义 | 推荐变量名 |
|--------|------|------|-----------|
| TON | Q | 定时完成 | `bT1Q` |
| TON | ET | 已计时间 | `tT1ET` |
| TOF | Q | 延时中 | `bT1Q` |
| TOF | ET | 已计时间 | `tT1ET` |
| TP | Q | 脉冲输出 | `bT1Q` |
| TP | ET | 已计时间 | `tT1ET` |
| CTU | Q | 计数到达 | `bC1Q` |
| CTU | CV | 当前值 | `wC1CV` |
| CTD | Q | 计数到零 | `bC1Q` |
| CTD | CV | 当前值 | `wC1CV` |

> 规则：同一 Network 中 `[TON T1 PT=5s]----( qOutput )` 无需声明 Q 变量——
> Q 的值隐式传递给下游元素。仅跨 Network 引用时才需要声明。

---

## 6. Branch 标准

### 6.1 基本格式

Branch 用于表示并联电路（或逻辑）。

```
|----[ A ]----+----( Out )
|             |
|----[ B ]----+
```

| 符号 | 含义 |
|------|------|
| `----` | 水平导线 |
| `+` | Branch 连接点（三通/四通接头） |
| `|` | 竖向导线（Branch 路径） |
| 空格 | Branch 行中左电源轨和 `+` 之间填充空格对齐 |

### 6.2 对齐规则

**核心规则：两个 `+` 必须在同一列。**

```
|----[ A ]----+----( Out )
|             |
|----[ B ]----+
```

- 主路径上的 `+`（第 1 行）和分支路径上的 `+`（第 3 行）**必须垂直对齐**
- 分支路径以 `|`（与左电源轨对齐）开头，以 `+`（与主路径 `+` 对齐）结尾

### 6.3 多输入 Branch （最多 3 路）

```
|----[ A ]----+----( Out )
|             |
|----[ B ]----+
|             |
|----[ C ]----+
```

### 6.4 单元素 Branch

```
|----[ A ]----+----( Out1 )
|             |
|----+-------( Out2 )
```

### 6.5 规则

✅ 支持 | V2 范围 |
| 并联（或逻辑） | 单层 Branch |
| 2 ~ 3 个并行支路 | 每路一个或多个串联元素 |

❌ 不支持 | 理由 |
| 嵌套 Branch（Branch 中的 Branch） | V2 有限范围，覆盖 80% 工业场景 |
| 多于 3 路分支 | 过度复杂，需要时拆多个 Network |

### 6.6 非法格式示例

这些格式解析器应报错：

```
# 错误：+ 未对齐
|----[ A ]----+----( Out )
|                |
|----[ B ]------+

# 错误：嵌套 Branch（V2 不支持）
|----[ A ]----+----[ B ]----+----( Out )
|             |             |
|             |----[ C ]----+
|
|----[ D ]------------------+

# 错误：非标准分隔符
+--[ A ]--+
```

---

## 7. 完整示例

### 7.1 电机启动自锁（最简）

```
ASCII-LAD-V2

Variables:
I0.0    bStart     BOOL    启动按钮
I0.1    bStop      BOOL    停止按钮
Q0.0    qMotor     BOOL    电机输出

Network 1
Title: 电机启动自锁

|----[ bStart ]----[/ bStop ]----+----( qMotor )
|                                |
|----[ qMotor ]------------------+
```

### 7.2 电机正反转（带互锁）

```
ASCII-LAD-V2

Variables:
I0.0    bFwd       BOOL    正转按钮
I0.1    bRev       BOOL    反转按钮
I0.2    bStop      BOOL    停止按钮
I0.3    bOL        BOOL    过载保护
Q0.0    qFwd       BOOL    正转接触器
Q0.1    qRev       BOOL    反转接触器

Network 1
Title: 正转启动（互锁反转）

|----[ bFwd ]----[/ bRev ]----[/ bStop ]----[/ bOL ]----( qFwd )
|                                                                  
|----[ qFwd ]-------------------------------------------+

Network 2
Title: 反转启动（互锁正转）

|----[ bRev ]----[/ bFwd ]----[/ bStop ]----[/ bOL ]----( qRev )
|                                                                  
|----[ qRev ]-------------------------------------------+
```

### 7.3 定时器延时启动

```
ASCII-LAD-V2

Variables:
I0.0    bStart     BOOL    启动
I0.1    bStop      BOOL    停止
Q0.0    qMotor     BOOL    电机输出
T1      tonDelay   TON     启动延时

Network 1
Title: 延时 5 秒启动

|----[ bStart ]----[/ bStop ]----[TON T1 PT=5s]----( qMotor )
```

### 7.4 计数器批次控制

```
ASCII-LAD-V2

Variables:
I0.0    bSensor    BOOL    产品检测传感器
I0.1    bReset     BOOL    计数器复位
Q0.0    qBoxReady  BOOL    装箱完成
C1      ctuProd    CTU     产品计数器

Network 1
Title: 产品计数（每满 100 输出）

|----[ bSensor ]----[CTU C1 PV=100]----( qBoxReady )
```

---

## 8. 语法速查表

### 8.1 元素速查

| 类型 | 语法 | 示例 |
|------|------|------|
| 常开触点 | `[ 操作数 ]` | `[ bStart ]` |
| 常闭触点 | `[/ 操作数 ]` | `[/ bStop ]` |
| 线圈 | `( 操作数 )` | `( qMotor )` |
| 置位线圈 | `(S 操作数)` | `(S qLatch)` |
| 复位线圈 | `(R 操作数)` | `(R qLatch)` |
| TON 定时器 | `[TON 名 PT=时长]` | `[TON T1 PT=5s]` |
| TOF 定时器 | `[TOF 名 PT=时长]` | `[TOF T1 PT=3s]` |
| TP 脉冲 | `[TP 名 PT=时长]` | `[TP T1 PT=1s]` |
| CTU 加计数 | `[CTU 名 PV=值]` | `[CTU C1 PV=10]` |
| CTD 减计数 | `[CTD 名 PV=值]` | `[CTD C1 PV=5]` |
| MOVE | `[MOVE IN=源 OUT=目标]` | `[MOVE IN=Speed OUT=Setpoint]` |
| 比较器 | `[CMP 操作 A B]` | `[CMP GT iCounter 10]` |
| FB 调用 | `[FB 名]` | `[FB MotorCtrl]` |
| FC 调用 | `[FC 名]` | `[FC Calculate]` |

### 8.2 导线速查

| 符号 | 含义 |
|------|------|
| `----` | 水平导线（4 个短横） |
| `|` | 左电源轨 / 竖向导轨 |
| `+` | Branch 连接点 |

### 8.3 结构速查

```
ASCII-LAD-V2                    ← 文件头（必填，第 1 行）

Variables:                      ← 变量区（可选）
地址    符号名    数据类型

Network <n>                     ← Network（必填，可多个）
Title: <标题>                   ← 标题（可选）

Comment:                        ← 注释（可选）
<注释文本>

|----<元素>----<元素>----<元素>  ← 梯形图内容（必填）
```

---

## 9. V2 范围与限制

### 9.1 V2 覆盖的工业场景（80%）

| 类型 | 覆盖场景 |
|------|---------|
| 基本逻辑 | 与、或、非、自锁、互锁 |
| 启停控制 | 电机、泵、风机、阀门 |
| 定时控制 | 延时启动/停止、脉冲 |
| 计数控制 | 产品计数、批次控制 |
| 比较逻辑 | 限值比较、模式判断 |
| 赋值操作 | 变量赋值、参数写入 |
| 简单过程 | 单层 Branch 的并行条件 |

### 9.2 V2 不支持（V3+）

| 特性 | 原因 |
|------|------|
| 嵌套 Branch | 复杂度高，使用场景不到 20% |
| 多行元素（如定时器方框展开） | V2 统一为单行 `[TON ...]` |
| 物理坐标信息 | 那是渲染器的工作 |
| FB/FC 参数映射 | V3 定义参数传递语法 |
| 数组/结构体访问 | V3 定义 |
| EN/ENO 连接 | V3 定义 |
| 跳转/标签 | 梯形图中不常用 |

### 9.3 解析原则

1. **逐行解析**：状态机按行读取，当前行决定解析状态
2. **容错策略**：遇到无法解析的 Network，跳过并记警告，不阻塞后续
3. **验证点**：
   - 文件头是否为 `ASCII-LAD-V2`
   - Network 编号是否连续
   - 元素语法是否正确（括号匹配、操作数非空）
   - Branch `+` 是否垂直对齐
   - 变量表字段数是否 >= 3

---

## 附录 A: 语法 BNF（简化）

```
program         ::= header vars_section network+
header          ::= "ASCII-LAD-V2"
vars_section    ::= "Variables:" NEWLINE variable*
variable        ::= ADDRESS SYMBOL DATATYPE [COMMENT] NEWLINE
network         ::= "Network" NUMBER NEWLINE
                    [title]
                    [comment]
                    rung+
title           ::= "Title:" TEXT NEWLINE
comment         ::= "Comment:" NEWLINE TEXT*
rung            ::= "|----" element_list NEWLINE
                    [branch_lines]
element_list    ::= element ("----" element)*
element         ::= contact | coil | timer | counter | move | comparator | fc_call
contact         ::= "[" [ "/" ] SPACE OPERAND SPACE "]"
coil            ::= "(" ["S" | "R"] SPACE OPERAND ")"
timer           ::= "[TON" | "[TOF" | "[TP" SPACE NAME SPACE "PT=" DURATION "]"
counter         ::= "[CTU" | "[CTD" SPACE NAME SPACE "PV=" NUMBER "]"
move            ::= "[MOVE" SPACE "IN=" OPERAND SPACE "OUT=" OPERAND "]"
comparator      ::= "[CMP" SPACE COMP_OP SPACE OPERAND SPACE OPERAND "]"
fc_call         ::= "[" ("FB" | "FC") SPACE NAME "]"
branch_lines    ::= "|" SPACE* "|" SPACE* "----" element_list "----+" NEWLINE
```

---

## 附录 B: 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0.0 | 2026-06-18 | 初始规范定义 |
| 2.1.0 | 2026-06-18 | MOVE 语法改为 IN=/OUT=；新增功能块输出映射（5.16）；变量命名约定（3.4） |
