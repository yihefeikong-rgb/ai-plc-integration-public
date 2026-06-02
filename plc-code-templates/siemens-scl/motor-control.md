# 电机控制 — SCL 生成模板

## 功能描述
三相异步电机的正反转控制，带急停、过载保护、电流监视。

## SCL 代码模板

```scl
FUNCTION_BLOCK "MotorControl"
TITLE = '电机控制'
VERSION : 0.1

VAR_INPUT
  iStartFwd : BOOL;        // 正转启动按钮
  iStartRev : BOOL;        // 反转启动按钮
  iStop : BOOL;            // 停止按钮
  iEStop : BOOL;           // 急停（常闭）
  iOverload : BOOL;        // 过载保护（常闭）
  iFwdLimit : BOOL;        // 正转限位
  iRevLimit : BOOL;        // 反转限位
  iSpeedSetpoint : REAL;   // 速度设定值 (0-3000 rpm)
  rCurrentActual : REAL;   // 实际电流值 (A)
END_VAR

VAR_OUTPUT
  oRunFwd : BOOL;          // 正转接触器
  oRunRev : BOOL;          // 反转接触器
  oSpeedActual : REAL;     // 实际速度输出
  oFault : BOOL;           // 故障指示
  oRunning : BOOL;         // 运行指示
END_VAR

VAR
  iState : INT;            // 状态机: 0=STOP, 1=RUN_FWD, 2=RUN_REV, 3=FAULT
  rCurrentLimit : REAL;    // 过流阈值
  tonFault : TON;          // 故障延时
  rRampUp : REAL;          // 加速斜坡
END_VAR

BEGIN
  // === 状态机: 急停/过载检测 ===
  IF NOT iEStop OR NOT iOverload THEN
    iState := 3;  // FAULT
    oRunFwd := FALSE;
    oRunRev := FALSE;
    oFault := TRUE;
  END_IF;

  // === 正常停止 ===
  IF iStop AND iState <> 3 THEN
    iState := 0;  // STOP
    oRunFwd := FALSE;
    oRunRev := FALSE;
  END_IF;

  // === 正转启动 ===
  IF iStartFwd AND iState = 0 AND iEStop AND iOverload THEN
    IF NOT iFwdLimit THEN
      iState := 1;  // RUN_FWD
      oRunFwd := TRUE;
      oRunRev := FALSE;
    END_IF;
  END_IF;

  // === 反转启动 ===
  IF iStartRev AND iState = 0 AND iEStop AND iOverload THEN
    IF NOT iRevLimit THEN
      iState := 2;  // RUN_REV
      oRunFwd := FALSE;
      oRunRev := TRUE;
    END_IF;
  END_IF;

  // === 正转限位停止 ===
  IF iFwdLimit AND iState = 1 THEN
    iState := 0;
    oRunFwd := FALSE;
  END_IF;

  // === 反转限位停止 ===
  IF iRevLimit AND iState = 2 THEN
    iState := 0;
    oRunRev := FALSE;
  END_IF;

  // === 过流保护 ===
  IF rCurrentActual > rCurrentLimit AND iState <> 3 THEN
    iState := 3;
    oRunFwd := FALSE;
    oRunRev := FALSE;
    oFault := TRUE;
  END_IF;

  // === 状态输出 ===
  oRunning := oRunFwd OR oRunRev;
  oSpeedActual := iSpeedSetpoint;
END_FUNCTION_BLOCK
```

## 变量命名规范
- 输入: iXxx（匈牙利命名法）
- 输出: oXxx
- 静态/中间: 小写前缀 + 驼峰
- 定时器: tonXxx, tofXxx, tpXxx
