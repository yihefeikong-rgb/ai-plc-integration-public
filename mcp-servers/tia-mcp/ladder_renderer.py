"""
SCL → 梯形图 (Ladder Diagram) SVG 渲染器

输入: LadderProgram JSON（AI 双生生成输出的格式）
输出: SVG 格式的梯形图可视化

使用: python ladder_renderer.py --input sample.json --output ladder.svg
      python ladder_renderer.py --demo  (生成示例)
"""

import json, math, sys, os
from xml.sax.saxutils import escape as xml_escape

# ─── 样式常量 ───────────────────────────────────────────
STYLE = {
    "bg": "#ffffff",
    "rail": "#1a1a2e",
    "rail_width": 3,
    "wire": "#333333",
    "wire_width": 1.5,
    "text": "#1a1a2e",
    "text_size": 12,
    "header_size": 14,
    "title_size": 16,
    "comment_size": 11,
    "comment_color": "#666666",
    "contact_off": "#e74c3c",
    "contact_on": "#27ae60",
    "contact_normal": "#333",
    "coil_off": "#e74c3c",
    "coil_on": "#27ae60",
    "coil_normal": "#333",
    "block_fill": "#f0f4f8",
    "block_stroke": "#4a5568",
    "highlight_line": "#eef2f7",
    "font_family": "monospace, 'Courier New'",
    "rung_height": 52,
    "rail_margin": 20,
    "left_rail_x": 60,
    "right_rail_margin": 40,
    "rung_label_width": 80,
    "symbol_spacing": 48,
}

# ─── SVG 构造器 ────────────────────────────────────────

class SVGBuilder:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.lines = []
        self.defs = []

    def add_def(self, svg):
        self.defs.append(svg)

    def rect(self, x, y, w, h, fill=None, stroke=None, rx=0):
        attrs = f'x="{x}" y="{y}" width="{w}" height="{h}"'
        if rx: attrs += f' rx="{rx}"'
        if fill: attrs += f' fill="{fill}"'
        if stroke: attrs += f' stroke="{stroke}"'
        self.lines.append(f'<rect {attrs}/>')

    def line(self, x1, y1, x2, y2, color=None, width=None):
        c = color or STYLE["wire"]
        w = width or STYLE["wire_width"]
        self.lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                          f'stroke="{c}" stroke-width="{w}"/>')

    def text(self, x, y, text, size=None, color=None, anchor="middle", bold=False):
        s = size or STYLE["text_size"]
        c = color or STYLE["text"]
        fw = "bold" if bold else "normal"
        tx = xml_escape(str(text))
        self.lines.append(f'<text x="{x}" y="{y}" font-size="{s}" fill="{c}" '
                          f'text-anchor="{anchor}" dominant-baseline="central" '
                          f'font-family="{STYLE["font_family"]}" font-weight="{fw}">'
                          f'{tx}</text>')

    def contact(self, x, y, name="", address="", negated=False, closed=False, state=None):
        """画一个触点符号"""
        r = 10
        cx, cy = x, y
        color = STYLE["contact_normal"]
        if state is True: color = STYLE["contact_on"]
        elif state is False: color = STYLE["contact_off"]

        if negated or closed:
            # 常闭触点 |/|
            self.line(cx - r, cy, cx - 3, cy, color, 2)
            self.line(cx + 3, cy, cx + r, cy, color, 2)
            # 斜线
            self.line(cx - 4, cy - 6, cx + 4, cy + 6, color, 2.5)
            # 圆圈
            self.lines.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="none" '
                              f'stroke="{color}" stroke-width="1.5"/>')
        else:
            # 常开触点 | |
            self.line(cx - r, cy, cx - 3, cy, color, 2)
            self.line(cx + 3, cy, cx + r, cy, color, 2)
            # 两条竖线
            self.line(cx - 3, cy - 5, cx - 3, cy + 5, color, 1.5)
            self.line(cx + 3, cy - 5, cx + 3, cy + 5, color, 1.5)

        if name:
            self.text(cx, cy - 18, name, 10, color, "center")
        if address:
            self.text(cx, cy + 18, address, 9, STYLE["comment_color"], "center")

    def coil(self, x, y, name="", address="", state=None, is_set=False, is_reset=False):
        """画一个线圈符号"""
        color = STYLE["coil_normal"]
        if state is True: color = STYLE["coil_on"]
        elif state is False: color = STYLE["coil_off"]

        r = 11
        # 括号 ()
        self.lines.append(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r-2}" '
                          f'fill="none" stroke="{color}" stroke-width="1.8"/>')

        label = name
        if is_set: label += " (S)"
        elif is_reset: label += " (R)"

        if label:
            self.text(x, y, label, 10, color, "center", bold=True)
        if address:
            self.text(x, y + 18, address, 9, STYLE["comment_color"], "center")

    def timer_block(self, x, y, name, preset, elapsed="", block_type="TON"):
        """画定时器功能块"""
        w, h = 100, 44
        self.lines.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" '
                          f'fill="{STYLE["block_fill"]}" stroke="{STYLE["block_stroke"]}" '
                          f'stroke-width="1" rx="3"/>')
        self.text(x, y - 10, f"{block_type}: {name}", 10, STYLE["text"], "center", True)
        self.text(x, y + 8, f"PT={preset}", 9, STYLE["comment_color"], "center")
        if elapsed:
            self.text(x, y + 20, f"ET={elapsed}", 9, STYLE["comment_color"], "center")

    def math_block(self, x, y, operation, dest, src_a, src_b=""):
        """画数学/比较功能块"""
        w, h = 110, 40
        self.lines.append(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" '
                          f'fill="{STYLE["block_fill"]}" stroke="{STYLE["block_stroke"]}" '
                          f'stroke-width="1" rx="3"/>')
        self.text(x, y - 8, operation, 11, STYLE["text"], "center", True)
        self.text(x, y + 8, f"{dest} = {src_a}{','+src_b if src_b else ''}", 9, STYLE["comment_color"], "center")

    def branch_arrow(self, x, y, direction="up"):
        """画并联分支的连接箭头/弧线"""
        r = 8
        if direction == "up":
            self.line(x, y, x, y - r, STYLE["wire"], 1.5)
            self.line(x - 4, y - r + 2, x, y - r, STYLE["wire"], 1.5)
            self.line(x + 4, y - r + 2, x, y - r, STYLE["wire"], 1.5)
        else:
            self.line(x, y, x, y + r, STYLE["wire"], 1.5)
            self.line(x - 4, y + r - 2, x, y + r, STYLE["wire"], 1.5)
            self.line(x + 4, y + r - 2, x, y + r, STYLE["wire"], 1.5)

    def rung_number(self, x, y, num):
        """梯级编号"""
        self.lines.append(f'<circle cx="{x}" cy="{y}" r="10" fill="#e2e8f0" '
                          f'stroke="#94a3b8" stroke-width="1"/>')
        self.text(x, y, str(num), 11, "#475569", "center", True)

    def network_title(self, x, y, title):
        """梯级标题"""
        self.text(x, y, title, 12, STYLE["text"], "start", True)

    def build(self):
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}" '
            f'style="background:{STYLE["bg"]}">'
        ]
        if self.defs:
            parts.append(f'<defs>{"".join(self.defs)}</defs>')
        parts.extend(self.lines)
        parts.append('</svg>')
        return '\n'.join(parts)


# ─── 渲染引擎 ─────────────────────────────────────────

class LadderRenderer:
    """将 LadderProgram JSON 渲染为 SVG"""

    def __init__(self, program: dict):
        self.program = program
        self.networks = program.get("networks", [])
        self.builder = None
        self.canvas_w = 900
        self.canvas_h = 200

    def render(self) -> str:
        """主渲染方法"""
        margin_top = 60
        margin_bottom = 30
        total_height = margin_top + margin_bottom

        # 第一遍：计算总高度
        for nw in self.networks:
            rungs = nw.get("rungs", [])
            total_height += self._rung_height(nw)

        self.canvas_h = max(400, total_height + 40)
        self.builder = SVGBuilder(self.canvas_w, self.canvas_h)

        # 画背景
        self.builder.rect(0, 0, self.canvas_w, self.canvas_h, STYLE["bg"])

        y = margin_top

        # 画标题
        block_name = self.program.get("blockName", "Unnamed")
        version = self.program.get("version", "")
        author = self.program.get("author", "AI Generated")
        title = f'FB "{block_name}"'
        if version: title += f"  V{version}"
        self.builder.text(self.canvas_w / 2, 22, title, STYLE["title_size"], STYLE["text"], "center", True)
        self.builder.text(self.canvas_w / 2, 42, f"Author: {author}", STYLE["comment_size"], STYLE["comment_color"], "center")

        # 画左右电源轨
        left_x = STYLE["left_rail_x"]
        right_x = self.canvas_w - STYLE["right_rail_margin"]

        self.builder.line(left_x, margin_top - 10, left_x, total_height - margin_bottom + 10,
                          STYLE["rail"], STYLE["rail_width"])
        self.builder.line(right_x, margin_top - 10, right_x, total_height - margin_bottom + 10,
                          STYLE["rail"], STYLE["rail_width"])

        # 渲染每个梯级
        for i, nw in enumerate(self.networks):
            rungs = nw.get("rungs", [])
            rh = self._rung_height(nw)
            rung_cy = y + rh / 2

            # 交替行背景
            if i % 2 == 0:
                self.builder.rect(STYLE["left_rail_x"], y, right_x - STYLE["left_rail_x"], rh,
                                  STYLE["highlight_line"])

            # 梯级编号
            self.builder.rung_number(STYLE["left_rail_x"] - 30, rung_cy, i + 1)

            # 梯级标题
            title = nw.get("title", "")
            if title:
                self.builder.network_title(right_x + 15, rung_cy, title)

            # 左轨到第一个元素的连线
            first_x = self._elements_start_x(rungs)
            if first_x > left_x + 10:
                self.builder.line(left_x, rung_cy, first_x - STYLE["symbol_spacing"] / 2, rung_cy)

            # 渲染当前梯级的元素
            self._render_rungs(rungs, rung_cy, left_x, right_x)

            # 右轨连线
            last_x = self._elements_end_x(rungs)
            if last_x > 0 and last_x + STYLE["symbol_spacing"] / 2 < right_x:
                self.builder.line(last_x + STYLE["symbol_spacing"] / 2, rung_cy, right_x, rung_cy)

            # 注释
            comment = nw.get("comment", "")
            if comment:
                self.builder.text(right_x + 15, rung_cy + 16, comment,
                                  STYLE["comment_size"], STYLE["comment_color"], "start")

            y += rh

        return self.builder.build()

    def _rung_height(self, network: dict) -> int:
        return STYLE["rung_height"]

    def _elements_start_x(self, rungs: list) -> int:
        if not rungs or not rungs[0]:
            return 0
        return STYLE["left_rail_x"] + STYLE["symbol_spacing"]

    def _elements_end_x(self, rungs: list) -> int:
        """计算梯级最右元素位置"""
        if not rungs or not rungs[0]:
            return 0
        return STYLE["left_rail_x"] + len(rungs[0]) * STYLE["symbol_spacing"] + 40

    def _render_rungs(self, rungs: list, cy: int, left_x: int, right_x: int):
        """渲染梯级的行（可含并联分支）"""
        base_x = STYLE["left_rail_x"] + STYLE["symbol_spacing"]

        if not rungs:
            return

        # 简单的单行渲染
        row = rungs[0]
        x = base_x
        for elem in row:
            self._render_element(elem, x, cy)
            x += STYLE["symbol_spacing"]

        # 如果有并联分支（多行）
        if len(rungs) > 1:
            branch_gap = 14
            base_cy = cy
            for branch_idx, branch_row in enumerate(rungs[1:], 1):
                by = base_cy + branch_idx * branch_gap
                # 分支起点连接
                bx = base_x
                for elem in branch_row:
                    self._render_element(elem, bx, by)
                    bx += STYLE["symbol_spacing"]

    def _render_element(self, elem: dict, x: int, y: int):
        """渲染一个梯形图元素"""
        t = elem.get("type", "")
        name = elem.get("symbol", elem.get("name", ""))
        addr = elem.get("address", "") or elem.get("operand", "")

        if t in ("normally_open", "contact_no"):
            self.builder.contact(x, y, name, addr, negated=False)
        elif t in ("normally_closed", "contact_nc"):
            self.builder.contact(x, y, name, addr, negated=True)
        elif t in ("coil",):
            self.builder.coil(x, y, name, addr)
        elif t == "coil_set":
            self.builder.coil(x, y, name, addr, is_set=True)
        elif t == "coil_reset":
            self.builder.coil(x, y, name, addr, is_reset=True)
        elif t in ("timer_on", "timer_off", "timer_pulse"):
            preset = elem.get("preset", "T#0S")
            self.builder.timer_block(x, y, name, preset, block_type=elem.get("type", "TON"))
        elif t in ("counter_up", "counter_down"):
            preset = elem.get("preset", "0")
            self.builder.math_block(x, y, elem.get("type", "CTU"), name, f"PV={preset}")
        elif t in ("compare_eq", "compare_gt", "compare_lt", "compare_ge", "compare_le"):
            a = elem.get("operandA", "")
            b = elem.get("operandB", "")
            self.builder.math_block(x, y, t.replace("_", " ").upper(), name, a, b)
        elif t in ("math_add", "math_sub", "math_mul", "math_div"):
            dest = elem.get("dest", "")
            a = elem.get("operandA", "")
            b = elem.get("operandB", "")
            op_map = {"math_add": "ADD", "math_sub": "SUB", "math_mul": "MUL", "math_div": "DIV"}
            self.builder.math_block(x, y, op_map.get(t, t), dest, a, b)
        elif t == "move":
            dest = elem.get("dest", "")
            src = elem.get("source", "")
            self.builder.math_block(x, y, "MOVE", f"{src} → {dest}")
        else:
            # 未知元素：画一个问号框
            self.builder.rect(x-20, y-12, 40, 24, "#fff0f0", "#e74c3c", 3)
            self.builder.text(x, y, f"?{t}", 10, "#e74c3c", "center", True)

    def to_html(self, svg_content: str) -> str:
        """将 SVG 嵌入 HTML 页面"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>梯形图 - {self.program.get("blockName", "Unnamed")}</title>
<style>
  body {{ background: #f5f5f5; font-family: sans-serif; padding: 20px; }}
  .ladder-container {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                       padding: 20px; overflow-x: auto; }}
  .block-info {{ margin-bottom: 16px; padding: 12px 16px; background: #f8fafc;
                 border-left: 4px solid #3b82f6; border-radius: 4px; }}
  .block-info h2 {{ margin: 0 0 4px 0; font-size: 18px; }}
  .block-info p {{ margin: 0; color: #666; font-size: 13px; }}
  .legend {{ display: flex; gap: 20px; margin-top: 12px; font-size: 12px; color: #555; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
</style>
</head>
<body>
<div class="block-info">
  <h2>📐 {self.program.get("blockName", "梯形图")}</h2>
  <p>变量: {len(self.program.get("variables",{}).get("inputs",[]))} 输入 · 
            {len(self.program.get("variables",{}).get("outputs",[]))} 输出 · 
            {len(self.program.get("variables",{}).get("local",[]))} 本地</p>
  <p>网络数: {len(self.program.get("networks",[]))}</p>
</div>
<div class="ladder-container">
{svg_content}
</div>
</body>
</html>"""


# ─── 示例生成 ─────────────────────────────────────────

def create_motor_control_sample() -> dict:
    """基于电机控制 SCL 模板生成等效的 LAD 示例"""
    return {
        "blockName": "MotorControl",
        "version": "0.1",
        "author": "AI Generated",
        "variables": {
            "inputs": [
                {"name": "bEmergencyStop", "type": "Bool", "address": "%I0.0"},
                {"name": "bStartForward", "type": "Bool", "address": "%I0.1"},
                {"name": "bStartReverse", "type": "Bool", "address": "%I0.2"},
                {"name": "bStop", "type": "Bool", "address": "%I0.3"},
                {"name": "bOverload", "type": "Bool", "address": "%I0.4"},
                {"name": "bReset", "type": "Bool", "address": "%I0.5"},
            ],
            "outputs": [
                {"name": "bForwardOut", "type": "Bool", "address": "%Q0.0"},
                {"name": "bReverseOut", "type": "Bool", "address": "%Q0.1"},
                {"name": "bFault", "type": "Bool", "address": "%Q0.2"},
            ],
            "local": [
                {"name": "bSafetyOK", "type": "Bool"},
                {"name": "bFaultLatch", "type": "Bool"},
            ]
        },
        "networks": [
            {
                "networkNumber": 1,
                "title": "急停互锁",
                "comment": "急停信号为 FALSE 时切断所有输出",
                "rungs": [
                    [
                        {"type": "normally_closed", "operand": "%I0.0", "symbol": "bEmergencyStop"},
                        {"type": "coil", "operand": "%M0.0", "symbol": "bSafetyOK"}
                    ]
                ]
            },
            {
                "networkNumber": 2,
                "title": "正转控制（自保持电路）",
                "comment": "启动自保持，互锁反转，受急停保护",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%I0.1", "symbol": "bStartForward"},
                        {"type": "normally_closed", "operand": "%I0.3", "symbol": "bStop"},
                        {"type": "normally_open", "operand": "%M0.0", "symbol": "bSafetyOK"},
                        {"type": "normally_closed", "operand": "%M0.2", "symbol": "bRunReverse"},
                        {"type": "coil", "operand": "%Q0.0", "symbol": "bForwardOut"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%Q0.0", "symbol": "bForwardOut"}
                    ]
                ]
            },
            {
                "networkNumber": 3,
                "title": "反转控制（自保持电路）",
                "comment": "启动自保持，互锁正转，受急停保护",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%I0.2", "symbol": "bStartReverse"},
                        {"type": "normally_closed", "operand": "%I0.3", "symbol": "bStop"},
                        {"type": "normally_open", "operand": "%M0.0", "symbol": "bSafetyOK"},
                        {"type": "normally_closed", "operand": "%Q0.0", "symbol": "bForwardOut"},
                        {"type": "coil", "operand": "%Q0.1", "symbol": "bReverseOut"}
                    ],
                    [
                        {"type": "normally_open", "operand": "%Q0.1", "symbol": "bReverseOut"}
                    ]
                ]
            },
            {
                "networkNumber": 4,
                "title": "正反转互锁保护",
                "comment": "防止正反转同时导通",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%Q0.0", "symbol": "bForwardOut"},
                        {"type": "normally_closed", "operand": "%Q0.1", "symbol": "bReverseOut"},
                        {"type": "coil", "operand": "%M0.1", "symbol": "bForwardSafe"}
                    ]
                ]
            },
            {
                "networkNumber": 5,
                "title": "故障检测与锁定",
                "comment": "过载触发故障，需手动复位",
                "rungs": [
                    [
                        {"type": "normally_closed", "operand": "%I0.4", "symbol": "bOverload"},
                        {"type": "normally_open", "operand": "%M0.3", "symbol": "bFaultLatch"},
                        {"type": "coil", "operand": "%Q0.2", "symbol": "bFault"}
                    ]
                ]
            },
            {
                "networkNumber": 6,
                "title": "故障复位",
                "comment": "复位按钮清除故障锁定",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%I0.5", "symbol": "bReset"},
                        {"type": "normally_open", "operand": "%Q0.2", "symbol": "bFault"},
                        {"type": "coil_set", "operand": "%M0.3", "symbol": "bFaultLatch", "dest": "FALSE"}
                    ]
                ]
            },
            {
                "networkNumber": 7,
                "title": "运行反馈超时定时器",
                "comment": "启动后 5s 内无反馈则报故障",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%Q0.0", "symbol": "bForwardOut"},
                        {"type": "normally_closed", "operand": "%I0.6", "symbol": "bRunFeedback"},
                        {"type": "timer_on", "symbol": "tmrFeedback", "preset": "T#5S", "operand": "%T0"}
                    ]
                ]
            },
            {
                "networkNumber": 8,
                "title": "故障触发（定时器输出）",
                "comment": "反馈超时触发故障锁定",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%T0", "symbol": "tmrFeedback.Q"},
                        {"type": "coil_set", "operand": "%M0.3", "symbol": "bFaultLatch"}
                    ]
                ]
            },
        ]
    }


def create_conveyor_sample() -> dict:
    """传送带控制梯形图示例——带多段速"""
    return {
        "blockName": "ConveyorControl",
        "version": "0.1",
        "author": "AI Generated",
        "variables": {
            "inputs": [
                {"name": "bStart", "type": "Bool", "address": "%I0.0"},
                {"name": "bStop", "type": "Bool", "address": "%I0.1"},
                {"name": "bEmergencyStop", "type": "Bool", "address": "%I0.2"},
                {"name": "bSensorEntry", "type": "Bool", "address": "%I0.3"},
                {"name": "bSensorExit", "type": "Bool", "address": "%I0.4"},
                {"name": "bSpeedSelect", "type": "Bool", "address": "%I0.5"},
            ],
            "outputs": [
                {"name": "bMotorOut", "type": "Bool", "address": "%Q0.0"},
                {"name": "bSpeedHigh", "type": "Bool", "address": "%Q0.1"},
                {"name": "iCycleCount", "type": "Int", "address": "%MW10"},
            ],
        },
        "networks": [
            {
                "networkNumber": 1,
                "title": "急停 + 启动总电路",
                "rungs": [
                    [
                        {"type": "normally_closed", "operand": "%I0.2", "symbol": "bEmergencyStop"},
                        {"type": "normally_open", "operand": "%I0.0", "symbol": "bStart"},
                        {"type": "normally_open", "operand": "%Q0.0", "symbol": "bMotorOut"},
                        {"type": "normally_closed", "operand": "%I0.1", "symbol": "bStop"},
                        {"type": "coil", "operand": "%Q0.0", "symbol": "bMotorOut"}
                    ]
                ]
            },
            {
                "networkNumber": 2,
                "title": "速度选择（高/低速）",
                "rungs": [
                    [
                        {"type": "normally_open", "operand": "%Q0.0", "symbol": "bMotorOut"},
                        {"type": "normally_open", "operand": "%I0.5", "symbol": "bSpeedSelect"},
                        {"type": "coil", "operand": "%Q0.1", "symbol": "bSpeedHigh"}
                    ]
                ]
            },
        ]
    }


# ─── CartGen JSON → Renderer 适配 ─────────────────────

def from_cartgen_spec(spec: dict) -> dict:
    """将 CartGen LadderSpec JSON 转换为 Renderer 内部格式"""
    interface = spec.get("interface", {})

    # 构建 operand → 物理地址映射
    addr_map = {}
    for v in interface.get("inputs", []):
        addr_map[v["name"]] = v.get("address", "")
    for v in interface.get("outputs", []):
        addr_map[v["name"]] = v.get("address", "")
    for v in interface.get("local", []):
        addr_map[v["name"]] = v.get("address", "")

    variables = {
        "inputs": [{"name": v["name"], "type": v.get("type", "Bool"),
                     "address": v.get("address", "")}
                   for v in interface.get("inputs", [])],
        "outputs": [{"name": v["name"], "type": v.get("type", "Bool"),
                      "address": v.get("address", "")}
                    for v in interface.get("outputs", [])],
        "local": [{"name": v["name"], "type": v.get("type", "Bool")}
                  for v in interface.get("local", [])],
    }

    # 构建 operand → name 映射
    name_map = {}
    for v in interface.get("inputs", []):
        name_map[v["name"]] = v["name"]
    for v in interface.get("outputs", []):
        name_map[v["name"]] = v["name"]
    for v in interface.get("local", []):
        name_map[v["name"]] = v["name"]

    networks = []
    for i, net in enumerate(spec.get("networks", [])):
        rung = []
        for elem in net.get("elements", []):
            op = elem.get("operand", "")
            rung.append({
                "type": elem.get("type", "normally_open"),
                "operand": op,
                "symbol": name_map.get(op, op),
                "address": addr_map.get(op, ""),  # 物理地址（可选）
            })
        networks.append({
            "networkNumber": i + 1,
            "title": net.get("title", f"Network {i+1}"),
            "comment": net.get("comment", ""),
            "rungs": [rung],
        })

    return {
        "blockName": spec.get("blockName", "Unnamed"),
        "version": "0.1",
        "author": "CartGen",
        "variables": variables,
        "networks": networks,
    }


def render_svg_preview(spec: dict) -> str:
    """从 CartGen LadderSpec JSON 直接渲染 SVG 字符串"""
    internal = from_cartgen_spec(spec)
    renderer = LadderRenderer(internal)
    return renderer.render()


def render_svg_preview_html(spec: dict) -> str:
    """从 CartGen LadderSpec JSON 渲染完整 HTML 页面"""
    internal = from_cartgen_spec(spec)
    renderer = LadderRenderer(internal)
    svg = renderer.render()
    return renderer.to_html(svg)


# ─── CLI ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SCL 梯形图 SVG 渲染器")
    parser.add_argument("--input", "-i", help="LAD JSON 输入文件路径")
    parser.add_argument("--output", "-o", default="ladder.svg", help="SVG 输出路径")
    parser.add_argument("--demo", "-d", action="store_true", help="生成电机控制示例")
    parser.add_argument("--conveyor", action="store_true", help="生成传送带示例")
    parser.add_argument("--html", action="store_true", help="同时输出 HTML 页面")
    args = parser.parse_args()

    if args.demo:
        program = create_motor_control_sample()
        print("📋 使用电机控制示例")
    elif args.conveyor:
        program = create_conveyor_sample()
        print("📋 使用传送带示例")
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            program = json.load(f)
    else:
        # 默认显示电机示例
        program = create_motor_control_sample()
        print("📋 使用电机控制示例（默认）")

    renderer = LadderRenderer(program)
    svg = renderer.render()

    # 输出 SVG
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"✅ SVG 已保存: {args.output} ({os.path.getsize(args.output)} bytes)")

    if args.html:
        html = renderer.to_html(svg)
        html_path = args.output.replace(".svg", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ HTML 已保存: {html_path}")


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════
# V2 集成适配 — AST → LayoutEngine → SVGRendererV2
# ═══════════════════════════════════════════════════════════

def render_v2_from_ast(block):
    """
    完整 V2 管线：LadderBlock (AST) → LayoutEngine → RenderTree → SVG

    Args:
        block: lad_ast.LadderBlock 实例

    Returns:
        SVG 字符串
    """
    from layout_engine import LayoutEngine
    from svg_renderer_v2 import SVGRendererV2

    engine = LayoutEngine()
    render_block = engine.layout(block)
    renderer = SVGRendererV2(render_block)
    return renderer.render()


def render_v2_from_json(json_path: str) -> str:
    """
    完整 V2 管线：JSON 文件 → AST → LayoutEngine → RenderTree → SVG

    Args:
        json_path: LadderSpec JSON 文件路径

    Returns:
        SVG 字符串
    """
    import json
    from lad_ast import LadderBlock

    with open(json_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    block = LadderBlock.from_dict(spec)
    return render_v2_from_ast(block)
