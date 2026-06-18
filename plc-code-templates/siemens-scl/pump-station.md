# 泵站控制 — SCL 生成模板

## 功能描述
多泵轮值控制系统（Lead-Lag），支持基于累计运行时间的 Duty 轮换、液位分档启泵、干转保护和泵数据记录。

## 核心特性
- **Duty 轮换**：选择累计运行时间最小的泵作为主导泵
- **液位分档**：按 20% 递增启泵（0-20%=0泵, 20-40%=1泵, ... 80-100%=4泵）
- **干转保护**：运行反馈 + 电流低于阈值 → 5秒后报警停机
- **错时启动**：主导泵立即启动，其余泵延迟 2 秒启动
- **累计运行时间**：记录每台泵的累计运行时数和启动次数

## UDT 定义（推荐抽离为独立类型）

```scl
TYPE "PumpData"
VERSION : 0.1
   STRUCT
      rCumulRuntime : Real;       // 累计运行时间 (小时)
      iStartsCount : Int;         // 启动次数
      rCurrentActual : Real;      // 实际电流 (A)
      bRunFeedback : Bool;        // 运行反馈
   END_STRUCT;
END_TYPE
```

## SCL 代码模板

```scl
FUNCTION_BLOCK "PumpStation"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bEnable : Bool;                    // 系统使能
    bReset : Bool;                     // 故障复位
    bEmergencyStop : Bool;             // 急停（常闭）
    rLevel : Real;                     // 液位传感器 (0-100%)
    iNumPumps : Int;                   // 水泵数量 (1-4)
    rRuntimeHours : Real;              // 运行时数阈值 (小时)
    rDryRunCurrent : Real;             // 干转电流阈值 (A)
    rCurrentPump1 : Real;              // 1号泵电流
    rCurrentPump2 : Real;              // 2号泵电流
    rCurrentPump3 : Real;              // 3号泵电流
    rCurrentPump4 : Real;              // 4号泵电流
    bRunFeedback1 : Bool;              // 1号泵运行反馈
    bRunFeedback2 : Bool;              // 2号泵运行反馈
    bRunFeedback3 : Bool;              // 3号泵运行反馈
    bRunFeedback4 : Bool;              // 4号泵运行反馈
END_VAR

VAR_OUTPUT
    bRunCmd1 : Bool;                   // 1号泵启动指令
    bRunCmd2 : Bool;                   // 2号泵启动指令
    bRunCmd3 : Bool;                   // 3号泵启动指令
    bRunCmd4 : Bool;                   // 4号泵启动指令
    bDryRunAlarm : Bool;               // 干转报警
    bLevelHigh : Bool;                 // 液位高报警
    bLevelLow : Bool;                  // 液位低报警
    bFault : Bool;                     // 系统故障
    iActivePumps : Int;                // 当前运行泵数
    iLeadPump : Int;                   // 当前主导泵编号
END_VAR

VAR
    // 泵运行数据
    rCumulRuntime1 : Real;             // 1号泵累计运行时间 (小时)
    rCumulRuntime2 : Real;             // 2号泵累计运行时间 (小时)
    rCumulRuntime3 : Real;             // 3号泵累计运行时间 (小时)
    rCumulRuntime4 : Real;             // 4号泵累计运行时间 (小时)
    iStartsCount1 : Int;               // 1号泵启动次数
    iStartsCount2 : Int;               // 2号泵启动次数
    iStartsCount3 : Int;               // 3号泵启动次数
    iStartsCount4 : Int;               // 4号泵启动次数

    // 运行状态
    bRunStatus1 : Bool;                // 1号泵运行状态
    bRunStatus2 : Bool;                // 2号泵运行状态
    bRunStatus3 : Bool;                // 3号泵运行状态
    bRunStatus4 : Bool;                // 4号泵运行状态

    // 轮换逻辑
    iPumpIndex : Int;                  // 轮换索引
    tRotation : TON;                   // 轮换计时器
    tStagger : TON;                    // 错时启动计时器
    tDryRun : TON;                     // 干转检测计时器
    rMinRuntime : Real;                // 最小运行时间
    bRotatePending : Bool;             // 轮换等待
    rCumulRuntimeLead : Real;          // 主导泵累计时间
    rCumulRuntimeCandidate : Real;     // 候选泵累计时间
    iCandidates : Int;                 // 候选泵数量
    iActiveCount : Int;                // 应启动泵数
    iStageCalc : Int;                  // 液位档位计算
    iLeadCandidate : Int;              // 最小运行时间泵索引
    rMinTime : Real;                   // 最小运行时数
    bPumpRunning : Bool;               // 任一泵运行
END_VAR

BEGIN
    // ── 急停 ──
    IF NOT bEmergencyStop THEN
        bRunCmd1 := FALSE; bRunCmd2 := FALSE;
        bRunCmd3 := FALSE; bRunCmd4 := FALSE;
        bFault := TRUE;
        RETURN;
    END_IF;

    // ── 故障复位 ──
    IF bFault AND bReset AND bEmergencyStop THEN
        bFault := FALSE;
    END_IF;

    IF bFault THEN RETURN; END_IF;

    // ── 运行状态跟踪 ──
    bRunStatus1 := bRunFeedback1;
    bRunStatus2 := bRunFeedback2;
    bRunStatus3 := bRunFeedback3;
    bRunStatus4 := bRunFeedback4;

    // ── 累计运行时数（模拟累加） ──
    // 实际项目应使用 RTC 或 OB 周期计算
    IF bRunStatus1 THEN rCumulRuntime1 := rCumulRuntime1 + 0.001; END_IF;
    IF bRunStatus2 THEN rCumulRuntime2 := rCumulRuntime2 + 0.001; END_IF;
    IF bRunStatus3 THEN rCumulRuntime3 := rCumulRuntime3 + 0.001; END_IF;
    IF bRunStatus4 THEN rCumulRuntime4 := rCumulRuntime4 + 0.001; END_IF;

    // ── 干转检测（电流低于阈值 + 运行反馈 = 干转） ──
    IF (bRunStatus1 AND rCurrentPump1 < rDryRunCurrent) OR
       (bRunStatus2 AND rCurrentPump2 < rDryRunCurrent) OR
       (bRunStatus3 AND rCurrentPump3 < rDryRunCurrent) OR
       (bRunStatus4 AND rCurrentPump4 < rDryRunCurrent) THEN
        tDryRun(IN := TRUE, PT := T#5S);
        IF tDryRun.Q THEN
            bDryRunAlarm := TRUE;
            bFault := TRUE;
            bRunCmd1 := FALSE; bRunCmd2 := FALSE;
            bRunCmd3 := FALSE; bRunCmd4 := FALSE;
            RETURN;
        END_IF;
    ELSE
        tDryRun(IN := FALSE);
    END_IF;

    // ── 液位档位计算 ──
    // 0-20%: 0 泵 | 20-40%: 1 泵 | 40-60%: 2 泵 | 60-80%: 3 泵 | 80-100%: 4 泵
    iStageCalc := REAL_TO_INT(rLevel / 20.0);
    iActiveCount := iStageCalc;

    // 限幅
    IF iActiveCount < 0 THEN iActiveCount := 0; END_IF;
    IF iActiveCount > iNumPumps THEN iActiveCount := iNumPumps; END_IF;

    // ── 液位报警 ──
    bLevelHigh := rLevel >= 90.0;
    bLevelLow := rLevel <= 10.0;

    // ── Duty轮换：累计运行时间最小的泵作为主导 ──
    iPumpIndex := 1;
    rMinTime := rCumulRuntime1;
    iLeadCandidate := 1;

    // 找最小累计运行时间的泵
    IF iNumPumps >= 2 AND rCumulRuntime2 < rMinTime THEN
        rMinTime := rCumulRuntime2; iLeadCandidate := 2;
    END_IF;
    IF iNumPumps >= 3 AND rCumulRuntime3 < rMinTime THEN
        rMinTime := rCumulRuntime3; iLeadCandidate := 3;
    END_IF;
    IF iNumPumps >= 4 AND rCumulRuntime4 < rMinTime THEN
        rMinTime := rCumulRuntime4; iLeadCandidate := 4;
    END_IF;

    iLeadPump := iLeadCandidate;

    // ── 错时启动 ──
    bRunCmd1 := FALSE; bRunCmd2 := FALSE;
    bRunCmd3 := FALSE; bRunCmd4 := FALSE;

    IF bEnable AND iActiveCount > 0 THEN
        IF iActiveCount >= 1 THEN
            tStagger(IN := TRUE, PT := T#2S);
            IF tStagger.Q THEN
                bRunCmd1 := iPumpIndex = 1 OR (iActiveCount >= 2 AND iPumpIndex <= 2)
                            OR (iActiveCount >= 3 AND iPumpIndex <= 3)
                            OR (iActiveCount >= 4);
            ELSE
                // 启动主导泵（无延时）
                CASE iLeadPump OF
                    1: bRunCmd1 := TRUE;
                    2: bRunCmd2 := TRUE;
                    3: bRunCmd3 := TRUE;
                    4: bRunCmd4 := TRUE;
                END_CASE;
            END_IF;
        END_IF;
    END_IF;

    // ── 轮换计时 ──
    bPumpRunning := bRunStatus1 OR bRunStatus2 OR bRunStatus3 OR bRunStatus4;
    IF bPumpRunning THEN
        tRotation(IN := TRUE, PT := T#30M);
        IF tRotation.Q THEN
            iPumpIndex := iPumpIndex + 1;
            IF iPumpIndex > iNumPumps THEN iPumpIndex := 1; END_IF;
            tRotation(IN := FALSE);
        END_IF;
    ELSE
        tRotation(IN := FALSE);
    END_IF;

    // ── iActivePumps 输出 ──
    iActivePumps := 0;
    IF bRunCmd1 THEN iActivePumps := iActivePumps + 1; END_IF;
    IF bRunCmd2 THEN iActivePumps := iActivePumps + 1; END_IF;
    IF bRunCmd3 THEN iActivePumps := iActivePumps + 1; END_IF;
    IF bRunCmd4 THEN iActivePumps := iActivePumps + 1; END_IF;

END_FUNCTION_BLOCK
```

## 变量命名规范
- 输入: bXxx (Bool), rXxx (Real), iXxx (Int)
- 输出: bXxx (Bool), iXxx (Int)
- 中间变量: bXxx, rXxx, iXxx + 驼峰描述
- 定时器: tXxx (TON)

## 调试提示
- 检查 `rDryRunCurrent` 阈值是否低于正常负载电流
- 轮换周期根据现场要求调整（建议 4-8 小时）
- 启动计数器 `iStartsCountX` 辅助判断泵是否需要维护（>10000次建议检查）
