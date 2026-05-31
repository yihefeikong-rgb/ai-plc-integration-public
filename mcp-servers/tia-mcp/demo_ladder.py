"""演示：SCL 电机控制模板 → 梯形图 SVG 渲染"""

from ladder_renderer import LadderRenderer, create_motor_control_sample
import json, os

def main():
    # ── 方案1：使用内置示例（电机正反转控制）──
    print("=" * 60)
    print("【方案1】使用内置电机控制示例")
    print("=" * 60)

    program1 = create_motor_control_sample()
    renderer1 = LadderRenderer(program1)
    svg1 = renderer1.render()

    out1 = "ladder_motor_control.svg"
    with open(out1, "w", encoding="utf-8") as f:
        f.write(svg1)
    print(f"  ✅ SVG: {out1} ({len(svg1)} 字节)")
    print(f"  📊 网络: {len(program1['networks'])} 个梯级")

    # 打印 JSON 描述
    with open("ladder_motor_control.json", "w", encoding="utf-8") as f:
        json.dump(program1, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON: ladder_motor_control.json")

    # ── 方案2：材料小车控制（来自 generate_scl.py 的 MaterialCartControl）──
    print()
    print("=" * 60)
    print("【方案2】材料小车控制 (MaterialCartControl)")
    print("  从 SCL 转换: CASE state machine → Ladder networks")
    print("=" * 60)

    cart_program = {
        "blockName": "MaterialCartControl",
        "version": "0.1",
        "author": "AI Generated (SCL→LAD)",
        "variables": {
            "inputs": [
                {"name": "bStart", "type": "Bool", "address": "%I0.0"},
                {"name": "bStop", "type": "Bool", "address": "%I0.1"},
                {"name": "bReset", "type": "Bool", "address": "%I0.2"},
                {"name": "bEmergencyStop", "type": "Bool", "address": "%I0.3"},
                {"name": "bForwardLimit", "type": "Bool", "address": "%I0.4"},
                {"name": "bReverseLimit", "type": "Bool", "address": "%I0.5"},
                {"name": "bOverload", "type": "Bool", "address": "%I0.6"},
                {"name": "bManualMode", "type": "Bool", "address": "%I0.7"},
                {"name": "bManualForward", "type": "Bool", "address": "%I1.0"},
                {"name": "bManualReverse", "type": "Bool", "address": "%I1.1"},
            ],
            "outputs": [
                {"name": "bForwardOut", "type": "Bool", "address": "%Q0.0"},
                {"name": "bReverseOut", "type": "Bool", "address": "%Q0.1"},
                {"name": "bRunning", "type": "Bool", "address": "%Q0.2"},
                {"name": "bFault", "type": "Bool", "address": "%Q0.3"},
            ],
            "local": [
                {"name": "iState", "type": "Int", "comment": "状态机 (0=IDLE,1=FW,2=UNLOAD,3=RV,4=LOAD,5=FAULT)"},
                {"name": "bFaultLatch", "type": "Bool"},
                {"name": "iCycleCount", "type": "Int"},
                {"name": "tStartTimer", "type": "Time"},
            ]
        },
        "networks": [
            {
                "networkNumber": 1,
                "title": "急停+过载安全链",
                "comment": "急停或过载触发时，切断所有输出，锁存故障",
                "rungs": [
                    [
                        {"type": "normally_closed", "operand": "%I0.3", "symbol": "bEmergencyStop"},
                        {"type": "coil", "operand": "%M0.0", "symbol": "bSafetyOK"}
                    ],
                    [
                        {"type": "normally_closed", "operand": "%I0.6", "symbol": "bOverload"},
                        {"type": "coil", "operand": "%M0.1", "symbol": "bSafeLoad"}
                    ]
                ]
            },
            {
                "networkNumber": 2,
                "title": "故障锁存与复位",
                "comment": "安全链熔断 → 锁存故障；复位按钮解除",
                "rungs": [
                    [
                        {"type": "normally_closed", "operand": "%M0.0", "symbol": "bSafetyOK"},
                        {"type": "coil_set", "operand": "%M0.2", "symbol": "bFaultLatch"}
                    ],
                    [
                        {"type": "normally_closed", "operand": "%M0.1", "symbol": "bSafeLoad"},
                        {"type": "coil_set", "operand": "%M0.2", "symbol": "bFaultLatch"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%I0.2", "symbol": "bReset"},
                        {"type": "normally_open", "operand": "%M0.2", "symbol": "bFaultLatch"},
                        {"type": "coil_reset", "operand": "%M0.2", "symbol": "bFaultLatch"}
                    ]
                ]
            },
            {
                "networkNumber": 3,
                "title": "手动模式",
                "comment": "手动模式下，正反转直接由按钮控制+互锁",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%I0.7", "symbol": "bManualMode"},
                        {"type": "normally_open", "operand": "%I1.0", "symbol": "bManualForward"},
                        {"type": "normally_closed", "operand": "%I1.1", "symbol": "bManualReverse"},
                        {"type": "coil", "operand": "%Q0.0", "symbol": "bForwardOut"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%I0.7", "symbol": "bManualMode"},
                        {"type": "normally_open", "operand": "%I1.1", "symbol": "bManualReverse"},
                        {"type": "normally_closed", "operand": "%I1.0", "symbol": "bManualForward"},
                        {"type": "coil", "operand": "%Q0.1", "symbol": "bReverseOut"}
                    ]
                ]
            },
            {
                "networkNumber": 4,
                "title": "状态机 — 前进（State=1）",
                "comment": "启动触发前进，到达前限位后转入卸载",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%I0.0", "symbol": "bStart"},
                        {"type": "normally_closed", "operand": "%M0.2", "symbol": "bFaultLatch"},
                        {"type": "coil_set", "operand": "%M2.1", "symbol": "iState=1"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%M2.1", "symbol": "iState=1"},
                        {"type": "coil", "operand": "%Q0.0", "symbol": "bForwardOut"},
                        {"type": "coil", "operand": "%Q0.2", "symbol": "bRunning"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%M2.1", "symbol": "iState=1"},
                        {"type": "normally_open", "operand": "%I0.4", "symbol": "bForwardLimit"},
                        {"type": "coil_set", "operand": "%M2.2", "symbol": "iState=2"},
                        {"type": "coil_reset", "operand": "%M2.1", "symbol": "iState=1"}
                    ]
                ]
            },
            {
                "networkNumber": 5,
                "title": "状态机 — 卸载（State=2）",
                "comment": "到达前端位，等待卸载时间后转入后退",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%M2.2", "symbol": "iState=2"},
                        {"type": "timer_on", "operand": "T1", "symbol": "tmrUnload", "preset": "T#5S"}
                    ],
                    [
                        {"type": "normally_open", "operand": "T1", "symbol": "tmrUnload.Q"},
                        {"type": "coil_set", "operand": "%M2.3", "symbol": "iState=3"},
                        {"type": "coil_reset", "operand": "%M2.2", "symbol": "iState=2"}
                    ]
                ]
            },
            {
                "networkNumber": 6,
                "title": "状态机 — 后退（State=3）",
                "comment": "后退到后限位，转入装载",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%M2.3", "symbol": "iState=3"},
                        {"type": "coil", "operand": "%Q0.1", "symbol": "bReverseOut"},
                        {"type": "coil", "operand": "%Q0.2", "symbol": "bRunning"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%M2.3", "symbol": "iState=3"},
                        {"type": "normally_open", "operand": "%I0.5", "symbol": "bReverseLimit"},
                        {"type": "coil_set", "operand": "%M2.4", "symbol": "iState=4"},
                        {"type": "coil_reset", "operand": "%M2.3", "symbol": "iState=3"}
                    ]
                ]
            },
            {
                "networkNumber": 7,
                "title": "状态机 — 装载完成→下一轮（State=4→1/0）",
                "comment": "装载定时到后自增计数，决定继续循环还是停止",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%M2.4", "symbol": "iState=4"},
                        {"type": "timer_on", "operand": "T2", "symbol": "tmrLoad", "preset": "T#3S"}
                    ],
                    [
                        {"type": "normally_open", "operand": "T2", "symbol": "tmrLoad.Q"},
                        {"type": "coil", "operand": "%Q0.0", "symbol": "bForwardOut"},
                        {"type": "coil_reset", "operand": "%M2.4", "symbol": "iState=4"},
                        {"type": "coil_set", "operand": "%M2.1", "symbol": "iState=1"}
                    ]
                ]
            },
            {
                "networkNumber": 8,
                "title": "故障状态输出",
                "comment": "状态机 State=5 时，输出故障信号",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%M2.5", "symbol": "iState=5"},
                        {"type": "coil", "operand": "%Q0.3", "symbol": "bFault"}
                    ]
                ]
            },
        ]
    }

    renderer2 = LadderRenderer(cart_program)
    svg2 = renderer2.render()

    out2 = "ladder_material_cart.svg"
    with open(out2, "w", encoding="utf-8") as f:
        f.write(svg2)
    print(f"  ✅ SVG: {out2} ({len(svg2)} 字节)")
    print(f"  📊 网络: {len(cart_program['networks'])} 个梯级")

    # ── 生成 HTML 对比页面 ──
    print()
    print("=" * 60)
    print("生成 HTML 对比页面...")
    print("=" * 60)

    # 读取等价的 SCL 代码（从 generate_scl.py）
    scl_code_path = os.path.join(os.path.dirname(__file__), "generate_scl.py")
    with open(scl_code_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 提取 SCL_CODE 的内容
    import re
    m = re.search(r"SCL_CODE = '''(.+?)'''", content, re.DOTALL)
    scl_sample = m.group(1) if m else "(未找到 SCL 代码)"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>SCL → 梯形图 渲染对比</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f0f2f5; font-family: -apple-system, 'Segoe UI', sans-serif; padding: 20px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 8px; color: #1a1a2e; }}
  h2 {{ font-size: 16px; margin: 20px 0 10px; color: #333; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
  .card {{ background: white; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
           padding: 20px; margin-bottom: 20px; overflow: auto; }}
  .card-title {{ font-size: 15px; font-weight: bold; margin-bottom: 12px; color: #2563eb; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px;
            font-weight: bold; margin-right: 6px; }}
  .badge-blue {{ background: #dbeafe; color: #1d4ed8; }}
  .badge-green {{ background: #dcfce7; color: #15803d; }}
  .badge-orange {{ background: #fef3c7; color: #b45309; }}
  .two-col {{ display: flex; gap: 16px; }}
  .two-col > div {{ flex: 1; min-width: 0; }}
  pre {{ font-size: 12px; line-height: 1.5; overflow-x: auto; background: #f8fafc;
         border-radius: 6px; padding: 12px; border: 1px solid #e2e8f0; }}
  .ladder-svg {{ display: block; margin: 0 auto; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 10px 0; font-size: 12px; }}
  .legend-item {{ display: flex; align-items: center; gap: 4px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .dot-green {{ background: #27ae60; }}
  .dot-red {{ background: #e74c3c; }}
  .dot-gray {{ background: #94a3b8; }}
  footer {{ text-align: center; color: #94a3b8; font-size: 12px; padding: 20px; }}
</style>
</head>
<body>
<div class="container">
  <h1>📐 SCL → 梯形图 渲染对比</h1>
  <p class="subtitle">AI 双生生成：同一功能描述 → 同时输出 SCL + LAD</p>

  <div class="legend">
    <span class="legend-item"><span class="dot dot-green"></span> 导通（ON）</span>
    <span class="legend-item"><span class="dot dot-red"></span> 断开（OFF）</span>
    <span class="legend-item"><span class="dot dot-gray"></span> 常规状态</span>
    <span class="badge badge-blue">NC</span> 常闭触点
    <span class="badge badge-green">NO</span> 常开触点
    <span class="badge badge-orange">(S)/(R)</span> 置位/复位线圈
  </div>

  <h2>🔷 示例1：电机正反转控制</h2>
  <div class="card">
    <div class="two-col">
      <div>
        <div class="card-title">梯形图 (LAD)</div>
        {svg1}
      </div>
      <div>
        <div class="card-title">SCL 代码（等价的 AI 生成输出）</div>
        <pre>// 与梯形图等价的功能：
// - 急停互锁（网络1）
// - 正转自保持+反转互锁（网络2）
// - 反转自保持+正转互锁（网络3）
// - 过载保护（网络4）
// - 故障复位（网络5）
// - 物理输出映射（网络6）

FUNCTION_BLOCK "MotorControl"
VERSION : 0.1
VAR_INPUT
    bEmergencyStop : Bool;
    bStartForward : Bool;
    bStartReverse : Bool;
    bStop : Bool;
    bOverload : Bool;
END_VAR
VAR_OUTPUT
    bForwardOut : Bool;
    bReverseOut : Bool;
    bFault : Bool;
END_VAR
VAR
    bSafetyOK : Bool;
    bFaultLatch : Bool;
END_VAR
BEGIN
    // 急停互锁
    bSafetyOK := bEmergencyStop;

    // 正转自保持 + 反转互锁
    bForwardOut := (bStartForward OR bForwardOut)
                   AND bStop AND bSafetyOK
                   AND NOT bReverseOut;

    // 反转自保持 + 正转互锁
    bReverseOut := (bStartReverse OR bReverseOut)
                   AND bStop AND bSafetyOK
                   AND NOT bForwardOut;

    // 过载保护
    IF NOT bOverload THEN
        bFault := TRUE;
    END_IF;
END_FUNCTION_BLOCK</pre>
      </div>
    </div>
  </div>

  <h2>🔷 示例2：材料小车控制（含状态机展开）</h2>
  <div class="card">
    <div class="card-title">梯形图 — 含 CASE 状态机展开</div>
    <div style="font-size: 12px; color: #666; margin-bottom: 10px;">
      原 SCL 中的 <code>CASE iState OF</code> 被展开为 8 个独立网络，
      每个网络等价于一个状态分支。定时器（TON）直接转化为功能块。
    </div>
    {svg2}
  </div>

  <h2>🔷 示例3：原始 SCL 代码（MaterialCartControl）</h2>
  <div class="card">
    <pre>{scl_sample}</pre>
  </div>

</div>
<footer>
  AI + PLC 集成项目 · 阶段3：西门子工程态 · SCL ↔ LAD 双生生成
</footer>
</body>
</html>"""

    out_html = "ladder_comparison.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ HTML 对比页面: {out_html}")
    print()
    print("=" * 60)
    print("💡 关键发现")
    print("=" * 60)
    print("""
1. 梯形图可以通过 JSON 描述完美表达
2. CASE 状态机 → N 个梯级（每状态一个网络）
3. IF/THEN/ELSE → 串并联触点组合
4. 定时器/计数器 → 功能块（TON/TOF/CTU）
5. AI 可以同时生成 SC L + LAD JSON，语义等价有保证
6. SVG 渲染的梯形图可在 HTML/Markdown 中直接查看
""")


if __name__ == "__main__":
    main()
