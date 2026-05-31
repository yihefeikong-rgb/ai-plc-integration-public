# PID 控制 SCL 模板

## 适用场景
- 温度 PID 控制（加热/冷却）
- 压力 PID 控制
- 流量 PID 控制
- 液位 PID 控制
- 速度闭环控制

## SCL 编码规范

### 变量命名
```
bEnable          : Bool;    // PID 使能
bAutoMode        : Bool;    // 自动/手动模式
rSetpoint        : Real;    // 设定值 (SP)
rProcessValue    : Real;    // 过程值 (PV)
rOutput          : Real;    // 控制输出 (CV) 0-100%
rKp              : Real;    // 比例增益
rTi              : Real;    // 积分时间 (ms)
rTd              : Real;    // 微分时间 (ms)
rOutputMax       : Real;    // 输出上限
rOutputMin       : Real;    // 输出下限
rManualOutput    : Real;    // 手动输出值
rDeadband        : Real;    // 死区
iAlarmHigh       : Int;     // 高报警阈值
iAlarmLow        : Int;     // 低报警阈值
```

### 安全保护（必须实现）
1. 输出限幅：rOutput 限制在 [rOutputMin, rOutputMax]
2. 传感器故障检测：PV 连续 3s 不变 → 切换手动模式
3. 偏差报警：|SP - PV| > 偏差阈值 → 报警
4. 积分分离：大偏差时取消积分作用
5. 无扰切换：手动→自动切换时 bumpless transfer

### PID 算法
- 位置式 PID（优先）
- 积分抗饱和 (anti-windup)
- 微分先行 (derivative on PV, not error)

### 状态机
```
DISABLED(0) -> MANUAL(1) <-> AUTO(2)
任意状态 -> FAULT(3) -> MANUAL(1)
```

### 示例结构
```pascal
FUNCTION_BLOCK "PIDController"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
VAR_INPUT
    bEnable : Bool;
    bAutoMode : Bool;
    rSetpoint : Real;
    rProcessValue : Real;
    rKp : Real := 1.0;
    rTi : Real := 1000.0;       // ms
    rTd : Real := 0.0;
    rOutputMax : Real := 100.0;
    rOutputMin : Real := 0.0;
    rSampleTime : Real := 100.0; // ms
END_VAR

VAR_OUTPUT
    rOutput : Real;
    bAlarmHigh : Bool;
    bAlarmLow : Bool;
    bSensorFault : Bool;
    bInAutoMode : Bool;
END_VAR

VAR
    rIntegral : Real;
    rPrevError : Real;
    rPrevPV : Real;
    tiSampleTimer : Time;
    tiSensorWatchdog : Time;
END_VAR

BEGIN
    // 实现位置式 PID + 抗饱和 + 无扰切换
END_FUNCTION_BLOCK
```
