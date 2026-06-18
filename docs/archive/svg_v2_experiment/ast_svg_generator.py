"""
AST/SVG Generator — 从 LadderProgram 结构化数据生成 AST + SVG

给现有 LLM→ASCII→LadderProgram 流程增加一路输出：
  LadderProgram → LadderBlock (AST) → LayoutEngine → SVGRendererV2 → SVG

对 demo 模式（motor-start-stop, traffic-light, conveyor）有精确的 AST 构建器。
对 LLM 模式做尽力转换，失败时优雅回退返回 None。
"""

import sys, os, re, json, logging

logger = logging.getLogger(__name__)

# ── 添加 V2 管线路径 ──────────────────────────────────
V2_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp-servers", "tia-mcp")
)
if V2_DIR not in sys.path:
    sys.path.insert(0, V2_DIR)

# ── 延迟导入 ────────────────────────────────────────────
def _import_v2():
    """导入 V2 模块，失败时返回 None"""
    try:
        from lad_ast import (
            LadderBlock, LadderNetwork, LadderRung,
            Contact, Coil, Branch, EmptyElement,
            OperandRef, InterfaceVariable,
        )
        from layout_engine import LayoutEngine
        from svg_renderer_v2 import SVGRendererV2
        return (LadderBlock, LadderNetwork, LadderRung,
                Contact, Coil, Branch, EmptyElement,
                OperandRef, InterfaceVariable,
                LayoutEngine, SVGRendererV2)
    except ImportError as e:
        logger.warning(f"V2 modules not available: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# Demo AST Builders（匹配 workflow.py 的 demo_keywords）
# ═══════════════════════════════════════════════════════════

def _build_motor_start_stop(title: str = "MotorStartStop") -> dict:
    """电机启停自保持电路"""
    v2 = _import_v2()
    if not v2:
        return None
    LadderBlock, LadderNetwork, LadderRung, Contact, Coil, Branch, _, OperandRef, InterfaceVariable, LayoutEngine, SVGRendererV2 = v2
    block = LadderBlock(
        name="MotorStartStop", number=1,
        inputs=[
            InterfaceVariable(name="bStart", data_type="Bool", address="%I0.0", comment="启动按钮"),
            InterfaceVariable(name="bStop", data_type="Bool", address="%I0.1", comment="停止按钮"),
            InterfaceVariable(name="bOverload", data_type="Bool", address="%I0.2", comment="过载保护"),
        ],
        outputs=[InterfaceVariable(name="qMotor", data_type="Bool", address="%Q0.0", comment="电机输出")],
        networks=[LadderNetwork(index=1, title="启动保持电路",
            comment="启动自锁，停止按钮和过载保护断开",
            rung=LadderRung(elements=[
                Contact(type="normally_open", operand=OperandRef(name="bStart", address="%I0.0")),
                Branch(paths=[[Contact(type="normally_open", operand=OperandRef(name="qMotor", address="%Q0.0"))]]),
                Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.1")),
                Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.2")),
                Coil(type="coil", operand=OperandRef(name="qMotor", address="%Q0.0")),
            ])),
        ],
    )
    return _render(block, LayoutEngine, SVGRendererV2)


def _build_traffic_light(title: str = "TrafficLight") -> dict:
    """十字路口交通灯"""
    v2 = _import_v2()
    if not v2:
        return None
    LadderBlock, LadderNetwork, LadderRung, Contact, Coil, Branch, _, OperandRef, InterfaceVariable, LayoutEngine, SVGRendererV2 = v2
    block = LadderBlock(
        name="TrafficLight", number=2,
        inputs=[
            InterfaceVariable(name="bStart", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="bStop", data_type="Bool", address="%I0.1"),
            InterfaceVariable(name="bEmergency", data_type="Bool", address="%I0.2"),
        ],
        outputs=[
            InterfaceVariable(name="qEW_Green", data_type="Bool", address="%Q0.0"),
            InterfaceVariable(name="qEW_Yellow", data_type="Bool", address="%Q0.1"),
            InterfaceVariable(name="qNS_Green", data_type="Bool", address="%Q0.2"),
        ],
        networks=[
            LadderNetwork(index=1, title="安全控制",
                comment="急停切断所有输出", rung=LadderRung(elements=[
                    Contact(type="normally_closed", operand=OperandRef(name="bEmergency")),
                    Contact(type="normally_open", operand=OperandRef(name="bStart")),
                    Coil(type="coil_set", operand=OperandRef(name="qEW_Green")),
                ])),
        ],
    )
    return _render(block, LayoutEngine, SVGRendererV2)


def _build_conveyor(title: str = "ConveyorControl") -> dict:
    """传送带控制"""
    v2 = _import_v2()
    if not v2:
        return None
    LadderBlock, LadderNetwork, LadderRung, Contact, Coil, Branch, _, OperandRef, InterfaceVariable, LayoutEngine, SVGRendererV2 = v2
    block = LadderBlock(
        name="ConveyorControl", number=500,
        inputs=[
            InterfaceVariable(name="iRun", data_type="Bool", address="%I0.1"),
            InterfaceVariable(name="iSensor", data_type="Bool", address="%I0.0"),
        ],
        outputs=[InterfaceVariable(name="oConveyor", data_type="Bool", address="%Q0.0")],
        networks=[LadderNetwork(index=1, title="传送带控制",
            comment="Run=1 且 Sensor=0 时 Conveyor=1",
            rung=LadderRung(elements=[
                Contact(type="normally_open", operand=OperandRef(name="iRun", address="%I0.1")),
                Contact(type="normally_closed", operand=OperandRef(name="iSensor", address="%I0.0")),
                Coil(type="coil", operand=OperandRef(name="oConveyor", address="%Q0.0")),
            ])),
        ],
    )
    return _render(block, LayoutEngine, SVGRendererV2)


def _build_motor_forward_reverse(title: str = "MotorControl") -> dict:
    """电机正反转（双 Network 带分支）"""
    v2 = _import_v2()
    if not v2:
        return None
    LadderBlock, LadderNetwork, LadderRung, Contact, Coil, Branch, _, OperandRef, InterfaceVariable, LayoutEngine, SVGRendererV2 = v2
    block = LadderBlock(
        name="MotorControl", number=2,
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
        networks=[
            LadderNetwork(index=1, title="正转控制",
                comment="正转自保持，互锁反转",
                rung=LadderRung(elements=[
                    Contact(type="normally_open", operand=OperandRef(name="bFwd", address="%I0.0")),
                    Branch(paths=[[Contact(type="normally_open", operand=OperandRef(name="qFwd", address="%Q0.0"))]]),
                    Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.3")),
                    Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.4")),
                    Coil(type="coil", operand=OperandRef(name="qFwd", address="%Q0.0")),
                ])),
            LadderNetwork(index=2, title="反转控制",
                comment="反转自保持，互锁正转",
                rung=LadderRung(elements=[
                    Contact(type="normally_open", operand=OperandRef(name="bRev", address="%I0.1")),
                    Branch(paths=[[Contact(type="normally_open", operand=OperandRef(name="qRev", address="%Q0.1"))]]),
                    Contact(type="normally_closed", operand=OperandRef(name="bStop", address="%I0.3")),
                    Contact(type="normally_closed", operand=OperandRef(name="bOverload", address="%I0.4")),
                    Contact(type="normally_closed", operand=OperandRef(name="qFwd", address="%Q0.0")),
                    Coil(type="coil", operand=OperandRef(name="qRev", address="%Q0.1")),
                ])),
        ],
    )
    return _render(block, LayoutEngine, SVGRendererV2)


# ═══════════════════════════════════════════════════════════
# 通用 LLM 输出 → AST 转换（尽力而为）
# ═══════════════════════════════════════════════════════════

def _build_from_structured(structured: dict) -> dict:
    """
    从 LadderProgram 的结构化 dict 尝试构建 AST。
    解析 ASCII 代码提取元素类型和操作数。
    """
    v2 = _import_v2()
    if not v2:
        return None
    (LadderBlock, LadderNetwork, LadderRung,
     Contact, Coil, Branch, EmptyElement,
     OperandRef, InterfaceVariable,
     LayoutEngine, SVGRendererV2) = v2

    variables = structured.get("variables", [])
    networks_data = structured.get("networks", [])
    if not networks_data:
        return None

    # 构建变量名 → 地址映射
    var_map = {}
    for v in variables:
        name = v.get("name", "")
        addr = v.get("address", "")
        if name:
            var_map[name] = addr

    ast_networks = []
    for nw_data in networks_data:
        code = nw_data.get("code", "")
        title = nw_data.get("title", "")
        comment = nw_data.get("comment", "")
        elements = _parse_ascii_elements(code, var_map, Contact, Coil, Branch, EmptyElement, OperandRef)
        if not elements:
            continue
        ast_networks.append(LadderNetwork(
            index=nw_data.get("number", len(ast_networks) + 1),
            title=title,
            comment=comment,
            rung=LadderRung(elements=elements),
        ))

    if not ast_networks:
        return None

    block = LadderBlock(
        name=structured.get("title", "GeneratedProgram"),
        number=1,
        networks=ast_networks,
    )
    return _render(block, LayoutEngine, SVGRendererV2)


def _parse_ascii_elements(code: str, var_map: dict,
                          Contact, Coil, Branch, EmptyElement, OperandRef):
    """
    从 ASCII 梯形图代码中提取元素列表。
    支持格式：
      - | | 或 --| |-- 常开触点
      - |/| 或 --|/|-- 常闭触点
      - ( ) 或 --( )-- 线圈
      - (S) 置位线圈
      - (R) 复位线圈
      - 行文本中出现的变量名
    """
    lines = code.split("\n")
    all_text = " ".join(lines)

    # 提取所有变量名（出现在触点/线圈符号附近的单词）
    element_types = []
    found_names = set()

    # 扫描每行
    for line in lines:
        # 检测常开触点 --| |-- 或 | |
        if "|" in line and "|" in line.split("/", 1)[0]:
            # 提取 | | 附近的变量名（通常在符号后面或上一行）
            pass

        # 检测常闭触点 |/|
        if "/" in line and "|" in line:
            pass

    # 简化：提取所有看起来像变量名的单词
    var_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_.]*)\b")
    matches = var_pattern.findall(all_text)
    for name in matches:
        # 过滤掉符号字符和短单词
        if len(name) >= 2 and not re.match(r"^[-+=|/()]+$", name):
            found_names.add(name)

    # 按出现顺序构建元素
    # 检测常开/常闭和线圈
    elements = []
    has_branch = False
    
    # 检查是否有并联分支（多行 rungs 模式或 "+" 连接符）
    has_branch = "+" in all_text and "|" in all_text
    
    # 按行解析
    # 第 1 行通常是主路径：变量名 → 触点 → 线圈
    # 后续行可能是分支路径
    
    # 简化：为每个变量名分配元素类型
    name_order = []
    type_map = {}  # name -> 'contact_no' | 'contact_nc' | 'coil' | 'coil_set'
    
    # 尝试从 line 中识别元素类型
    for line_text in lines:
        line_trimmed = line_text.strip()
        if not line_trimmed:
            continue
        
        # 跳过标记符号
        for m in var_pattern.finditer(line_trimmed):
            name = m.group(1)
            if len(name) < 2 or re.match(r"^[-+=|/()]+$", name):
                continue
            
            # 判断类型：检查字符上下文
            before = line_trimmed[:m.start()]
            after = line_trimmed[m.end():]
            
            if "( )" in after or "(" in before:
                type_map[name] = "coil"
            elif "(S)" in after:
                type_map[name] = "coil_set"
            elif "(R)" in after:
                type_map[name] = "coil_reset"
            elif "/" in before or "/" in after:
                type_map[name] = "contact_nc"
            else:
                type_map[name] = "contact_no"
            
            if name not in name_order:
                name_order.append(name)
    
    if not name_order:
        return None
    
    # 为每个变量建元素（假设先串联再无分支）
    # 删除 __ 开头的不像变量名的
    name_order = [n for n in name_order if not n.startswith("__")][:10]
    if not name_order:
        return None
    
    # 查找哪些元素是触点，哪些是线圈
    contacts = []
    coils = []
    
    # 按规则：最后一个输出变量通常是线圈，其余是触点
    # 更好的规则：如果名称以 q 开头或者匹配输出变量，是线圈
    for name in name_order:
        addr = var_map.get(name, "")
        t = type_map.get(name, "contact_no")
        
        # 如果变量地址以 Q 开头，优先作为线圈
        if addr.startswith("%Q") or addr.startswith("Q") or name.startswith("q") or name.startswith("o"):
            coils.append((name, t))
        else:
            contacts.append((name, t))
    
    # 构建元素列表
    # 如果既有触点又有线圈，最后一个线圈作为实际线圈
    if coils:
        for name, t in contacts:
            op = OperandRef(name=name, address=var_map.get(name, ""))
            if "nc" in t:
                elements.append(Contact(type="normally_closed", operand=op))
            else:
                elements.append(Contact(type="normally_open", operand=op))
        
        # 最后加线圈
        for name, t in coils[-1:]:
            op = OperandRef(name=name, address=var_map.get(name, ""))
            if t == "coil_set":
                elements.append(Coil(type="coil_set", operand=op))
            elif t == "coil_reset":
                elements.append(Coil(type="coil_reset", operand=op))
            else:
                elements.append(Coil(type="coil", operand=op))
    else:
        # 全都当触点
        for name, t in contacts:
            op = OperandRef(name=name, address=var_map.get(name, ""))
            if "nc" in t:
                elements.append(Contact(type="normally_closed", operand=op))
            else:
                elements.append(Contact(type="normally_open", operand=op))
    
    return elements


_DEMO_MAP = {
    "motor-start-stop": _build_motor_start_stop,
    "traffic-light": _build_traffic_light,
    "conveyor": _build_conveyor,
}


def _render(block, LayoutEngine, SVGRendererV2):
    """AST → SVG（内部辅助）"""
    try:
        engine = LayoutEngine()
        render_block = engine.layout(block)
        renderer = SVGRendererV2(render_block)
        svg = renderer.render()
        return {
            "ast": block.to_dict(),
            "svg": svg,
        }
    except Exception as e:
        logger.warning(f"SVG render failed: {e}")
        return {"ast": None, "svg": None}


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def generate_ast_and_svg(structured: dict, mode: str = "demo") -> dict:
    """
    主入口：从 LadderProgram 结构化数据生成 AST + SVG。

    Args:
        structured: generate_ladder() 返回的 structured 字段
            = { title, description, variables: [...], networks: [...] }
        mode: "demo" | "llm" | "placeholder"

    Returns:
        { "ast": dict | None, "svg": str | None }
    """
    title = structured.get("title", "")

    if mode == "demo":
        # 匹配 demo 关键词生成精确 AST
        for keyword, builder in _DEMO_MAP.items():
            if keyword in title.lower():
                result = builder(title)
                if result:
                    return result

    # 尝试从结构化数据构建
    result = _build_from_structured(structured)
    if result:
        return result

    # 失败时使用电机 demo 作为默认回退
    if _import_v2():
        fallback = _build_motor_start_stop("MotorStartStop")
        if fallback:
            return fallback

    return {"ast": None, "svg": None}
