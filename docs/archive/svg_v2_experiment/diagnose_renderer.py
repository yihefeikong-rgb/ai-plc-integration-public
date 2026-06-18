#!/usr/bin/env python
"""SVG Renderer Diagnosis — analyze current rendering state"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

from lad_ast import (
    LadderBlock, LadderNetwork, LadderRung, LadderElement,
    Contact, Coil, Branch, OperandRef, InterfaceVariable,
)
from layout_engine import LayoutEngine
from svg_renderer_v2 import SVGRendererV2

# Build MotorControl with branch
block = LadderBlock(
    name="MotorControl",
    number=1,
    inputs=[
        InterfaceVariable(name="bStart", data_type="Bool", address="%I0.0"),
        InterfaceVariable(name="bStop", data_type="Bool", address="%I0.1"),
        InterfaceVariable(name="bEmergency", data_type="Bool", address="%I0.2"),
        InterfaceVariable(name="bOverload", data_type="Bool", address="%I0.3"),
    ],
    outputs=[
        InterfaceVariable(name="qMotor", data_type="Bool", address="%Q0.0"),
    ],
    networks=[
        LadderNetwork(
            index=1,
            title="Motor Start/Stop with Self-Holding",
            comment="Standard motor self-holding circuit",
            rung=LadderRung(
                elements=[
                    Contact(
                        type="normally_open",
                        operand=OperandRef(name="bStart", address="%I0.0"),
                    ),
                    Branch(
                        paths=[
                            [
                                Contact(
                                    type="normally_open",
                                    operand=OperandRef(name="qMotor", address="%Q0.0"),
                                ),
                            ],
                        ],
                    ),
                    Contact(
                        type="normally_closed",
                        operand=OperandRef(name="bStop", address="%I0.1"),
                    ),
                    Contact(
                        type="normally_open",
                        operand=OperandRef(name="bEmergency", address="%I0.2"),
                    ),
                    Contact(
                        type="normally_closed",
                        operand=OperandRef(name="bOverload", address="%I0.3"),
                    ),
                    Coil(
                        type="coil",
                        operand=OperandRef(name="qMotor", address="%Q0.0"),
                    ),
                ],
            ),
        ),
    ],
)

# Run pipeline
engine = LayoutEngine()
rb = engine.layout(block)
renderer = SVGRendererV2(rb)
svg = renderer.render()

# Part A: LayoutEngine coordinates
print("="*70)
print("PART A: LAYOUT ENGINE COORDINATES")
print("="*70)

for net in rb.networks:
    print(f"\nNetwork {net.index}: '{net.title}'")
    print(f"  Canvas: {net.canvas_width:.0f} x {net.canvas_height:.0f}")
    print(f"  Left rail: {net.left_rail_x:.0f}, Right rail: {net.right_rail_x:.0f}")
    for row in net.rows:
        print(f"  Row {row.row_index} center_y={row.y_center:.1f}:")
        for e in row.elements:
            print(f"    {e.symbol_name:<20} col={e.col} row={e.row} x={e.x_center:<8.1f} y={e.y_center:<8.1f} type={e.elem_type}")
    if net.branches:
        for br in net.branches:
            print(f"  Branch: start_col={br.start_col} end_col={br.end_col}")
            print(f"          start_x={br.start_x:.1f} end_x={br.end_x:.1f}")
            print(f"          main_row_y={br.main_row_y:.1f} branch_rows={br.branch_rows}")

# Part B: SVG actual y-coordinates
print("\n" + "="*70)
print("PART B: SVG ACTUAL Y-COORDINATES")
print("="*70)

y_vals = re.findall(r'y(?:1|2)?=\"(\d+\.?\d*)\"', svg)
all_ys = sorted(set(float(y) for y in y_vals))
print(f"All unique y values in SVG: {all_ys}")

y_26_count = sum(1 for y in y_vals if float(y) == 26.0)
print(f"\nFixed y=26 occurrences: {y_26_count}")

# Find element label y-positions
label_ys = re.findall(r'<text.*? y=\"(\d+\.?\d*)\".*?>(b[A-Z]|q[A-Z])', svg)
print(f"\nElement label y-positions:")
for y, name in label_ys[:10]:
    print(f"  {name} at y={y}")

# Part C: Bug Diagnosis
print("\n" + "="*70)
print("PART C: BUG DIAGNOSIS")
print("="*70)

# Wire continuity check
wire_lines = re.findall(r'<line.*? y1=\"(\d+\.?\d*)\".*? y2=\"(\d+\.?\d*)\".*?>', svg)
horiz_ys = set()
for y1, y2 in wire_lines:
    if y1 == y2:
        horiz_ys.add(float(y1))
print(f"\nHorizontal wire y-values: {sorted(horiz_ys)}")

# Network offset check
print(f"\nNetwork 0 y_offset in SVGRendererV2.render(): starts at 60")
print(f"Row 0 center_y from layout: {rb.networks[0].rows[0].y_center}")
print(f"So element y in SVG = 60 + {rb.networks[0].rows[0].y_center} = {60 + rb.networks[0].rows[0].y_center}")

# Check if elements use network-relative or global y
# Look for the 'y=26' pattern which would indicate elements are
# using row.y_center directly without adding base_y
print(f"\nDiagnosis: Checking if elements correctly add base_y offset")
print(f"  If elements appear at y=26, they're using raw row.y_center w/o base_y")
print(f"  If elements appear at y=86, they're correctly adding base_y+row.y_center")

# Show SVG snippet around first contact
idx = svg.find('data-type="contact_no"')
if idx > 0:
    chunk = svg[max(0, idx - 100):idx + 400]
    y_near = re.findall(r' y[12]?=\"(\d+\.?\d*)\"', chunk)
    print(f"\nFirst contact SVG: y-values nearby = {y_near}")

# Save diagnosis SVG
diag_path = os.path.join(os.path.dirname(__file__), "diagnosis_before.svg")
with open(diag_path, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"\nDiagnosis SVG saved: {diag_path}")
