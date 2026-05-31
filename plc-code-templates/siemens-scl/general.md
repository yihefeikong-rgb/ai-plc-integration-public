# 通用 SCL 代码生成模板

## 适用范围
无特定模板匹配时的通用 SCL 代码生成。适用于各类逻辑控制、数据处理、通信处理等场景。

## SCL 编码规范（IEC 61131-3 + 西门子扩展）

### 变量命名（匈牙利命名法）
| 前缀 | 类型 | 示例 |
|------|------|------|
| b | Bool | bStart, bFault |
| i | Int | iState, iCount |
| di | DInt | diPosition |
| r | Real | rTemperature, rSpeed |
| s | String | sMessage |
| t | Time | tDelay |
| arr | Array | arrData |
| stat | 静态变量 | statCycleCount |

### 代码结构要求
1. **版本头部**：包含版本号、作者、日期、描述
2. **输入验证**：所有输入参数必须做范围检查
3. **输出限幅**：所有输出必须限制在安全范围内
4. **状态机**：复杂逻辑必须使用状态机而非嵌套 IF
5. **故障处理**：捕获异常状态，返回故障码
6. **中文注释**：关键逻辑必须有中文注释

### 必须包含的安全特性
1. 急停互锁（如果涉及运动/输出）
2. 看门狗/心跳检测
3. 超时保护
4. 上电初始化

### 通用 FB 骨架
```pascal
FUNCTION_BLOCK "BlockName"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'
// 描述: <功能描述>

VAR_INPUT
    bEnable : Bool;             // 使能
    bEmergencyStop : Bool;      // 急停（常闭，TRUE=正常）
END_VAR

VAR_OUTPUT
    bBusy : Bool;               // 忙信号
    bDone : Bool;               // 完成信号
    bFault : Bool;              // 故障信号
    iFaultCode : Int;           // 故障代码
END_VAR

VAR_IN_OUT
    // 需保持的变量
END_VAR

VAR
    iState : Int := 0;          // 状态机 0=IDLE
    tiWatchdog : Time;          // 看门狗
END_VAR

BEGIN
    // === 急停检查（最高优先级）===
    IF NOT bEmergencyStop THEN
        bFault := TRUE;
        iFaultCode := 1;        // 急停激活
        RETURN;
    END_IF;
    
    // === 状态机 ===
    CASE iState OF
        0: // IDLE - 等待使能
            // ...
        1: // RUN - 运行
            // ...
        99: // FAULT - 故障
            // 故障复位逻辑
    END_CASE;
    
    // === 看门狗 ===
    // 防止程序死循环
END_FUNCTION_BLOCK
```

### 禁止事项
- 禁止使用 JMP/LABEL 跳转指令
- 禁止无限循环（FOR/WHILE 必须有退出条件）
- 禁止直接操作外设地址（使用 DB 映射）
- 禁止在 FB 中使用全局变量（使用 VAR_IN_OUT）
