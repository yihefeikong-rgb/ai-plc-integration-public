# 电机控制 SCL 模板

## 适用场景
- 三相异步电机正反转
- 星三角启动
- 变频器速度控制
- 多段速运行

## SCL 编码规范

### 变量命名（匈牙利命名法）
```
bEmergencyStop   : Bool;    // 急停信号
bOverload        : Bool;    // 过载信号
bRunForward      : Bool;    // 正转运行
bRunReverse      : Bool;    // 反转运行
bRunFeedback     : Bool;    // 运行反馈
rSpeedSetpoint   : Real;    // 速度设定 (0-3000 rpm)
rSpeedActual     : Real;    // 实际速度
iState           : Int;     // 状态机状态
tOnDelay         : Time;    // 启动延时
tOffDelay        : Time;    // 停止延时
tStarDeltaTime   : Time;    // 星三角切换时间
```

### 互锁逻辑（必须实现）
1. 正反转互锁：正转和反转不能同时为 TRUE
2. 急停优先：急停=TRUE 时所有输出置 FALSE
3. 过载保护：过载=TRUE 时停止并锁定，需手动复位
4. 运行反馈超时：启动后 5s 内无反馈则报故障
5. 正反转切换延时：切换方向前至少等待 2s

### 状态机
```
INIT(0) -> STOP(1) -> RUN_FORWARD(2) / RUN_REVERSE(3) -> FAULT(4)
FAULT(4) --复位--> STOP(1)
```

### 示例结构
```pascal
FUNCTION_BLOCK "MotorControl"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
VAR_INPUT
    bStartForward : Bool;     // 正转启动按钮
    bStartReverse : Bool;     // 反转启动按钮
    bStop : Bool;             // 停止按钮
    bEmergencyStop : Bool;    // 急停（常闭）
    bOverload : Bool;         // 过载（常闭）
    bRunFeedback : Bool;      // 运行反馈
    rSpeedSetpoint : Real;    // 速度给定
END_VAR

VAR_OUTPUT
    bForwardOut : Bool;       // 正转输出
    bReverseOut : Bool;       // 反转输出
    bFault : Bool;            // 故障指示
    iFaultCode : Int;         // 故障代码
    rSpeedOut : Real;         // 速度输出
END_VAR

VAR
    iState : Int := 0;        // 状态机
    tSwitchDelay : Time;      // 切换延时
    tFeedbackTimeout : Time;  // 反馈超时
END_VAR

BEGIN
    // 实现状态机 + 互锁逻辑
END_FUNCTION_BLOCK
```
