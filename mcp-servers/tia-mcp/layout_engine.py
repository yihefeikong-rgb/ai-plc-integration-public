"""
LayoutEngine — 梯形图布局引擎

将 LadderBlock (AST) 转换为 RenderBlock (RenderTree)，
为每个梯形图元素分配列/行并计算像素坐标。

职责（唯一）：
1. 列号分配（串联元素行走列，分支元素拆分行）
2. 行号分配（主路径=0，分支路径=1+）
3. 像素坐标计算（col/row → x/y）
4. 画布尺寸计算
5. 分支起止位置计算

不负责：
- SVG 生成（那是 SVGRendererV2 的事）
- 分支嵌套（V1 不支持，会抛 NotImplementedError）
"""

from __future__ import annotations
from typing import Optional

from lad_ast import (
    LadderBlock, LadderNetwork, LadderRung, LadderElement,
    Contact, Coil, Branch, EmptyElement,
    Timer, Counter, Comparator, MathElement, MoveElement, BoxCall,
    OperandRef,
)
from render_tree import (
    RenderBlock, RenderNetwork, RenderRow, RenderElement, RenderBranch,
    COLUMN_WIDTH, ROW_HEIGHT, BRANCH_ROW_GAP,
    LEFT_RAIL_MARGIN, RIGHT_RAIL_MARGIN,
    TOP_MARGIN, BOTTOM_MARGIN, NETWORK_GAP,
)


class LayoutEngineError(Exception):
    """LayoutEngine 专用异常"""
    pass


class LayoutEngine:
    """布局引擎 — AST → RenderBlock"""

    def layout(self, block: LadderBlock) -> RenderBlock:
        """主入口：将整个 LadderBlock 布局为 RenderBlock"""
        networks = []
        for nw in block.networks:
            networks.append(self._layout_network(nw))

        total_width = max((n.canvas_width for n in networks), default=800)
        total_height = sum(n.canvas_height + NETWORK_GAP for n in networks) + TOP_MARGIN + BOTTOM_MARGIN

        # 统一所有 network 的宽度
        for n in networks:
            n.canvas_width = total_width

        return RenderBlock(
            block_name=block.name,
            block_number=block.number,
            networks=networks,
            total_width=total_width,
            total_height=total_height,
        )

    def _layout_network(self, network: LadderNetwork) -> RenderNetwork:
        """布局一个 Network"""
        elements = network.rung.elements
        if not elements:
            return RenderNetwork(
                index=network.index,
                title=network.title,
                comment=network.comment,
                canvas_width=LEFT_RAIL_MARGIN + COLUMN_WIDTH + RIGHT_RAIL_MARGIN,
                canvas_height=ROW_HEIGHT,
                left_rail_x=LEFT_RAIL_MARGIN,
                right_rail_x=LEFT_RAIL_MARGIN + COLUMN_WIDTH + RIGHT_RAIL_MARGIN,
            )

        # ── 第一遍：分配列/行到每个元素 ──
        main_path: list[tuple[str, LadderElement, int]] = []  # (elem_type, element, col)
        branches: list[dict] = []  # {start_col, end_col, paths: list[list[tuple]]}
        extra_rows = 0  # 分支行数
        col = 0

        for elem in elements:
            if isinstance(elem, EmptyElement):
                continue

            if isinstance(elem, Branch):
                # 单层 Branch — 分支
                if not elem.paths:
                    raise LayoutEngineError(f"Network {network.index}: Branch with empty paths")
                # 检查嵌套分支
                for path in elem.paths:
                    for sub_el in path:
                        if isinstance(sub_el, Branch):
                            raise NotImplementedError(
                                f"Network {network.index}: Nested branches not supported in V1"
                            )

                # 计算此分支的最长路径长度
                max_path_len = max(len(path) for path in elem.paths)
                branch_start_col = col
                branch_end_col = branch_start_col + max_path_len

                # 构造分支数据
                branch_paths = []
                for path in elem.paths:
                    path_items = []
                    for sub_el in path:
                        if isinstance(sub_el, EmptyElement):
                            continue
                        et = self._element_type(sub_el)
                        path_items.append((et, sub_el))
                    branch_paths.append(path_items)
                    extra_rows += 1  # 每个分支路径一行

                branches.append({
                    "start_col": branch_start_col,
                    "end_col": branch_end_col,
                    "paths": branch_paths,
                })

                col = branch_end_col  # 分支后继续
            else:
                et = self._element_type(elem)
                main_path.append((et, elem, col))
                col += 1

        total_cols = col

        # ── 第二遍：计算像素坐标 ──
        total_rows = 1 + extra_rows  # 主路径 + 分支行

        net_canvas_width = LEFT_RAIL_MARGIN + total_cols * COLUMN_WIDTH + RIGHT_RAIL_MARGIN
        net_canvas_height = total_rows * ROW_HEIGHT + extra_rows * BRANCH_ROW_GAP

        # 构建行
        rows = []
        render_branches = []

        # 主路径行 (row 0)
        main_row_y = ROW_HEIGHT / 2  # 相对于 network 顶部
        main_elements = []
        for (et, elem, element_col) in main_path:
            x = LEFT_RAIL_MARGIN + element_col * COLUMN_WIDTH + COLUMN_WIDTH / 2
            render_elem = self._make_render_element(et, elem, element_col, 0, x, main_row_y)
            main_elements.append(render_elem)
        rows.append(RenderRow(row_index=0, y_center=main_row_y, elements=main_elements))

        # 分支行 (row 1+) — 修复分支叠加 bug：正确累加 BRANCH_ROW_GAP
        branch_row_offset = 0  # 累计偏移
        for br_idx, branch_data in enumerate(branches):
            for path_idx, path_items in enumerate(branch_data["paths"]):
                branch_row_index = 1 + br_idx + path_idx
                # 修复：每个分支行累加 ROW_HEIGHT + BRANCH_ROW_GAP
                branch_y = TOP_MARGIN + (branch_row_offset + 1) * ROW_HEIGHT + branch_row_offset * BRANCH_ROW_GAP + ROW_HEIGHT / 2
                branch_row_offset += 1
                br_elements = []
                for i, (et, elem) in enumerate(path_items):
                    element_col = branch_data["start_col"] + i
                    x = LEFT_RAIL_MARGIN + element_col * COLUMN_WIDTH + COLUMN_WIDTH / 2
                    render_elem = self._make_render_element(et, elem, element_col, branch_row_index, x, branch_y)
                    br_elements.append(render_elem)
                rows.append(RenderRow(row_index=branch_row_index, y_center=branch_y, elements=br_elements))

                # 计算分支几何
                start_x = LEFT_RAIL_MARGIN + branch_data["start_col"] * COLUMN_WIDTH + COLUMN_WIDTH / 2
                end_x = LEFT_RAIL_MARGIN + branch_data["end_col"] * COLUMN_WIDTH + COLUMN_WIDTH / 2
                render_branches.append(RenderBranch(
                    start_col=branch_data["start_col"],
                    end_col=branch_data["end_col"],
                    start_x=start_x,
                    end_x=end_x,
                    main_row_y=main_row_y,
                    branch_rows=[branch_row_index],
                ))

        return RenderNetwork(
            index=network.index,
            title=network.title,
            comment=network.comment,
            rows=rows,
            branches=render_branches,
            canvas_width=net_canvas_width,
            canvas_height=net_canvas_height,
            left_rail_x=LEFT_RAIL_MARGIN,
            right_rail_x=LEFT_RAIL_MARGIN + total_cols * COLUMN_WIDTH + RIGHT_RAIL_MARGIN,
        )

    # ─── 辅助方法 ──────────────────────────────────────────

    @staticmethod
    def _element_type(elem: LadderElement) -> str:
        """获取元素的渲染类型字符串"""
        if isinstance(elem, Contact):
            return "contact_nc" if elem.type == "normally_closed" else "contact_no"
        if isinstance(elem, Coil):
            return elem.type  # "coil", "coil_set", "coil_reset"
        if isinstance(elem, Timer):
            return "timer"
        if isinstance(elem, Counter):
            return "counter"
        if isinstance(elem, Comparator):
            return "comparator"
        if isinstance(elem, MathElement):
            return "math"
        if isinstance(elem, MoveElement):
            return "move"
        if isinstance(elem, BoxCall):
            return "box"
        return "unknown"

    @staticmethod
    def _make_render_element(
        et: str, elem: LadderElement,
        col: int, row: int, x: float, y: float
    ) -> RenderElement:
        """从 AST 元素和位置创建 RenderElement"""
        extra = {}
        operand_name = ""
        address = ""

        if isinstance(elem, (Contact, Coil)):
            operand_name = elem.operand.name
            address = elem.operand.address
        elif isinstance(elem, Timer):
            operand_name = elem.instance
            extra["timer_type"] = elem.timer_type.value
            extra["preset"] = elem.preset
            if elem.q_operand:
                extra["q_operand"] = elem.q_operand.name
            if elem.et_operand:
                extra["et_operand"] = elem.et_operand.name
        elif isinstance(elem, Counter):
            operand_name = elem.instance
            extra["counter_type"] = elem.counter_type.value
            extra["preset"] = elem.preset
            if elem.q_operand:
                extra["q_operand"] = elem.q_operand.name
        elif isinstance(elem, Comparator):
            operand_name = f"{elem.operand_a.name} {elem.op.value} {elem.operand_b.name}"
            extra["op"] = elem.op.value
        elif isinstance(elem, MathElement):
            operand_name = f"{elem.dest.name} = {elem.src_a.name}"
            extra["op"] = elem.op.value
            if elem.src_b:
                operand_name += f", {elem.src_b.name}"
        elif isinstance(elem, MoveElement):
            operand_name = f"{elem.src.name} → {elem.dest.name}"
        elif isinstance(elem, BoxCall):
            operand_name = elem.instance
            extra["box_type"] = elem.box_type
            extra["inputs"] = elem.inputs
            extra["outputs"] = elem.outputs

        return RenderElement(
            col=col,
            row=row,
            x_center=x,
            y_center=y,
            elem_type=et,
            symbol_name=operand_name,
            address=address,
            extra=extra,
        )
