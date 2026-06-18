"""
SVGRendererV2 — 梯形图 SVG 渲染器 V2

纯渲染层，从 RenderTree 预计算数据生成 SVG。
不计算任何坐标 — 坐标来自 LayoutEngine。

数据流：
    RenderBlock (来自 LayoutEngine)
        ↓
    SVGRendererV2
        ↓
    SVG string

对比 V1 (ladder_renderer.py)：
    V1: 自行解析 JSON 字典 + 计算坐标 + 渲染 SVG（混合）
    V2: 纯渲染，坐标从 LayoutEngine 获取（分层）
"""

from __future__ import annotations
from xml.sax.saxutils import escape as xml_escape

from render_tree import (
    RenderBlock, RenderNetwork, RenderRow, RenderElement, RenderBranch,
    STYLE,
    COLUMN_WIDTH, ROW_HEIGHT, LEFT_RAIL_MARGIN,
)


# ═══════════════════════════════════════════════════════════
# SVGBuilderV2 — 底层 SVG 绘图原语（暗色主题）
# ═══════════════════════════════════════════════════════════

class SVGBuilderV2:
    """SVG 构建器 — 提供绘图原语（暗色主题专用）"""

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.lines = []
        self.defs = []

    def add_def(self, svg: str):
        self.defs.append(svg)

    def rect(self, x, y, w, h, fill=None, stroke=None, rx=0):
        attrs = f'x="{x}" y="{y}" width="{w}" height="{h}"'
        if rx:
            attrs += f' rx="{rx}"'
        if fill:
            attrs += f' fill="{fill}"'
        if stroke:
            attrs += f' stroke="{stroke}"'
        self.lines.append(f'<rect {attrs}/>')

    def line(self, x1, y1, x2, y2, color=None, width=None):
        c = color or STYLE["wire"]
        w = width or STYLE["wire_width"]
        self.lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{c}" stroke-width="{w}"/>'
        )

    def circle(self, cx, cy, r, fill="none", stroke=None, stroke_width=1):
        c = stroke or STYLE["wire"]
        self.lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="{fill}" stroke="{c}" stroke-width="{stroke_width}"/>'
        )

    def ellipse(self, cx, cy, rx, ry, fill="none", stroke=None, stroke_width=1.5):
        c = stroke or STYLE["wire"]
        self.lines.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
            f'fill="{fill}" stroke="{c}" stroke-width="{stroke_width}"/>'
        )

    def text(self, x, y, text, size=None, color=None, anchor="middle", bold=False):
        s = size or STYLE["label_size"]
        c = color or STYLE["text"]
        fw = "bold" if bold else "normal"
        tx = xml_escape(str(text))
        self.lines.append(
            f'<text x="{x}" y="{y}" font-size="{s}" fill="{c}" '
            f'text-anchor="{anchor}" dominant-baseline="central" '
            f'font-family="{STYLE["font_family"]}" font-weight="{fw}">'
            f'{tx}</text>'
        )

    def g(self, attrs: str = ""):
        """开启一个 <g> 组"""
        self.lines.append(f"<g {attrs}>")

    def g_end(self):
        """关闭最近的 </g>"""
        self.lines.append("</g>")

    def build(self) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}" '
            f'style="background:{STYLE["bg"]};font-family:{STYLE["font_family"]}">'
        ]
        if self.defs:
            parts.append(f"<defs>{''.join(self.defs)}</defs>")
        parts.extend(self.lines)
        parts.append("</svg>")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# Element Renderers — 单个元素绘制
# ═══════════════════════════════════════════════════════════

# All element functions accept (builder, elem, row_y)
# row_y = global SVG y-coordinate (base_y + row.y_center)

def _render_contact(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制触点（常开/常闭）"""
    x, y = elem.x_center, row_y
    is_nc = elem.elem_type == "contact_nc"
    cs = STYLE["contact_nc" if is_nc else "contact_no"]
    r = 16  # enlarged from 10

    builder.line(x - r, y, x - 3, y, cs["stroke"], 2)
    builder.line(x + 3, y, x + r, y, cs["stroke"], 2)

    if is_nc:
        builder.line(x - 6, y - 8, x + 6, y + 8, cs["stroke"], 2.5)
        builder.circle(x, y, 4, fill="none", stroke=cs["stroke"], stroke_width=1.5)
    else:
        builder.line(x - 4, y - 7, x - 4, y + 7, cs["stroke"], 2)
        builder.line(x + 4, y - 7, x + 4, y + 7, cs["stroke"], 2)

    if elem.symbol_name:
        builder.text(x, y - 24, elem.symbol_name, 10, cs["text"], "center")
    if elem.address:
        builder.text(x, y + 24, elem.address, 9, STYLE["text_dim"], "center")


def _render_coil(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制线圈"""
    x, y = elem.x_center, row_y
    et = elem.elem_type
    cs_map = {
        "coil": STYLE["coil"],
        "coil_set": STYLE["coil_set"],
        "coil_reset": STYLE["coil_reset"],
    }
    cs = cs_map.get(et, STYLE["coil"])
    rx, ry = 16, 13  # enlarged from (11, 9)

    builder.line(x - rx, y, x - rx + 3, y, cs["stroke"], 2)
    builder.line(x + rx - 3, y, x + rx, y, cs["stroke"], 2)
    builder.ellipse(x, y, rx, ry, fill="none", stroke=cs["stroke"], stroke_width=1.8)

    label = elem.symbol_name
    if et == "coil_set":
        label += " (S)"
    elif et == "coil_reset":
        label += " (R)"
    if label:
        builder.text(x, y, label, 10, cs["text"], "center", bold=True)
    if elem.address:
        builder.text(x, y + 24, elem.address, 9, STYLE["text_dim"], "center")


def _render_timer(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制定时器功能块"""
    x, y = elem.x_center, row_y
    extra = elem.extra
    w, h = 120, 56  # enlarged from (100, 44)
    block_type = extra.get("timer_type", "TON")
    preset = extra.get("preset", "T#0S")
    instance = elem.symbol_name

    builder.rect(x - w / 2, y - h / 2, w, h, STYLE["block_fill"], STYLE["block_stroke"], rx=3)
    builder.text(x, y - 12, f"{block_type}: {instance}", 10, STYLE["text"], "center", True)
    builder.text(x, y + 10, f"PT={preset}", 9, STYLE["text_dim"], "center")
    if extra.get("q_operand"):
        builder.text(x + w / 2 - 8, y - h / 2 + 8, extra["q_operand"], 8, STYLE["text_dim"], "end")
    if extra.get("et_operand"):
        builder.text(x + w / 2 - 8, y + h / 2 - 6, extra["et_operand"], 8, STYLE["text_dim"], "end")


def _render_counter(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制计数器功能块"""
    x, y = elem.x_center, row_y
    extra = elem.extra
    w, h = 120, 56  # enlarged
    ctype = extra.get("counter_type", "CTU")
    preset = extra.get("preset", "0")

    builder.rect(x - w / 2, y - h / 2, w, h, STYLE["block_fill"], STYLE["block_stroke"], rx=3)
    builder.text(x, y - 12, f"{ctype}: {elem.symbol_name}", 10, STYLE["text"], "center", True)
    builder.text(x, y + 10, f"PV={preset}", 9, STYLE["text_dim"], "center")


def _render_box(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制通用功能块"""
    x, y = elem.x_center, row_y
    extra = elem.extra
    w, h = 140, 60  # enlarged
    box_type = extra.get("box_type", "FB")
    instance = elem.symbol_name

    builder.rect(x - w / 2, y - h / 2, w, h, STYLE["block_fill"], STYLE["block_stroke"], rx=3)
    builder.text(x, y - 12, f"{box_type}", 11, STYLE["text"], "center", True)
    if instance:
        builder.text(x, y + 12, f'"{instance}"', 10, STYLE["text_dim"], "center")

    inputs = extra.get("inputs", {})
    outputs = extra.get("outputs", {})
    for i, (pin_name, pin_val) in enumerate(inputs.items()):
        py = y - h / 2 + 14 + i * 12
        builder.text(x - w / 2 + 6, py, f"{pin_name}={pin_val}", 8, STYLE["text_dim"], "start")
    for i, (pin_name, pin_val) in enumerate(outputs.items()):
        py = y - h / 2 + 14 + i * 12
        builder.text(x + w / 2 - 6, py, f"{pin_name}={pin_val}", 8, STYLE["text_dim"], "end")


def _render_math_block(builder: SVGBuilderV2, elem: RenderElement, row_y: float):
    """绘制算术/比较/传送指令的通用矩形框"""
    x, y = elem.x_center, row_y
    w, h = 130, 50  # enlarged
    op = elem.extra.get("op", elem.elem_type.upper())

    builder.rect(x - w / 2, y - h / 2, w, h, STYLE["block_fill"], STYLE["block_stroke"], rx=3)
    builder.text(x, y, op, 11, STYLE["text"], "center", True)
    if elem.symbol_name:
        builder.text(x, y + 16, elem.symbol_name, 8, STYLE["text_dim"], "center")


# ═══════════════════════════════════════════════════════════
# SVGRendererV2 — 主渲染器
# ═══════════════════════════════════════════════════════════

class SVGRendererV2:
    """
    SVG Renderer V2 — 纯渲染引擎。

    输入：RenderBlock（来自 LayoutEngine，坐标已预计算）
    输出：SVG 字符串
    原则：不计算任何坐标，只读取 RenderTree 数据。
    """

    def __init__(self, render_block: RenderBlock):
        self.block = render_block
        self._builder: SVGBuilderV2 | None = None

    def render(self) -> str:
        """主入口：生成完整 SVG"""
        w = self.block.total_width
        h = self.block.total_height
        self._builder = SVGBuilderV2(w, h)

        # 背景
        self._builder.rect(0, 0, w, h, STYLE["bg"])

        # 标题
        title = self.block.block_name or "LAD Program"
        self._builder.text(w / 2, 18, title, STYLE["title_size"], STYLE["text_accent"], "center", True)
        sub = f"Block #{self.block.block_number} · {len(self.block.networks)} Network(s)"
        self._builder.text(w / 2, 38, sub, STYLE["header_size"], STYLE["text_dim"], "center")

        # 逐 Network 渲染
        y_offset = 60.0
        for net in self.block.networks:
            net_h = net.canvas_height
            self._render_network(net, y_offset)
            y_offset += net_h + 12

        return self._builder.build()

    def _render_network(self, net: RenderNetwork, base_y: float):
        """渲染一个 Network"""
        b = self._builder
        lx = net.left_rail_x
        rx = net.right_rail_x

        # 行高亮（交替背景）
        if net.index % 2 == 1:
            b.rect(lx, base_y, rx - lx, net.canvas_height, STYLE["highlight_line"])

        # 电源轨
        rail_top = base_y - 10
        rail_bot = base_y + net.canvas_height + 10
        b.line(lx, rail_top, lx, rail_bot, STYLE["rail"], STYLE["rail_width"])
        b.line(rx, rail_top, rx, rail_bot, STYLE["rail"], STYLE["rail_width"])

        # Network 标题
        if net.title:
            b.text(lx - 36, base_y + ROW_HEIGHT / 2, str(net.index), 11, STYLE["text"], "center")

        # 标题文字
        if net.title:
            b.text(rx + 12, base_y + ROW_HEIGHT / 2, net.title, STYLE["header_size"], STYLE["text_accent"], "start", True)
        if net.comment:
            b.text(rx + 12, base_y + ROW_HEIGHT / 2 + 18, net.comment, 10, STYLE["text_dim"], "start")

        # draw rows and branches
        self._render_rows(net, base_y)
        self._render_branches(net, base_y)

    def _render_rows(self, net: RenderNetwork, base_y: float):
        """渲染所有行（导线 + 元素）"""
        b = self._builder
        lx = net.left_rail_x
        rx = net.right_rail_x

        for row in net.rows:
            row_y = base_y + row.y_center
            elements = row.elements

            if not elements:
                continue

            # 左轨到第一个元素的导线
            first_x = elements[0].x_center
            if first_x > lx + 10:
                b.line(lx, row_y, first_x - COLUMN_WIDTH / 2, row_y)

            # 元素间的导线 + 元素绘制
            for i, elem in enumerate(elements):
                # 导线：前一个元素到当前元素
                if i > 0:
                    prev_x = elements[i - 1].x_center
                    curr_x = elem.x_center
                    mid = (prev_x + curr_x) / 2
                    b.line(prev_x + COLUMN_WIDTH / 4, row_y, curr_x - COLUMN_WIDTH / 4, row_y)

                # 绘制元素
                self._render_element(elem, row_y)

            # 最后一个元素到右轨
            last_x = elements[-1].x_center
            if last_x + COLUMN_WIDTH / 2 < rx:
                b.line(last_x + COLUMN_WIDTH / 4, row_y, rx, row_y)

    def _render_branches(self, net: RenderNetwork, base_y: float):
        """渲染分支连接线"""
        b = self._builder
        for br in net.branches:
            main_y = base_y + br.main_row_y
            for branch_row_idx in br.branch_rows:
                # 找到对应的分支行 y
                for row in net.rows:
                    if row.row_index == branch_row_idx:
                        branch_y = base_y + row.y_center

                        # 竖线：主路径 → 分支行（起点）
                        b.line(br.start_x, main_y, br.start_x, branch_y)

                        # 竖线：分支行 → 主路径（汇合点）
                        b.line(br.end_x, main_y, br.end_x, branch_y)

                        # 如果有元素在分支行，在元素间画导线
                        if row.elements:
                            for i, elem in enumerate(row.elements):
                                if i > 0:
                                    prev_x = row.elements[i - 1].x_center
                                    curr_x = elem.x_center
                                    b.line(prev_x + COLUMN_WIDTH / 4, branch_y, curr_x - COLUMN_WIDTH / 4, branch_y)

                            # 分支行两端导线到竖线
                            first_x = row.elements[0].x_center
                            last_x = row.elements[-1].x_center
                            if first_x > br.start_x + 5:
                                b.line(br.start_x, branch_y, first_x - COLUMN_WIDTH / 4, branch_y)
                            if last_x + COLUMN_WIDTH / 4 < br.end_x:
                                b.line(last_x + COLUMN_WIDTH / 4, branch_y, br.end_x, branch_y)
                        break

    def _render_element(self, elem: RenderElement, row_y: float):
        """分派到具体元素绘制函数"""
        b = self._builder

        # 添加 data-* 属性支持点击
        attrs = f'data-type="{xml_escape(elem.elem_type)}" data-operand="{xml_escape(elem.symbol_name)}"'
        b.g(attrs)

        if elem.elem_type in ("contact_no", "contact_nc"):
            _render_contact(b, elem, row_y)
        elif elem.elem_type in ("coil", "coil_set", "coil_reset"):
            _render_coil(b, elem, row_y)
        elif elem.elem_type == "timer":
            _render_timer(b, elem, row_y)
        elif elem.elem_type == "counter":
            _render_counter(b, elem, row_y)
        elif elem.elem_type == "box":
            _render_box(b, elem, row_y)
        elif elem.elem_type in ("comparator", "math", "move"):
            _render_math_block(b, elem, row_y)
        else:
            # 未知元素：问号框
            b.rect(elem.x_center - 20, elem.y_center - 12, 40, 24, "#fff0f0", "#e74c3c", 3)
            b.text(elem.x_center, elem.y_center, f"?{elem.elem_type}", 10, "#e74c3c", "center", True)

        b.g_end()




