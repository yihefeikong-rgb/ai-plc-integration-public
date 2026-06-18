# 包装机 — SCL 生成模板

## 功能描述
包装机状态机控制，实现送料→夹紧→封口→切断→顶出的自动化循环。带批次计数、状态超时报警和故障处理。

## 核心特性
- **CASE 状态机**：8 个明确状态，状态转换清晰
- **超时监控**：每个工步都有独立超时检测，超时自动报故障
- **批次跟踪**：完成计数 + 目标批次到达自动停止
- **安全互锁**：急停、过载、安全门三重保护
- **故障代码**：每个报警源对应唯一故障码，便于诊断

## 状态图

```
         ┌─────────────────────────────────────┐
         │                                     │
    ┌────▼────┐  启动   ┌─────────┐  产品到位   ┌───────┐
    │  IDLE   ├───────►│STARTING ├──────────►│ CLAMP │
    │   (0)   │         │   (1)   │            │  (3)  │
    └────┬────┘         └─────────┘            └───┬───┘
         ▲                                        │
         │                                     夹紧OK
    ┌────┴────┐  顶出OK   ┌────────┐  切断OK   ┌───▼───┐
    │ EJECT   │◄─────────│  CUT   │◄─────────│ SEAL  │
    │   (6)   │           │  (5)   │           │  (4)  │
    └─────────┘           └────────┘           └───────┘
         │                                          │
         │  ← 回到 IDLE                             │ 超时
         ▼                                          ▼
    ┌──────────┐                              ┌──────────┐
    │COMPLETE  │                              │  FAULT   │
    │   (7)    │                              │   (99)   │
    └──────────┘                              └──────────┘
```

## SCL 代码模板

```scl
FUNCTION_BLOCK "PackagingMachine"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bStart : Bool;                     // 启动循环
    bStop : Bool;                      // 停止
    bReset : Bool;                     // 故障复位
    bEmergencyStop : Bool;             // 急停（常闭）
    bProductPresent : Bool;            // 产品到到位
    bClampClosed : Bool;               // 夹爪闭合反馈
    bSealDone : Bool;                  // 封口完成
    bCutDone : Bool;                   // 切断完成
    bEjectDone : Bool;                 // 顶出完成
    bGuardOpen : Bool;                 // 安全门打开
    bOverload : Bool;                  // 过载保护（常闭）
    iTargetBatch : Int;                // 目标批次数量
END_VAR

VAR_OUTPUT
    bConveyorRun : Bool;               // 输送带运行
    bClamp : Bool;                     // 夹爪
    bSeal : Bool;                      // 封口
    bCut : Bool;                       // 切断
    bEject : Bool;                     // 顶出
    bRunning : Bool;                   // 运行中
    bFault : Bool;                     // 故障
    iState : Int;                      // 当前状态（调试用）
    iBatchCount : Int;                 // 当前批次计数
    bBatchComplete : Bool;             // 批次完成
    iFaultCode : Int;                  // 故障代码
END_VAR

VAR
    // 状态常量
    c_IDLE : Int := 0;                 // 待机
    c_STARTING : Int := 1;             // 启动中
    c_CONVEY : Int := 2;               // 送料
    c_CLAMP : Int := 3;                // 夹紧
    c_SEAL : Int := 4;                 // 封口
    c_CUT : Int := 5;                  // 切断
    c_EJECT : Int := 6;                // 顶出
    c_COMPLETE : Int := 7;             // 循环完成
    c_FAULT : Int := 99;               // 故障

    // 当前状态
    iCurrentState : Int := 0;

    // 定时器
    tStartDelay : TON;                 // 启动延时
    tConveyDelay : TON;                // 送料超时
    tClampDelay : TON;                 // 夹紧超时
    tSealDelay : TON;                  // 封口超时
    tCutDelay : TON;                   // 切断超时
    tEjectDelay : TON;                 // 顶出超时
    tFaultReset : TON;                 // 故障复位延时

    // 边沿检测
    bStartOld : Bool;                  // 启动按钮上一周期
    bStartRising : Bool;               // 启动上升沿

    // 报警
    bAlarmConvey : Bool;               // 送料超时报警
    bAlarmClamp : Bool;                // 夹紧超时报警
    bAlarmSeal : Bool;                 // 封口超时报警
    bAlarmCut : Bool;                  // 切断超时报警
    bAlarmEject : Bool;                // 顶出超时报警
END_VAR

BEGIN
    // ── 安全链 ──
    IF NOT bEmergencyStop OR NOT bOverload OR bGuardOpen THEN
        bConveyorRun := FALSE; bClamp := FALSE; bSeal := FALSE;
        bCut := FALSE; bEject := FALSE; bRunning := FALSE;
        iCurrentState := c_FAULT; bFault := TRUE; iFaultCode := 1;
        RETURN;
    END_IF;

    // ── 故障复位 ──
    IF bFault AND bReset AND NOT bStart THEN
        iCurrentState := c_IDLE; bFault := FALSE; iFaultCode := 0;
        bAlarmConvey := FALSE; bAlarmClamp := FALSE; bAlarmSeal := FALSE;
        bAlarmCut := FALSE; bAlarmEject := FALSE;
        bBatchComplete := FALSE;
    END_IF;

    IF bFault THEN RETURN; END_IF;

    // ── 上升沿检测 ──
    bStartRising := bStart AND NOT bStartOld;
    bStartOld := bStart;

    // ── 状态机 ──
    CASE iCurrentState OF

        0:  // IDLE — 等待启动
            bConveyorRun := FALSE; bClamp := FALSE; bSeal := FALSE;
            bCut := FALSE; bEject := FALSE; bRunning := FALSE;

            // 批次完成时自动停止
            IF iBatchCount >= iTargetBatch AND iTargetBatch > 0 THEN
                bBatchComplete := TRUE;
            END_IF;

            IF bStartRising AND NOT bBatchComplete THEN
                iCurrentState := c_STARTING;
            END_IF;

        1:  // STARTING — 启动延时 1s
            tStartDelay(IN := TRUE, PT := T#1S);
            bRunning := TRUE;
            IF tStartDelay.Q THEN
                tStartDelay(IN := FALSE);
                iCurrentState := c_CONVEY;
            END_IF;

        2:  // CONVEY — 送料等待产品到位
            bConveyorRun := TRUE; bRunning := TRUE;
            tConveyDelay(IN := TRUE, PT := T#10S);

            IF bProductPresent THEN
                tConveyDelay(IN := FALSE);
                bConveyorRun := FALSE;
                iCurrentState := c_CLAMP;
            ELSIF tConveyDelay.Q THEN
                // 送料超时报警
                bAlarmConvey := TRUE; bFault := TRUE; iFaultCode := 10;
                iCurrentState := c_FAULT;
            END_IF;

        3:  // CLAMP — 夹紧
            bClamp := TRUE; bRunning := TRUE;
            tClampDelay(IN := TRUE, PT := T#3S);

            IF bClampClosed THEN
                tClampDelay(IN := FALSE);
                iCurrentState := c_SEAL;
            ELSIF tClampDelay.Q THEN
                bAlarmClamp := TRUE; bFault := TRUE; iFaultCode := 20;
                iCurrentState := c_FAULT;
            END_IF;

        4:  // SEAL — 封口
            bClamp := TRUE; bSeal := TRUE; bRunning := TRUE;
            tSealDelay(IN := TRUE, PT := T#5S);

            IF bSealDone THEN
                tSealDelay(IN := FALSE);
                bSeal := FALSE;
                iCurrentState := c_CUT;
            ELSIF tSealDelay.Q THEN
                bAlarmSeal := TRUE; bFault := TRUE; iFaultCode := 30;
                iCurrentState := c_FAULT;
            END_IF;

        5:  // CUT — 切断
            bClamp := TRUE; bCut := TRUE; bRunning := TRUE;
            tCutDelay(IN := TRUE, PT := T#3S);

            IF bCutDone THEN
                tCutDelay(IN := FALSE);
                bCut := FALSE;
                bClamp := FALSE;
                iCurrentState := c_EJECT;
            ELSIF tCutDelay.Q THEN
                bAlarmCut := TRUE; bFault := TRUE; iFaultCode := 40;
                iCurrentState := c_FAULT;
            END_IF;

        6:  // EJECT — 顶出
            bEject := TRUE; bRunning := TRUE;
            tEjectDelay(IN := TRUE, PT := T#3S);

            IF bEjectDone THEN
                tEjectDelay(IN := FALSE);
                bEject := FALSE;
                iBatchCount := iBatchCount + 1;
                iCurrentState := c_COMPLETE;
            ELSIF tEjectDelay.Q THEN
                bAlarmEject := TRUE; bFault := TRUE; iFaultCode := 50;
                iCurrentState := c_FAULT;
            END_IF;

        7:  // COMPLETE — 循环完成，回到 IDLE
            bRunning := FALSE;
            iCurrentState := c_IDLE;

        99: // FAULT — 故障状态
            bConveyorRun := FALSE; bClamp := FALSE; bSeal := FALSE;
            bCut := FALSE; bEject := FALSE; bRunning := FALSE;
            bFault := TRUE;

    END_CASE;

    // ── 停止命令（任何非故障状态下） ──
    IF bStop AND iCurrentState <> c_FAULT AND iCurrentState <> c_IDLE THEN
        bConveyorRun := FALSE; bClamp := FALSE; bSeal := FALSE;
        bCut := FALSE; bEject := FALSE; bRunning := FALSE;
        iCurrentState := c_IDLE;
    END_IF;

    // ── 复位批次计数 ──
    IF bReset AND iTargetBatch > 0 THEN
        iBatchCount := 0;
        bBatchComplete := FALSE;
    END_IF;

    // ── 状态输出 ──
    iState := iCurrentState;

END_FUNCTION_BLOCK
```

## 故障代码表
| 代码 | 含义 | 可能原因 |
|:----:|------|---------|
| 1 | 安全链断开 | 急停/过载/安全门触发 |
| 10 | 送料超时 | 产品未到位/传感器故障 |
| 20 | 夹紧超时 | 气缸故障/气源压力不足 |
| 30 | 封口超时 | 加热丝断裂/温控异常 |
| 40 | 切断超时 | 刀具卡死/气缸故障 |
| 50 | 顶出超时 | 产品卡料/顶出气缸故障 |

## 调试建议
- 首次调试将各超时时间设为较大值，排除超时干扰
- 检查每个气缸磁簧开关/接近传感器信号是否正常
- 批次计数达到目标后自动停止，需复位才能继续生产
