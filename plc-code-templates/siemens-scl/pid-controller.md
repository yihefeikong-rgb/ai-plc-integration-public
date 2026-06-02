# PID 控制器 — SCL 生成模板

## 功能描述
带积分分离和抗饱和的 PID 控制器，用于温度、压力、流量等模拟量控制。

## SCL 代码模板

```scl
FUNCTION_BLOCK "PIDController"
TITLE = 'PID控制器'
VERSION : 0.1

VAR_INPUT
  rSetpoint : REAL;         // 设定值 (工程单位)
  rProcessValue : REAL;     // 过程值 (工程单位)
  rKp : REAL;               // 比例增益
  rTi : REAL;               // 积分时间 (秒)
  rTd : REAL;               // 微分时间 (秒)
  rOutputMin : REAL;        // 输出下限
  rOutputMax : REAL;        // 输出上限
  iEnable : BOOL;           // PID 使能
  iReset : BOOL;            // 手动复位
  iManualMode : BOOL;       // 手动模式
  rManualValue : REAL;      // 手动输出值
  rDeadband : REAL;         // 死区
END_VAR

VAR_OUTPUT
  rControlOutput : REAL;    // 控制输出
  rError : REAL;            // 偏差值
  rP : REAL;                // P 分量
  rI : REAL;                // I 分量
  rD : REAL;                // D 分量
  oLimiting : BOOL;         // 输出限幅中
END_VAR

VAR
  rIntegral : REAL;         // 积分累加值
  rPrevError : REAL;        // 上次偏差
  rSampleTime : REAL;       // 采样时间 (秒)
  tonCycle : TON;           // 采样周期
  rOutput : REAL;           // 计算输出
END_VAR

BEGIN
  // === 采样定时器 (100ms) ===
  tonCycle(IN := iEnable, PT := T#100MS);
  
  IF tonCycle.Q AND iEnable THEN
    // 偏差计算
    rError := rSetpoint - rProcessValue;
    
    // 死区处理
    IF ABS(rError) < rDeadband THEN
      rError := 0.0;
    END_IF;
    
    // P 分量
    rP := rKp * rError;
    
    // I 分量 (积分分离: 偏差大时停止积分)
    IF ABS(rError) < 100.0 THEN
      rIntegral := rIntegral + rKp * rError * 0.1 / rTi;
    END_IF;
    
    // 抗饱和: 输出限幅时停止积分
    IF rOutput >= rOutputMax OR rOutput <= rOutputMin THEN
      rIntegral := rIntegral - rKp * rError * 0.1 / rTi;
    END_IF;
    
    rI := rIntegral;
    
    // D 分量
    rD := rKp * rTd * (rError - rPrevError) / 0.1;
    
    // 计算输出
    rOutput := rP + rI + rD;
    
    // 输出限幅
    IF rOutput > rOutputMax THEN
      rOutput := rOutputMax;
      oLimiting := TRUE;
    ELSIF rOutput < rOutputMin THEN
      rOutput := rOutputMin;
      oLimiting := TRUE;
    ELSE
      oLimiting := FALSE;
    END_IF;
    
    // 模式选择
    IF iManualMode THEN
      rControlOutput := rManualValue;
    ELSE
      rControlOutput := rOutput;
    END_IF;
    
    // 保存上次偏差
    rPrevError := rError;
  END_IF;
  
  // 复位
  IF iReset THEN
    rIntegral := 0.0;
    rPrevError := 0.0;
    rControlOutput := 0.0;
  END_IF;
END_FUNCTION_BLOCK
```

## 使用说明
- 采样周期固定 100ms
- 积分分离: 偏差 > 100 时停止积分
- 抗饱和: 输出限幅时反积分
- 手动/自动无扰切换
