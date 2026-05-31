# 传送带控制 SCL 模板

## 适用场景
- 单条/多条传送带启停控制
- 传送带级联（上下游联动）
- 物料检测与分拣
- 变频调速传送带

## SCL 编码规范

### 变量命名
```
bStart           : Bool;    // 启动按钮
bStop            : Bool;    // 停止按钮
bEmergencyStop   : Bool;    // 急停
bMaterialDetect  : Bool;    // 物料检测
bJamDetect       : Bool;    // 堵料检测
bDownstreamReady : Bool;    // 下游就绪
bUpstreamRunning : Bool;    // 上游运行中
rSpeedSetpoint   : Real;    // 速度设定 (0-1500 rpm)
rSpeedActual     : Real;    // 实际速度
iState           : Int;     // 状态
tiAccelTime      : Time;    // 加速时间
tiDecelTime      : Time;    // 减速时间
```

### 级联控制逻辑（多条传送带必须实现）
1. 逆序启动：下游传送带先启动，上游后启动
2. 顺序停止：上游先停，下游后停
3. 下游故障时上游立即停止（防堵料）
4. 上游故障时下游延时停止（清空物料）

### 物料跟踪
- 物料检测上升沿 → 启动计数器
- 延时后下游传感器未检测到 → 堵料报警
- 连续3次堵料 → 故障锁定

### 状态机
```
IDLE(0) -> STARTING(1) -> RUNNING(2) -> STOPPING(3) -> IDLE(0)
任意状态 -> FAULT(4) --复位--> IDLE(0)
```

### 示例结构
```pascal
FUNCTION_BLOCK "ConveyorControl"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
VAR_INPUT
    bStart : Bool;
    bStop : Bool;
    bEmergencyStop : Bool;
    bMaterialSensor : Bool;      // 入料传感器
    bDischargeSensor : Bool;     // 出料传感器
    bDownstreamReady : Bool;     // 下游就绪
    rSpeedSetpoint : Real;
END_VAR

VAR_OUTPUT
    bRun : Bool;
    bFault : Bool;
    iFaultCode : Int;
    iMaterialCount : Int;        // 物料计数
    rActualSpeed : Real;
END_VAR

VAR
    iState : Int := 0;
    tiStartDelay : Time;         // 启动延时（级联）
    tiStopDelay : Time;          // 停止延时
    tiTrackingTimeout : Time;    // 物料跟踪超时
    iJamCount : Int := 0;        // 堵料计数
END_VAR

BEGIN
    // 实现级联控制 + 物料跟踪
END_FUNCTION_BLOCK
```
