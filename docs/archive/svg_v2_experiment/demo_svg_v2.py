#!/usr/bin/env python
"""
demo_svg_v2.py — SVGRendererV2 演示生成器

生成 3 个示例 SVG：
1. SimpleSeries.svg — 简单串联电路
2. ConveyorControl.svg — 传送带控制（串联）
3. MotorControl.svg — 电机自保持（含分支）

用法：
    python demo_svg_v2.py [--output-dir DIR]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from lad_ast import (
    LadderBlock, LadderNetwork, LadderRung, LadderElement,
    Contact, Coil, Branch, OperandRef, InterfaceVariable,
)
from layout_engine import LayoutEngine
from svg_renderer_v2 import SVGRendererV2


# ─── Demo 1: 简单串联 ────────────────────────────────────

def build_series() -> LadderBlock:
    """
    Network 1: Start/Stop Control
    bStart(NO) → bStop(NC) → bOverload(NC) → qMotor(COIL)
    """
    elements: list[LadderElement] = [
        Contact(type="normally_open", operand=OperandRef(name="bStart", address="%I0.0")),
        Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.1")),
        Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.2")),
        Coil(type="coil", operand=OperandRef(name="qMotor", address="%Q0.0")),
    ]
    return LadderBlock(
        name="SimpleSeries",
        number=1,
        networks=[LadderNetwork(index=1, title="Start/Stop Control", rung=LadderRung(elements=elements))],
        inputs=[
            InterfaceVariable(name="bStart", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="bStop", data_type="Bool", address="%I0.1"),
            InterfaceVariable(name="bOverload", data_type="Bool", address="%I0.2"),
        ],
        outputs=[InterfaceVariable(name="qMotor", data_type="Bool", address="%Q0.0")],
    )


# ─── Demo 2: 传送带控制 ──────────────────────────────────

def build_conveyor() -> LadderBlock:
    """
    Network 1: Conveyor Control
    iRun(NO) → iSensor(NC) → oConveyor(COIL)
    """
    elements: list[LadderElement] = [
        Contact(type="normally_open", operand=OperandRef(name="iRun", address="%I0.1")),
        Contact(type="normally_closed", operand=OperandRef(name="iSensor", address="%I0.0")),
        Coil(type="coil", operand=OperandRef(name="oConveyor", address="%Q0.0")),
    ]
    return LadderBlock(
        name="ConveyorControl",
        number=500,
        networks=[LadderNetwork(index=1, title="Conveyor Control", rung=LadderRung(elements=elements))],
        inputs=[
            InterfaceVariable(name="iSensor", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="iRun", data_type="Bool", address="%I0.1"),
        ],
        outputs=[InterfaceVariable(name="oConveyor", data_type="Bool", address="%Q0.0")],
    )


# ─── Demo 3: 电机自保持（含分支） ─────────────────────────

def build_motor() -> LadderBlock:
    """
    Network 1: Motor Forward (Self-Holding)
    bFwd(NO) → [Branch] → bStop(NC) → bOverload(NC) → bSafetyOK(NO) → qFwd(COIL)
                └→ qFwd(NO) (自保持)
    
    Network 2: Motor Reverse (Self-Holding)  
    bRev(NO) → [Branch] → bStop(NC) → bOverload(NC) → bSafetyOK(NO) → qRev(COIL)
                └→ qRev(NO) (自保持)
    """
    nw1 = LadderNetwork(
        index=1,
        title="Motor Forward Control",
        comment="Self-holding forward circuit with overload protection",
        rung=LadderRung(elements=[
            Contact(type="normally_open", operand=OperandRef(name="bFwd", address="%I0.0")),
            Branch(paths=[
                [Contact(type="normally_open", operand=OperandRef(name="qFwd", address="%Q0.0"))],
            ]),
            Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.3")),
            Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.4")),
            Contact(type="normally_open", operand=OperandRef(name="bSafetyOK", address="%M0.0")),
            Coil(type="coil", operand=OperandRef(name="qFwd", address="%Q0.0")),
        ]),
    )

    nw2 = LadderNetwork(
        index=2,
        title="Motor Reverse Control",
        comment="Self-holding reverse circuit with forward interlock",
        rung=LadderRung(elements=[
            Contact(type="normally_open", operand=OperandRef(name="bRev", address="%I0.1")),
            Branch(paths=[
                [Contact(type="normally_open", operand=OperandRef(name="qRev", address="%Q0.1"))],
            ]),
            Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.3")),
            Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.4")),
            Contact(type="normally_closed", operand=OperandRef(name="qFwd", address="%Q0.0")),  # 互锁
            Coil(type="coil", operand=OperandRef(name="qRev", address="%Q0.1")),
        ]),
    )

    return LadderBlock(
        name="MotorControl",
        number=2,
        networks=[nw1, nw2],
        inputs=[
            InterfaceVariable(name="bFwd", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="bRev", data_type="Bool", address="%I0.1"),
            InterfaceVariable(name="bStop", data_type="Bool", address="%I0.3"),
            InterfaceVariable(name="bOverload", data_type="Bool", address="%I0.4"),
        ],
        outputs=[
            InterfaceVariable(name="qFwd", data_type="Bool", address="%Q0.0"),
            InterfaceVariable(name="qRev", data_type="Bool", address="%Q0.1"),
        ],
    )


# ─── Demo 4: 定时器 + 计数器 ─────────────────────────────

def build_timer_counter() -> LadderBlock:
    """
    Network 1: On-Delay Timer
    bTrigger(NO) → timer_TON
    
    Network 2: Counter
    bCount(NO) → counter_CTU
    """
    from lad_ast import Timer, Counter, TimerType, CounterType

    nw1 = LadderNetwork(
        index=1,
        title="On-Delay Timer",
        comment="Trigger starts timer, Q output after 5s",
        rung=LadderRung(elements=[
            Contact(type="normally_open", operand=OperandRef(name="bTrigger", address="%I0.0")),
            Timer(
                timer_type=TimerType.TON,
                instance="tonDelay",
                preset="T#5S",
                q_operand=OperandRef(name="qTimerDone", address="%M0.1"),
            ),
        ]),
    )

    nw2 = LadderNetwork(
        index=2,
        title="Counter",
        comment="Count up on rising edge",
        rung=LadderRung(elements=[
            Contact(type="normally_open", operand=OperandRef(name="bCount", address="%I0.1")),
            Counter(
                counter_type=CounterType.CTU,
                instance="ctuParts",
                preset="10",
                q_operand=OperandRef(name="qCountDone", address="%M0.2"),
            ),
        ]),
    )

    return LadderBlock(
        name="TimerCounterDemo",
        number=3,
        networks=[nw1, nw2],
        inputs=[
            InterfaceVariable(name="bTrigger", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="bCount", data_type="Bool", address="%I0.1"),
        ],
        outputs=[
            InterfaceVariable(name="qTimerDone", data_type="Bool"),
            InterfaceVariable(name="qCountDone", data_type="Bool"),
        ],
    )


# ─── 渲染器 ───────────────────────────────────────────────

def render_svg(block: LadderBlock, path: str):
    """AST → SVG"""
    engine = LayoutEngine()
    render_block = engine.layout(block)
    renderer = SVGRendererV2(render_block)
    svg = renderer.render()
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    size_kb = os.path.getsize(path) / 1024
    print(f"  OK: {path} ({size_kb:.1f} KB)")


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 50)
    print("SVGRendererV2 Demo Generator")
    
    demos = [
        ("SimpleSeries.svg", build_series(), "Simple Series Circuit"),
        ("ConveyorControl.svg", build_conveyor(), "Conveyor Control"),
        ("MotorControl.svg", build_motor(), "Motor Forward/Reverse with Branch"),
        ("TimerCounterDemo.svg", build_timer_counter(), "Timer & Counter Demo"),
    ]
    
    for filename, block, desc in demos:
        print(f"\n--- {desc}")
        print(f"   Networks: {len(block.networks)}")
        total_elems = sum(len(n.rung.elements) for n in block.networks)
        print(f"   Elements: {total_elems}")
        path = os.path.join(output_dir, filename)
        render_svg(block, path)
    
    print(f"\n{'=' * 50}")
    print("All demos generated!")


if __name__ == "__main__":
    main()
