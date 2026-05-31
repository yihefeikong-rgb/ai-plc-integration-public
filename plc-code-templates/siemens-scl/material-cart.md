# 运料小车往复控制 SCL 模板

## 适用场景
- 运料小车两点间自动往复运行
- 装卸料位自动定位
- 多周期计数与自动停止
- 手动/自动切换控制

## 控制逻辑

### 运行流程
```
按启动 → 前进(正转) → 前限位SQ1 → 停5秒(卸料)
  → 后退(反转) → 后限位SQ2 → 停3秒(装料)
  → 前进 → 循环...
  → 按停止: 完成当前半程后停
  → 急停: 立即停
```

### 状态机
```
IDLE(0) → FWD_RUN(1) → FWD_STOP_UNLOAD(2) → REV_RUN(3)
  → REV_STOP_LOAD(4) → FWD_RUN(1) → ...
  任意 → FAULT(5) → 复位 → IDLE(0)
```

### 变量命名
```
bStart           : Bool;    // 启动按钮
bStop            : Bool;    // 停止按钮
bEmergencyStop   : Bool;    // 急停(常闭)
bForwardLimit    : Bool;    // 前限位SQ1
bReverseLimit    : Bool;    // 后限位SQ2
bOverload        : Bool;    // 过载保护(常闭)
bManualMode      : Bool;    // 手动模式
bManualForward   : Bool;    // 手动正转
bManualReverse   : Bool;    // 手动反转
bForwardOut      : Bool;    // 正转输出KM1
bReverseOut      : Bool;    // 反转输出KM2
bRunning         : Bool;    // 运行指示
bFault           : Bool;    // 故障
iFaultCode       : Int;     // 故障码
iCycleCount      : Int;     // 完成周期数
iCycleSetpoint   : Int;     // 设定周期数(0=无限)
tiUnloadTime     : Time;    // 前位卸料时间(默认5s)
tiLoadTime       : Time;    // 后位装料时间(默认3s)
iState           : Int;     // 状态机
```

### 互锁要求
1. 正反转互锁：KM1和KM2不能同时为TRUE
2. 急停优先：急停激活时所有输出置FALSE，需手动复位
3. 过载保护：过载时停止并锁定
4. 限位保护：到限位立即切断对应方向输出
5. 正反转切换必须有延时（至少1s间隔）
