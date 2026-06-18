# 冷却塔控制 — SCL 生成模板

## 功能描述
多风机冷却塔控制系统，支持 VFD 速度调节、多台风机错时分级启停、温度 PID 控制、冷机联锁和安全保护。

## 核心特性
- **温度级联控制**：出水温度 PID 调节 VFD 频率（0-50 Hz）
- **风机错时启动**：4 台风机依次启动，每台间隔 2 分钟
- **冷机联锁**：冷机运行时强制开启循环泵
- **安全保护**：流量开关、系统压力、防冻三重保护
- **自动分级**：VFD 频率分 5 档（0-4 台风机）

## 控制逻辑框图

```
出水温度设定 ──┐
               ├──[PID]── VFD 频率 ── 分级 ── 风机1-4
出水温度实际 ──┘                  │
                                  └── 0-20%: 0台
                                      20-40%: 1台
                                      40-60%: 2台
                                      60-80%: 3台
                                      80-100%: 4台
```

## SCL 代码模板

```scl
FUNCTION_BLOCK "CoolingTower"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bEnable : Bool;                    // 系统使能
    bStop : Bool;                      // 停止
    bReset : Bool;                     // 故障复位
    bEmergencyStop : Bool;             // 急停（常闭）
    rTempReturn : Real;                // 回水温度 (degC)
    rTempSupply : Real;                // 出水温度 (degC)
    rTempOutdoor : Real;               // 室外温度 (degC)
    bFlowSwitch : Bool;                // 水流开关
    bChillerRun : Bool;                // 冷机运行信号
    rPressure : Real;                  // 系统压力 (bar)
    rPressureLow : Real;               // 低压报警阈值 (bar)
    rPressureHigh : Real;              // 高压报警阈值 (bar)
    rVFDActual : Real;                 // VFD 实际频率 (Hz)
END_VAR

VAR_OUTPUT
    bFanRun1 : Bool;                   // 1号风机运行
    bFanRun2 : Bool;                   // 2号风机运行
    bFanRun3 : Bool;                   // 3号风机运行
    bFanRun4 : Bool;                   // 4号风机运行
    rVFDSpeed : Real;                  // VFD 频率设定 (0-50 Hz)
    bPumpRun : Bool;                   // 循环泵运行
    bFlowAlarm : Bool;                 // 流量报警
    bPressureAlarm : Bool;             // 压力报警
    bTempHighAlarm : Bool;             // 高温报警
    bAntiFreezeAlarm : Bool;           // 防冻报警
    bFault : Bool;                     // 系统故障
    iActiveFans : Int;                 // 当前运行风机数
    rTempDiff : Real;                  // 进出水温差
END_VAR

VAR
    // 温度设定
    rTempSetpoint : Real;              // 出水温度设定值 (degC)
    rDiffSetpoint : Real;              // 目标温差 (degC)
    rAntiFreezeTemp : Real;            // 防冻温度 (degC)

    // 风机错时启动
    tFan1Delay : TON;                  // 1号风机启动延时
    tFan2Delay : TON;                  // 2号风机启动延时
    tFan3Delay : TON;                  // 3号风机启动延时
    tFan4Delay : TON;                  // 4号风机启动延时
    tFanOffDelay : TON;                // 风机停止延时

    // 报警延时
    tFlowDelay : TON;                  // 流量报警延时
    tPressureDelay : TON;              // 压力报警延时
    tTempDelay : TON;                  // 温度报警延时
    tAntiFreezeDelay : TON;            // 防冻报警延时

    // 状态标记
    bFlowTrip : Bool;                  // 流量跳闸
    bPressureTrip : Bool;              // 压力跳闸
    bTempTrip : Bool;                  // 温度跳闸
    bFreezeTrip : Bool;                // 防冻跳闸
    bCoolingDemand : Bool;             // 冷却需求
    bChillerInterlock : Bool;          // 冷机联锁

    // PID 温度调节
    rTempError : Real;                 // 温度偏差
    rPrevError : Real;                 // 上次偏差
    rIntegral : Real;                  // 积分累加
    rFanOutput : Real;                 // 风机计算输出 (0-1)
    rFanStaging : Real;                // 风机分级值
    iFanStages : Int;                  // 风机档位 0-4
    iReqFans : Int;                    // 需求风机台数
END_VAR

BEGIN
    // ── 急停 ──
    IF NOT bEmergencyStop THEN
        bFanRun1 := FALSE; bFanRun2 := FALSE;
        bFanRun3 := FALSE; bFanRun4 := FALSE;
        bPumpRun := FALSE; rVFDSpeed := 0.0;
        bFault := TRUE;
        RETURN;
    END_IF;

    // ── 故障复位 ──
    IF bFault AND bReset THEN
        bFault := FALSE;
        bFlowTrip := FALSE; bPressureTrip := FALSE;
        bTempTrip := FALSE; bFreezeTrip := FALSE;
    END_IF;

    IF bFault THEN RETURN; END_IF;

    // ── 停止 ──
    IF bStop THEN
        bFanRun1 := FALSE; bFanRun2 := FALSE;
        bFanRun3 := FALSE; bFanRun4 := FALSE;
        bPumpRun := FALSE; rVFDSpeed := 0.0;
    END_IF;

    // ── 出厂水温差计算 ──
    rTempDiff := rTempReturn - rTempSupply;

    // ── 安全联锁 ──
    // 流量开关
    IF NOT bFlowSwitch THEN
        tFlowDelay(IN := TRUE, PT := T#5S);
        IF tFlowDelay.Q THEN
            bFlowTrip := TRUE;
            bFlowAlarm := TRUE;
            bFanRun1 := FALSE; bFanRun2 := FALSE;
            bFanRun3 := FALSE; bFanRun4 := FALSE;
            rVFDSpeed := 0.0;
        END_IF;
    ELSE
        tFlowDelay(IN := FALSE);
    END_IF;

    // 压力保护
    IF rPressure > rPressureHigh OR rPressure < rPressureLow THEN
        tPressureDelay(IN := TRUE, PT := T#3S);
        IF tPressureDelay.Q THEN
            bPressureTrip := TRUE;
            bPressureAlarm := TRUE;
        END_IF;
    ELSE
        tPressureDelay(IN := FALSE);
    END_IF;

    // 防冻保护
    IF rTempOutdoor < rAntiFreezeTemp THEN
        tAntiFreezeDelay(IN := TRUE, PT := T#30S);
        IF tAntiFreezeDelay.Q THEN
            bFreezeTrip := TRUE;
            bAntiFreezeAlarm := TRUE;
        END_IF;
    ELSE
        tAntiFreezeDelay(IN := FALSE);
    END_IF;

    // 流量/压力/防冻跳闸时故障停机
    IF bFlowTrip OR bPressureTrip OR bFreezeTrip THEN
        bFault := TRUE;
        bFanRun1 := FALSE; bFanRun2 := FALSE;
        bFanRun3 := FALSE; bFanRun4 := FALSE;
        rVFDSpeed := 0.0;
        RETURN;
    END_IF;

    // ── 循环泵控制 ──
    bChillerInterlock := bChillerRun;
    IF bEnable OR bChillerInterlock THEN
        bPumpRun := TRUE;
    ELSE
        bPumpRun := FALSE;
    END_IF;

    // ── 冷却需求计算 ──
    bCoolingDemand := rTempSupply > rTempSetpoint OR rTempDiff > rDiffSetpoint;

    // ── PID 温度调节 ──
    rTempError := rTempSupply - rTempSetpoint;

    IF bCoolingDemand AND bEnable AND NOT bStop THEN
        rIntegral := rIntegral + rTempError * 0.02;
        IF rIntegral > 1.0 THEN rIntegral := 1.0; END_IF;
        IF rIntegral < 0.0 THEN rIntegral := 0.0; END_IF;

        rFanOutput := rTempError * 0.1 + rIntegral;
        IF rFanOutput > 1.0 THEN rFanOutput := 1.0; END_IF;
        IF rFanOutput < 0.0 THEN rFanOutput := 0.0; END_IF;
    ELSE
        rFanOutput := 0.0;
        rIntegral := 0.0;
    END_IF;

    // ── VFD 频率计算 ──
    rVFDSpeed := rFanOutput * 50.0;

    // ── 风机分级 ──
    rFanStaging := rFanOutput * 5.0;  // 0-5 的缩放
    iReqFans := REAL_TO_INT(rFanStaging);
    IF iReqFans > 4 THEN iReqFans := 4; END_IF;
    IF iReqFans < 0 THEN iReqFans := 0; END_IF;

    // ── 错时启动风机 ──
    // 1号风机
    IF iReqFans >= 1 THEN
        tFan1Delay(IN := TRUE, PT := T#2M);
        bFanRun1 := tFan1Delay.Q;
    ELSE
        tFan1Delay(IN := FALSE);
        bFanRun1 := FALSE;
    END_IF;

    // 2号风机（+2分钟延时）
    IF iReqFans >= 2 THEN
        tFan2Delay(IN := TRUE, PT := T#4M);
        bFanRun2 := tFan2Delay.Q;
    ELSE
        tFan2Delay(IN := FALSE);
        bFanRun2 := FALSE;
    END_IF;

    // 3号风机（+2分钟延时）
    IF iReqFans >= 3 THEN
        tFan3Delay(IN := TRUE, PT := T#6M);
        bFanRun3 := tFan3Delay.Q;
    ELSE
        tFan3Delay(IN := FALSE);
        bFanRun3 := FALSE;
    END_IF;

    // 4号风机（+2分钟延时）
    IF iReqFans >= 4 THEN
        tFan4Delay(IN := TRUE, PT := T#8M);
        bFanRun4 := tFan4Delay.Q;
    ELSE
        tFan4Delay(IN := FALSE);
        bFanRun4 := FALSE;
    END_IF;

    // ── 高温报警 ──
    IF rTempSupply > rTempSetpoint + 5.0 THEN
        tTempDelay(IN := TRUE, PT := T#30S);
        IF tTempDelay.Q THEN
            bTempHighAlarm := TRUE;
        END_IF;
    ELSE
        tTempDelay(IN := FALSE);
        bTempHighAlarm := FALSE;
    END_IF;

    // ── 运行风机计数 ──
    iActiveFans := 0;
    IF bFanRun1 THEN iActiveFans := iActiveFans + 1; END_IF;
    IF bFanRun2 THEN iActiveFans := iActiveFans + 1; END_IF;
    IF bFanRun3 THEN iActiveFans := iActiveFans + 1; END_IF;
    IF bFanRun4 THEN iActiveFans := iActiveFans + 1; END_IF;

END_FUNCTION_BLOCK
```

## 参数配置

| 参数 | 典型值 | 说明 |
|------|--------|------|
| rTempSetpoint | 32.0 °C | 出水温度设定值 |
| rDiffSetpoint | 5.0 °C | 目标进出水温差 |
| rAntiFreezeTemp | 4.0 °C | 防冻保护启动温度 |
| rPressureLow | 1.0 bar | 系统低压报警 |
| rPressureHigh | 8.0 bar | 系统高压报警 |

## 安全保护说明

| 保护 | 延时 | 动作 |
|------|:----:|------|
| 流量丢失 | 5s | 停止所有风机和 VFD |
| 压力异常 | 3s | 触发故障停机 |
| 防冻 | 30s | 触发故障预警（可配置为开启循环泵） |
| 高温 | 30s | 报警信号输出 |

## 调试建议
- **VFD 参数整定**：先手动设定 VFD 频率值，确认风机转向正确后再启用自动 PID
- **风机错时启动**：建议间隔 2-5 分钟，避免同时启动造成电网冲击
- **防冻逻辑**：北方冬季建议在防冻报警后增加循环泵强制运行和电加热启动逻辑
- **冷机联锁**：确认冷却塔与冷机的启停时序，先开水泵再开冷机
