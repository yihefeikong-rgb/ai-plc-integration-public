# SBR 污水处理 — SCL 生成模板

## 功能描述
序批式反应器（Sequencing Batch Reactor）污水处理工艺控制。五阶段循环：进水 → 曝气 → 沉淀 → 滗水 → 闲置。

## 核心特性
- **五阶段时序控制**：FILL / AERATE / SETTLE / DECANT / IDLE
- **DO 分档曝气**：根据溶解氧浓度自动切换低速/高速/停止
- **参数可配置**：各阶段时长和 DO 阈值通过 DB 在线调整
- **液位联锁**：高液位终止进水，低液位终止滗水
- **周期计数**：记录处理循环次数

## 工艺时序

```
    FILL    AERATE    SETTLE    DECANT    IDLE
   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
   │进水  │ │曝气  │ │沉淀  │ │滗水  │ │闲置  │
   │1H    │ │2H    │ │1H    │ │1H    │ │30M   │
   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
      │        │        │        │        │
      └────────┴────────┴────────┴────────┘
                   循环重复
```

## SCL 代码模板

```scl
FUNCTION_BLOCK "SBRProcess"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bStart : Bool;                     // 启动处理循环
    bStop : Bool;                      // 停止
    bReset : Bool;                     // 故障复位
    bEmergencyStop : Bool;             // 急停（常闭）
    rLevel : Real;                     // 液位 (0-100%)
    rDIConcentration : Real;           // DO 溶解氧浓度 (mg/L)
    bHighLevel : Bool;                 // 高液位开关
    bLowLevel : Bool;                  // 低液位开关
    bDecantValveOpen : Bool;           // 滗水器阀开反馈
    bDecantValveClosed : Bool;         // 滗水器阀关反馈
END_VAR

VAR_OUTPUT
    bInletValve : Bool;                // 进水阀
    bAeratorLow : Bool;                // 曝气低速
    bAeratorHigh : Bool;               // 曝气高速
    bDecantValve : Bool;               // 滗水器阀
    bSludgeValve : Bool;               // 排泥阀
    bPhaseActive : Bool;               // 阶段运行中
    bCycleComplete : Bool;             // 循环完成
    bFault : Bool;                     // 故障
    iCurrentPhase : Int;               // 当前阶段编号
    iCycleCount : Int;                 // 运行周期数
    tPhaseRemaining : Time;            // 当前阶段剩余时间
END_VAR

VAR_IN_OUT
    // SBR 工艺参数（可从 DB 配置）
    tFillTime : Time;                  // 进水阶段时长 (默认 T#1H)
    tAerateTime : Time;                // 曝气阶段时长 (默认 T#2H)
    tSettleTime : Time;                // 沉淀阶段时长 (默认 T#1H)
    tDecantTime : Time;                // 滗水阶段时长 (默认 T#1H)
    tIdleTime : Time;                  // 闲置阶段时长 (默认 T#30M)
    rDOSetpoint : Real;                // DO 设定值 (mg/L)
    rAerateLowThreshold : Real;        // 曝气低速 DO 阈值 (mg/L)
END_VAR

VAR
    // 阶段常量
    c_IDLE : Int := 0;
    c_FILL : Int := 1;
    c_AERATE : Int := 2;
    c_SETTLE : Int := 3;
    c_DECANT : Int := 4;

    // 阶段计时器
    tPhaseTimer : TON;                 // 阶段计时
    tAerateTrans : TON;                // 曝气切换延时

    // 阶段预设时间 (秒)
    tFillTimeS : Time;
    tAerateTimeS : Time;
    tSettleTimeS : Time;
    tDecantTimeS : Time;
    tIdleTimeS : Time;

    // 边沿检测
    bStartOld : Bool;
    bStartRising : Bool;

    // DO 控制
    bDOHigh : Bool;                    // DO 高于设定
    bDOLow : Bool;                     // DO 低于设定
    iPhaseState : Int;
END_VAR

BEGIN
    // ── 急停 ──
    IF NOT bEmergencyStop THEN
        bInletValve := FALSE; bAeratorLow := FALSE; bAeratorHigh := FALSE;
        bDecantValve := FALSE; bSludgeValve := FALSE; bPhaseActive := FALSE;
        bFault := TRUE; iCurrentPhase := c_IDLE;
        RETURN;
    END_IF;

    // ── 故障复位 ──
    IF bFault AND bReset THEN
        bFault := FALSE;
    END_IF;

    IF bFault THEN RETURN; END_IF;

    // ── 上升沿检测 ──
    bStartRising := bStart AND NOT bStartOld;
    bStartOld := bStart;

    // ── 停止 ──
    IF bStop AND iCurrentPhase <> c_IDLE THEN
        bInletValve := FALSE; bAeratorLow := FALSE; bAeratorHigh := FALSE;
        bDecantValve := FALSE; bSludgeValve := FALSE;
        bPhaseActive := FALSE; iCurrentPhase := c_IDLE;
        tPhaseTimer(IN := FALSE);
    END_IF;

    // ── 启动 ──
    IF bStartRising AND iCurrentPhase = c_IDLE THEN
        iCurrentPhase := c_FILL;
        bCycleComplete := FALSE;
    END_IF;

    // ── SBR 阶段执行 ──
    iPhaseState := iCurrentPhase;

    CASE iPhaseState OF

        1:  // FILL — 进水阶段
            bInletValve := TRUE; bPhaseActive := TRUE;
            tPhaseTimer(IN := TRUE, PT := tFillTimeS);

            // 达到高液位或计时到则进入曝气
            IF tPhaseTimer.Q OR bHighLevel THEN
                bInletValve := FALSE;
                tPhaseTimer(IN := FALSE);
                iCurrentPhase := c_AERATE;
            END_IF;

        2:  // AERATE — 曝气阶段
            bPhaseActive := TRUE;

            // DO 分档控制
            IF rDIConcentration < rAerateLowThreshold THEN
                bAeratorLow := TRUE; bAeratorHigh := TRUE;    // 高速曝气
            ELSIF rDIConcentration < rDOSetpoint THEN
                bAeratorLow := TRUE; bAeratorHigh := FALSE;   // 低速曝气
            ELSE
                bAeratorLow := FALSE; bAeratorHigh := FALSE;  // 停止曝气
            END_IF;

            tPhaseTimer(IN := TRUE, PT := tAerateTimeS);
            IF tPhaseTimer.Q THEN
                bAeratorLow := FALSE; bAeratorHigh := FALSE;
                tPhaseTimer(IN := FALSE);
                iCurrentPhase := c_SETTLE;
            END_IF;

        3:  // SETTLE — 沉淀阶段
            bPhaseActive := TRUE;
            bAeratorLow := FALSE; bAeratorHigh := FALSE;

            tPhaseTimer(IN := TRUE, PT := tSettleTimeS);
            IF tPhaseTimer.Q THEN
                tPhaseTimer(IN := FALSE);
                iCurrentPhase := c_DECANT;
            END_IF;

        4:  // DECANT — 滗水阶段
            bPhaseActive := TRUE;

            // 低液位到达或滗水器全开反馈
            IF NOT bLowLevel THEN
                bDecantValve := TRUE;
            END_IF;

            tPhaseTimer(IN := TRUE, PT := tDecantTimeS);
            IF tPhaseTimer.Q OR bLowLevel THEN
                bDecantValve := FALSE;
                tPhaseTimer(IN := FALSE);
                iCycleCount := iCycleCount + 1;
                bCycleComplete := TRUE;
                iCurrentPhase := c_IDLE;
            END_IF;

        0:  // IDLE — 闲置
            bInletValve := FALSE; bAeratorLow := FALSE; bAeratorHigh := FALSE;
            bDecantValve := FALSE; bSludgeValve := FALSE; bPhaseActive := FALSE;

    END_CASE;

    // ── 阶段剩余时间计算 ──
    IF tPhaseTimer.IN THEN
        tPhaseRemaining := tPhaseTimer.PT - tPhaseTimer.ET;
    ELSE
        tPhaseRemaining := T#0S;
    END_IF;

END_FUNCTION_BLOCK
```

## 参数配置说明

| 参数 | 典型值 | 说明 |
|------|--------|------|
| tFillTime | T#1H | 进水阶段，根据进水量调整 |
| tAerateTime | T#2H | 曝气阶段，根据 COD 负荷调整 |
| tSettleTime | T#1H | 沉淀阶段，应足够使污泥沉降 |
| tDecantTime | T#1H | 滗水阶段，根据滗水器速度调整 |
| tIdleTime | T#30M | 闲置阶段，可排泥再生 |
| rDOSetpoint | 2.0 mg/L | 目标溶解氧浓度 |
| rAerateLowThreshold | 1.5 mg/L | 低于此值开启高速曝气 |

## 调试建议
- 首次运行先调大各阶段时间，确认时序正常再逐步缩短
- DO 传感器需要定期校准，否则会影响曝气控制
- 滗水器反馈信号建议加入防抖处理（ON 延时 2s）
- 建议在闲置阶段加入排泥控制，根据 MLSS 测定频率自动排泥
