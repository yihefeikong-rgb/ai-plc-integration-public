"""
RenderTree — 布局后的梯形图渲染数据模型

LayoutEngine 的输出，SVGRendererV2 的输入。
纯数据对象，不含坐标计算逻辑。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 样式常量
# ═══════════════════════════════════════════════════════════

# 网格布局
COLUMN_WIDTH = 64          # 每列像素宽度 (enlarged for bigger contacts)
ROW_HEIGHT = 60            # 每行像素高度（主路径）(enlarged)
BRANCH_ROW_GAP = 18        # 分支行额外间距
LEFT_RAIL_MARGIN = 80      # 左轨左边距
RIGHT_RAIL_MARGIN = 40     # 右轨右边距
TOP_MARGIN = 70            # 顶部标题区高度
BOTTOM_MARGIN = 20         # 底部留白
NETWORK_GAP = 12           # Network 间间距

# SVG 颜色主题
STYLE = {
    "bg": "#1a1a2e",
    "rail": "#4a4a6a",
    "rail_width": 4,
    "wire": "#616161",
    "wire_width": 1.2,
    "text": "#e0e0e0",
    "text_dim": "#9e9e9e",
    "text_accent": "#80cbc4",
    "title_size": 14,
    "header_size": 12,
    "label_size": 10,
    "address_size": 9,
    "contact_no": {"fill": "#4fc3f7", "stroke": "#29b6f6", "text": "#e0e0e0"},
    "contact_nc": {"fill": "#ffb74d", "stroke": "#ffa726", "text": "#e0e0e0"},
    "coil": {"fill": "#81c784", "stroke": "#66bb6a", "text": "#1a1a2e"},
    "coil_set": {"fill": "#4db6ac", "stroke": "#26a69a", "text": "#1a1a2e"},
    "coil_reset": {"fill": "#ef5350", "stroke": "#e53935", "text": "#1a1a2e"},
    "block_fill": "#2a2a4a",
    "block_stroke": "#5a5a8a",
    "highlight_line": "#222244",
    "font_family": "monospace, 'Courier New'",
    "rung_badge": {"fill": "#e2e8f0", "stroke": "#94a3b8", "text": "#475569"},
}


# ═══════════════════════════════════════════════════════════
# RenderElement — 单个已定位的梯形图元素
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderElement:
    """已定位的梯形图元素，包含像素坐标和类型信息

    LayoutEngine 填充 col/row/x_center/y_center。
    SVGRendererV2 仅读取这些值绘制 SVG。
    """
    col: int = 0               # 0-based 列号
    row: int = 0               # 0=主路径, 1+=分支路径
    x_center: float = 0.0      # 像素 x 中心
    y_center: float = 0.0      # 像素 y 中心
    elem_type: str = ""        # contact_no / contact_nc / coil / coil_set / coil_reset / timer / counter / comparator / math / move / box
    symbol_name: str = ""      # 操作数符号名
    address: str = ""          # 物理地址
    extra: dict = field(default_factory=dict)  # 类型特定数据 (preset, box_type, instance, inputs, outputs, ...)


# ═══════════════════════════════════════════════════════════
# RenderBranch — 预计算的并联分支连接线几何
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderBranch:
    """并联分支的连接线几何（预计算）"""
    start_col: int = 0         # 分支起始列
    end_col: int = 0           # 分支结束列
    start_x: float = 0.0       # 分支起点 x 像素
    end_x: float = 0.0         # 分支汇合点 x 像素
    main_row_y: float = 0.0    # 主路径 y 坐标
    branch_rows: list[int] = field(default_factory=list)  # 分支行的 row 索引


# ═══════════════════════════════════════════════════════════
# RenderRow — 一行元素
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderRow:
    """水平行（主路径或分支路径）"""
    row_index: int = 0         # 0 = 主路径, 1+ = 分支路径
    y_center: float = 0.0      # 本行的 y 中心
    elements: list[RenderElement] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# RenderNetwork — 一个完整布局后的 Network
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderNetwork:
    """一个 Network 的完整布局结果"""
    index: int = 0
    title: str = ""
    comment: str = ""
    rows: list[RenderRow] = field(default_factory=list)
    branches: list[RenderBranch] = field(default_factory=list)
    canvas_width: float = 800.0
    canvas_height: float = 200.0
    left_rail_x: float = 0.0
    right_rail_x: float = 0.0


# ═══════════════════════════════════════════════════════════
# RenderBlock — 顶层布局输出
# ═══════════════════════════════════════════════════════════

@dataclass
class RenderBlock:
    """整个功能块的布局结果"""
    block_name: str = ""
    block_number: int = 0
    networks: list[RenderNetwork] = field(default_factory=list)
    total_width: float = 800.0
    total_height: float = 200.0
