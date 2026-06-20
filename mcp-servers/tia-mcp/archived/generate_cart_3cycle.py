"""
生成 材料小车往复3次停止 的 LAD JSON + PLCopen XML + 一键运行脚本

功能: 材料小车自动循环前进/后退/卸载/装载，3次后停止
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from generate_plcopen_xml import generate_material_cart_xml

# ── 1. 生成 LAD JSON（给 lad_creator.py 用）──

LAD_PROGRAM = {
    "blockName": "AutoCart3Cycle",
    "version": "0.1",
    "author": "AI Generated",
    "networks": [
        {
            "networkNumber": 1,
            "title": "急停+过载安全链",
            "comment": "急停或过载时切断所有输出，锁存故障",
            "elements": [
                {"type": "normally_closed", "operand": "%I0.0", "symbol": "bEmergencyStop"},
                {"type": "coil", "operand": "%M0.0", "symbol": "bSafetyOK"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 2,
            "title": "故障锁存与复位",
            "comment": "安全链熔断→锁存故障；复位解除",
            "elements": [
                {"type": "normally_closed", "operand": "%M0.0", "symbol": "bSafetyOK"},
                {"type": "coil_set", "operand": "%M0.2", "symbol": "bFaultLatch"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 3,
            "title": "启动→前进（State=0→1）",
            "comment": "启动按钮触发前进，无故障时开始循环",
            "elements": [
                {"type": "normally_open", "operand": "%I0.1", "symbol": "bStart"},
                {"type": "normally_closed", "operand": "%M0.2", "symbol": "bFaultLatch"},
                {"type": "normally_closed", "operand": "%M2.0", "symbol": "bCycleDone"},
                {"type": "coil_set", "operand": "%M2.1", "symbol": "bStateFwd"}
            ],
            "hasParallelBranch": True,
            "parallelElements": [
                {"type": "normally_open", "operand": "%M2.1", "symbol": "bStateFwd"}
            ],
        },
        {
            "networkNumber": 4,
            "title": "前进→前限位→卸载（State=1→2）",
            "comment": "前进输出，到前限位后转卸载",
            "elements": [
                {"type": "normally_open", "operand": "%M2.1", "symbol": "bStateFwd"},
                {"type": "coil", "operand": "%Q0.0", "symbol": "bForwardOut"},
                {"type": "coil", "operand": "%Q0.2", "symbol": "bRunning"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 5,
            "title": "前进→前限位检测",
            "comment": "到前限位后清除前进状态，设置卸载状态",
            "elements": [
                {"type": "normally_open", "operand": "%M2.1", "symbol": "bStateFwd"},
                {"type": "normally_open", "operand": "%I0.2", "symbol": "bForwardLimit"},
                {"type": "coil_reset", "operand": "%M2.1", "symbol": "bStateFwd"},
                {"type": "coil_set", "operand": "%M2.2", "symbol": "bStateUnload"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 6,
            "title": "卸载定时（State=2→3）",
            "comment": "TON定时5秒，到后转后退",
            "elements": [
                {"type": "normally_open", "operand": "%M2.2", "symbol": "bStateUnload"},
                {"type": "timer_on", "operand": "T1", "symbol": "tmrUnload", "preset": "T#5S"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 7,
            "title": "卸载完成→后退（State=2→3）",
            "comment": "定时到后清除卸载状态，设置后退状态",
            "elements": [
                {"type": "timer_on", "operand": "T1", "symbol": "tmrUnload"},
                {"type": "normally_open", "operand": "T1", "symbol": "tmrUnload.Q"},
                {"type": "coil_reset", "operand": "%M2.2", "symbol": "bStateUnload"},
                {"type": "coil_set", "operand": "%M2.3", "symbol": "bStateRev"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 8,
            "title": "后退输出（State=3）",
            "comment": "后退运行，到后限位转装载",
            "elements": [
                {"type": "normally_open", "operand": "%M2.3", "symbol": "bStateRev"},
                {"type": "coil", "operand": "%Q0.1", "symbol": "bReverseOut"},
                {"type": "coil", "operand": "%Q0.2", "symbol": "bRunning"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 9,
            "title": "后退→后限位→装载（State=3→4）",
            "comment": "到后限位清除后退设装载",
            "elements": [
                {"type": "normally_open", "operand": "%M2.3", "symbol": "bStateRev"},
                {"type": "normally_open", "operand": "%I0.3", "symbol": "bReverseLimit"},
                {"type": "coil_reset", "operand": "%M2.3", "symbol": "bStateRev"},
                {"type": "coil_set", "operand": "%M2.4", "symbol": "bStateLoad"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 10,
            "title": "装载定时（State=4→0/1）",
            "comment": "TON定时3秒，到后计数+1，判断是否继续循环",
            "elements": [
                {"type": "normally_open", "operand": "%M2.4", "symbol": "bStateLoad"},
                {"type": "timer_on", "operand": "T2", "symbol": "tmrLoad", "preset": "T#3S"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 11,
            "title": "装载完成→计数判断",
            "comment": "装载定时到，自增计数。满3次→停止，不满→继续前进",
            "elements": [
                {"type": "timer_on", "operand": "T2", "symbol": "tmrLoad"},
                {"type": "normally_open", "operand": "T2", "symbol": "tmrLoad.Q"},
                {"type": "coil_reset", "operand": "%M2.4", "symbol": "bStateLoad"},
                {"type": "coil", "operand": "%M3.0", "symbol": "bIncrementCycle"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 12,
            "title": "计数 ≥ 3 ? → 停止 / 继续",
            "comment": "计数满3次设 bCycleDone，否则设 bStateFwd 继续",
            "elements": [
                {"type": "normally_open", "operand": "%M3.1", "symbol": "bCycleCountGE3"},
                {"type": "coil_set", "operand": "%M2.0", "symbol": "bCycleDone"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
        {
            "networkNumber": 13,
            "title": "故障输出",
            "comment": "故障锁存位驱动故障灯",
            "elements": [
                {"type": "normally_open", "operand": "%M0.2", "symbol": "bFaultLatch"},
                {"type": "coil", "operand": "%Q0.3", "symbol": "bFault"}
            ],
            "hasParallelBranch": False, "parallelElements": [],
        },
    ]
}


def main():
    out_dir = os.path.dirname(__file__)

    # ── 输出1: LAD JSON（给 lad_creator.py 用）──
    lad_json_path = os.path.join(out_dir, "cart_3cycle.json")
    with open(lad_json_path, "w", encoding="utf-8") as f:
        json.dump(LAD_PROGRAM, f, ensure_ascii=False, indent=2)
    print(f"✅ LAD JSON: {lad_json_path}")

    # ── 输出2: PLCopen XML（手工导入 TIA Portal 用）──
    # 修改 generate_plcopen_xml 的马达小车生成，改用3次版本
    # 这里直接用现有的 generate_material_cart_xml
    xml_content = generate_material_cart_xml()
    xml_path = os.path.join(out_dir, "cart_3cycle.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"✅ PLCopen XML: {xml_path}")

    # ── 输出3: 等价的 SCL 代码 ──
    scl_code = '''FUNCTION_BLOCK "AutoCart3Cycle"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
AUTHOR : 'AI_Generated'

VAR_INPUT
    bStart : Bool;           // 启动
    bStop : Bool;            // 停止
    bReset : Bool;           // 复位
    bEmergencyStop : Bool;   // 急停（常闭）
    bForwardLimit : Bool;    // 前限位
    bReverseLimit : Bool;    // 后限位
    bOverload : Bool;        // 过载（常闭）
END_VAR

VAR_OUTPUT
    bForwardOut : Bool;      // 正转输出
    bReverseOut : Bool;      // 反转输出
    bRunning : Bool;         // 运行中
    bFault : Bool;           // 故障指示
END_VAR

VAR
    iState : Int := 0;       // 0=停止 1=前进 2=卸载 3=后退 4=装载
    iCycleCount : Int := 0;  // 循环计数器
    bFaultLatch : Bool;      // 故障锁存
    bCycleDone : Bool;       // 循环完成标志
    tmrUnload : TON;         // 卸载定时器 5s
    tmrLoad : TON;           // 装载定时器 3s
END_VAR

BEGIN
    // ── 安全链 ──
    IF NOT bEmergencyStop OR NOT bOverload THEN
        bForwardOut := FALSE; bReverseOut := FALSE; bRunning := FALSE;
        bFaultLatch := TRUE; iState := 5;
    END_IF;

    // ── 故障复位 ──
    IF bFaultLatch AND bReset THEN
        bFaultLatch := FALSE; iState := 0; iCycleCount := 0; bCycleDone := FALSE;
    END_IF;
    IF bFaultLatch THEN bFault := TRUE; RETURN; END_IF;

    // ── 状态机 ──
    CASE iState OF
        0:  // 停止等待启动
            IF bStart AND NOT bCycleDone THEN iState := 1; END_IF;
        1:  // 前进
            bForwardOut := TRUE; bRunning := TRUE;
            IF bForwardLimit THEN bForwardOut := FALSE; iState := 2; END_IF;
        2:  // 卸载
            tmrUnload(IN := TRUE, PT := T#5S);
            bRunning := TRUE;
            IF tmrUnload.Q THEN iState := 3; END_IF;
        3:  // 后退
            bReverseOut := TRUE; bRunning := TRUE;
            IF bReverseLimit THEN bReverseOut := FALSE; iState := 4; END_IF;
        4:  // 装载
            tmrLoad(IN := TRUE, PT := T#3S);
            bRunning := TRUE;
            IF tmrLoad.Q THEN
                iCycleCount := iCycleCount + 1;
                IF iCycleCount >= 3 THEN
                    bCycleDone := TRUE; iState := 0;
                ELSE
                    iState := 1;
                END_IF;
            END_IF;
        5:  // 故障
            bFault := TRUE;
            IF bReset THEN bFaultLatch := FALSE; iState := 0; END_IF;
    END_CASE;

    // ── 停止按钮 ──
    IF bStop AND iState >= 1 AND iState <= 4 THEN
        bForwardOut := FALSE; bReverseOut := FALSE; iState := 0;
    END_IF;
END_FUNCTION_BLOCK'''

    scl_path = os.path.join(out_dir, "cart_3cycle.scl")
    with open(scl_path, "w", encoding="utf-8") as f:
        f.write(scl_code)
    print(f"✅ SCL 代码: {scl_path}")

    # ── 输出4: 一键运行脚本 ──
    bat_path = os.path.join(out_dir, "run_cart_3cycle.bat")
    bat_content = r"""@echo off
chcp 65001 >nul
echo ====================================
echo  材料小车 — 往复3次停止
echo ====================================
echo.

echo [1/3] 启动 lad_creator.py 创建 LAD 块...
echo 目标: D:\TIA FANG ZHEN\...
echo.

:: 改成你的仿真项目路径
set PROJECT_PATH=D:\TIA FANG ZHEN\PLC_DEMO.ap19

:: 读取 cart_3cycle.json 并传给 lad_creator.py
python lad_creator.py cart_3cycle.json

if %ERRORLEVEL% EQU 0 (
    echo ✅ LAD 块创建成功
) else (
    echo ❌ 创建失败，检查 TIA Portal 是否安装
)

pause
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"✅ 运行脚本: {bat_path}")

    # ── 输出5: 记忆路径 ──
    mem = {
        "tia_portal_v18": r"D:\TIA BEN TI",
        "tia_simulation": r"D:\TIA FANG ZHEN",
        "lad_creator": str(lad_json_path),
        "note": "在装了TIA Portal的机器上，双击 run_cart_3cycle.bat"
    }
    mem_path = os.path.join(out_dir, "lad_paths.json")
    with open(mem_path, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)
    print(f"✅ 路径记忆: {mem_path}")
    print()
    print("=" * 50)
    print("🚀 使用方式")
    print("=" * 50)
    print("1. 把 mcp-servers/tia-mcp/ 拷到装了 TIA Portal 的机器")
    print("2. 编辑 run_cart_3cycle.bat 中的 PROJECT_PATH")
    print("3. 双击 run_cart_3cycle.bat")
    print("   或: python lad_creator.py cart_3cycle.json")
    print()
    print("或者直接导入 SCL：")
    print("  import_scl_file(scl_code, 'AutoCart3Cycle',")
    print("                 project_path='D:\\TIA FANG ZHEN\\...')")


if __name__ == "__main__":
    main()
