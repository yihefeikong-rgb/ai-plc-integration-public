# VAV变风量末端控制 — VAVBoxControl

## 功能概述

VAV（Variable Air Volume）变风量末端箱控制，含级联PID（温度→风量→阀位）、压力无关控制、制冷/制热/死区自动切换、再热阀控制、夜间回退模式。

## 适用场景

- 商业楼宇变风量空调系统
- 单风道VAV末端箱（带再热盘管或无再热）
- 多区域独立温控
- 压力无关型VAV控制器

## 接口定义

### 输入
| 信号 | 类型 | 说明 |
|------|------|------|
| bEnable | Bool | 系统使能 |
| bReset | Bool | 故障复位 |
| bEmergencyStop | Bool | 急停（常闭） |
| bManualMode | Bool | 手动模式 |
| rAirflowActual | Real | 实际风量 (m3/h) |
| rAirflowRaw | Real | 传感器原始值 |
| rRoomTemp | Real | 区域回风温度 (degC) |
| rRoomHumidity | Real | 区域湿度 (%RH) |
| rDuctPressure | Real | 风管静压 (Pa) |
| rDamperFeedback | Real | 风阀开度反馈 (0-100%) |
| bDamperFault | Bool | 风阀故障 |
| bOccupied | Bool | 区域占用 |
| rCoolSetpoint / rHeatSetpoint | Real | 制冷/制热设定温度 |
| rAirflowMin / rAirflowMax | Real | 最小/最大风量限制 |
| rHumiditySetpoint | Real | 湿度设定值 |
| rNightSetbackOffset | Real | 夜间回退偏移 |

### 输出
| 信号 | 类型 | 说明 |
|------|------|------|
| rDamperCmd | Real | 风阀开度命令 (0-100%) |
| rReheatValve | Real | 再热阀开度 (0-100%) |
| rAirflowSetpoint | Real | 当前风量设定值 |
| bCoolMode / bHeatMode / bDeadband | Bool | 模式指示 |
| bNightMode | Bool | 夜间模式 |
| bDamperAlarm / bTempAlarm | Bool | 报警 |

## 控制策略

### 级联PID架构
```
[温度PID 外环] → 风量设定值 → [风量PID 内环] → 风阀开度
```

### 模式切换
| 模式 | 条件 | 动作 |
|:----:|------|------|
| COOL | 室温 > 设定+0.5degC | 温度PID输出映射到风量（越热风量越大） |
| HEAT | 室温 < 设定-0.5degC | 风量最小，再热PID调节再热阀 |
| DEADBAND | 温度在设定区间内 | 风量最小，再热关闭 |
| NIGHT | !bOccupied | 风量降至最小50%，防冻保护 |

### 压力无关控制
- 根据风管静压实时补偿风阀开度
- 标准工况250Pa下系数为1.0
- 静压变化时自动调整，保证风量不受管网扰动影响

### 夜间回退
- 非占用时段自动进入
- 温度设定值放宽（偏移可配置，默认3degC）
- 温度过低时启动再热防冻
- 温度过高时恢复最小新风

## 安全规则

1. 急停无条件关闭风阀
2. 风阀执行器故障即时报警
3. 温度越限超过15分钟触发报警
4. 风量设定值始终限制在最小最大范围内
5. 夜间模式自动防冻保护
