# 传送带控制 — SCL 生成模板

## 功能描述
多段传送带的速度控制和联锁，带物料检测、满料停止、紧急停止。

## SCL 代码模板

```scl
FUNCTION_BLOCK "ConveyorControl"
TITLE = '传送带控制'
VERSION : 0.1

VAR_INPUT
  iStart : BOOL;             // 启动
  iStop : BOOL;              // 停止
  iEStop : BOOL;             // 急停（常闭）
  iSensorEntry : BOOL;       // 入口传感器
  iSensorMid : BOOL;         // 中部传感器
  iSensorExit : BOOL;        // 出口传感器
  iJamSensor : BOOL;         // 堵料传感器
  iFullSensor : BOOL;        // 满料传感器
  iAutoMode : BOOL;          // 自动模式
  iSpeedPot : INT;           // 速度电位器 (0-27648)
END_VAR

VAR_OUTPUT
  oConveyorRun : BOOL;       // 传送带运行
  oSpeedOut : INT;           // 速度输出 (0-27648)
  oJamAlarm : BOOL;          // 堵料报警
  oFullLight : BOOL;         // 满料指示灯
  oRunningLight : BOOL;      // 运行指示灯
END_VAR

VAR
  iState : INT;              // 状态: 0=STOP, 1=RUN, 2=JAM, 3=FULL
  tonJamDelay : TON;         // 堵料检测延时
  xJamTimerRun : BOOL;       // 堵料计时运行中
  rSpeedPercent : REAL;      // 速度百分比
END_VAR

BEGIN
  // === 速度转换 ===
  rSpeedPercent := INT_TO_REAL(iSpeedPot) / 276.48;
  IF rSpeedPercent < 10.0 THEN
    rSpeedPercent := 10.0;  // 最低速度 10%
  END_IF;
  oSpeedOut := REAL_TO_INT(rSpeedPercent * 276.48 / 100.0);

  // === 急停 ===
  IF NOT iEStop THEN
    iState := 0;
    oConveyorRun := FALSE;
    oJamAlarm := TRUE;
    RETURN;
  END_IF;

  // === 满料停止 ===
  IF iFullSensor THEN
    iState := 3;
    oConveyorRun := FALSE;
    oFullLight := TRUE;
  END_IF;

  // === 启动 ===
  IF iStart AND NOT iStop AND NOT iFullSensor THEN
    IF iAutoMode THEN
      // 自动模式: 入口有料才启动
      IF iSensorEntry THEN
        iState := 1;
        oFullLight := FALSE;
      END_IF;
    ELSE
      // 手动模式: 直接启动
      iState := 1;
      oFullLight := FALSE;
    END_IF;
  END_IF;

  // === 停止 ===
  IF iStop THEN
    iState := 0;
    oConveyorRun := FALSE;
  END_IF;

  // === 传送带运行 ===
  IF iState = 1 THEN
    oConveyorRun := TRUE;
    oRunningLight := TRUE;
  ELSE
    oConveyorRun := FALSE;
    oRunningLight := FALSE;
  END_IF;

  // === 堵料检测 ===
  IF iSensorEntry AND iSensorMid AND NOT iSensorExit AND iState = 1 THEN
    IF NOT xJamTimerRun THEN
      tonJamDelay(IN := TRUE, PT := T#5S);
      xJamTimerRun := TRUE;
    END_IF;
    IF tonJamDelay.Q THEN
      iState := 2;
      oJamAlarm := TRUE;
    END_IF;
  ELSE
    tonJamDelay(IN := FALSE);
    xJamTimerRun := FALSE;
  END_IF;

  // === 出口物料放行 ===
  IF iSensorExit AND iState = 1 THEN
    // 出口有料时继续运行，等待下游取走
    oConveyorRun := TRUE;
  END_IF;
END_FUNCTION_BLOCK
```

## 联锁规则
- 急停：无条件停止所有传送带
- 满料：入口传送带停止，防止堆积
- 堵料：入口和中段同时有料、出口无料超过 5s 判定为堵料
- 速度：保留 10% 最低速度防止电机堵转
