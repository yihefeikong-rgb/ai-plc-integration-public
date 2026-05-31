"""
PLCopen XML 生成器 — 生成标准 Ladder Diagram XML

可直接在 TIA Portal 中通过以下方式导入：
  文件 → 导入/导出 → 从 PLCopen XML 导入

或者手动修改项目文件后缀为 .xml 后用 TIA Portal 打开

格式: IEC 61131-3 (PLCopen TC6-XML v2.0.1)
"""

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from datetime import datetime

NS = "http://www.plcopen.org/xml/tc6_0201"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", NS)
ET.register_namespace("xsi", NS_XSI)


def _make_element(tag, attrib=None, text=None):
    """创建带命名空间的元素"""
    el = ET.Element(f"{{{NS}}}{tag}", attrib or {})
    if text is not None:
        el.text = text
    return el


def _add_sub(parent, tag, attrib=None, text=None):
    el = ET.SubElement(parent, f"{{{NS}}}{tag}", attrib or {})
    if text is not None:
        el.text = text
    return el


def _format_xml(tree):
    """将 XML 树格式化为缩进良好的文本"""
    rough = ET.tostring(tree.getroot(), encoding="unicode")
    dom = minidom.parseString(rough.encode())
    # 清理多余的空白
    lines = dom.toprettyxml(indent="  ")
    # 去除 <?xml...?> 前面的多余空白
    return lines


# ─── High-level 构建器 ─────────────────────────────

class LadderElement:
    """梯形图元素——触点、线圈、功能块"""
    def __init__(self, local_id, kind, subtype, var_name, x, y, width=50, height=40, params=None):
        self.local_id = local_id
        self.kind = kind          # contact / coil / block
        self.subtype = subtype    # normallyOpen / normallyClosed / normal / set / reset / TON / CTU ...
        self.var_name = var_name  # 变量名
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.params = params or {}
        self.connected_to = None  # 后续元素，用于连线

    def to_xml(self, parent):
        if self.kind == "contact":
            el = _add_sub(parent, "element", {
                "type": "contact",
                "localId": str(self.local_id),
                "width": str(self.width),
                "height": str(self.height),
            })
            _add_sub(el, "position", {"x": str(self.x), "y": str(self.y)})
            _add_sub(el, "connectionPointIn")
            _add_sub(el.find(f"{{{NS}}}connectionPointIn"), "relPosition",
                     {"x": "0", "y": str(self.height // 2)})
            _add_sub(el, "connectionPointOut")
            _add_sub(el.find(f"{{{NS}}}connectionPointOut"), "relPosition",
                     {"x": str(self.width), "y": str(self.height // 2)})
            _add_sub(el, "variable", text=self.var_name)
            _add_sub(el, "contactType", text=self.subtype)

        elif self.kind == "coil":
            el = _add_sub(parent, "element", {
                "type": "coil",
                "localId": str(self.local_id),
                "width": str(self.width),
                "height": str(self.height),
            })
            _add_sub(el, "position", {"x": str(self.x), "y": str(self.y)})
            _add_sub(el, "connectionPointIn")
            _add_sub(el.find(f"{{{NS}}}connectionPointIn"), "relPosition",
                     {"x": "0", "y": str(self.height // 2)})
            _add_sub(el, "connectionPointOut")
            _add_sub(el.find(f"{{{NS}}}connectionPointOut"), "relPosition",
                     {"x": str(self.width), "y": str(self.height // 2)})
            _add_sub(el, "variable", text=self.var_name)
            _add_sub(el, "coilType", text=self.subtype)

        elif self.kind == "block":
            el = _add_sub(parent, "element", {
                "type": "blockInstance",
                "localId": str(self.local_id),
                "width": str(self.width),
                "height": str(self.height),
            })
            _add_sub(el, "position", {"x": str(self.x), "y": str(self.y)})
            _add_sub(el, "connectionPointIn")
            _add_sub(el.find(f"{{{NS}}}connectionPointIn"), "relPosition",
                     {"x": "0", "y": str(self.height // 2)})
            _add_sub(el, "connectionPointOut")
            _add_sub(el.find(f"{{{NS}}}connectionPointOut"), "relPosition",
                     {"x": str(self.width), "y": str(self.height // 2)})
            # 块类型
            _add_sub(el, "blockType", text=self.subtype)  # TON, CTU, ADD, MOVE...
            # 实例名
            _add_sub(el, "instanceName", text=self.var_name)
            # 输入/输出参数
            for pin_name, pin_var in self.params.get("inputs", {}).items():
                pin = _add_sub(el, "inputVariable", {"formalParameter": pin_name})
                _add_sub(pin, "variable", text=pin_var)
            for pin_name, pin_var in self.params.get("outputs", {}).items():
                pin = _add_sub(el, "outputVariable", {"formalParameter": pin_name})
                _add_sub(pin, "variable", text=pin_var)

        return el


class LadderNetwork:
    """一个梯形图网络（梯级）"""
    def __init__(self, network_number, title="", comment=""):
        self.network_number = network_number
        self.title = title
        self.comment = comment
        self.elements = []

    def add_element(self, elem):
        self.elements.append(elem)
        return elem

    def to_xml(self, parent):
        nw = _add_sub(parent, "ladderNetwork", {
            "networkNumber": str(self.network_number),
        })
        if self.title:
            nw.set("networkTitle", self.title)
        if self.comment:
            nw.set("networkComment", self.comment)

        # 添加元素
        for elem in self.elements:
            elem.to_xml(nw)

        # 添加连接
        for i, elem in enumerate(self.elements[:-1]):
            next_elem = self.elements[i + 1]
            conn = _add_sub(nw, "connection", {
                "localId": str(1000 + i),
                "refLocalId": str(elem.local_id),
            })
            # 连接点的位置——当前元素的输出到下一个元素的输入
            mid_x = (elem.x + elem.width + next_elem.x) // 2
            mid_y = elem.y + elem.height // 2
            _add_sub(conn, "position", {"x": str(mid_x), "y": str(mid_y)})
            _add_sub(conn, "connectionPoint", {
                "refLocalId": str(next_elem.local_id),
                "formalParameter": "",
            })

        return nw


# ─── 生成电机控制的完整 PLCopen XML ────────────────

def generate_motor_control_xml():
    """生成电机正反转控制的 PLCopen XML (LAD)"""
    root = ET.Element(f"{{{NS}}}project")
    root.set("xmlns:xsi", NS_XSI)
    root.set("xsi:schemaLocation",
             f"{NS} http://www.plcopen.org/xml/tc6_0201")

    now = datetime.now().isoformat()

    # ── fileHeader ──
    fh = _add_sub(root, "fileHeader", {
        "companyName": "AI-PLC-Integration",
        "productName": "AI SCL→LAD Generator",
        "productVersion": "1.0",
        "creationDateTime": now,
    })

    # ── contentHeader ──
    ch = _add_sub(root, "contentHeader", {
        "name": "MotorControl",
        "modificationDateTime": now,
    })
    ci = _add_sub(ch, "coordinateInfo")
    _add_sub(ci, "fbd")
    _add_sub(ci.find(f"{{{NS}}}fbd"), "scaling", {"x": "1", "y": "1"})
    _add_sub(ci, "ld")
    _add_sub(ci.find(f"{{{NS}}}ld"), "scaling", {"x": "2", "y": "2"})
    _add_sub(ci, "sfc")
    _add_sub(ci.find(f"{{{NS}}}sfc"), "scaling", {"x": "1", "y": "1"})

    # ── types → pous ──
    types = _add_sub(root, "types")
    pous = _add_sub(types, "pous")

    # POU: MotorControl (Function Block)
    pou = _add_sub(pous, "pou", {
        "name": "MotorControl",
        "pouType": "functionBlock",
    })
    _add_sub(pou, "interface")

    # 接口：输入
    iface = pou.find(f"{{{NS}}}interface")
    iv = _add_sub(iface, "inputVars")
    for name, addr, desc in [
        ("bEmergencyStop", "%I0.0", "急停（常闭触点）"),
        ("bStartForward", "%I0.1", "正转启动按钮"),
        ("bStop", "%I0.2", "停止按钮（常闭）"),
        ("bStartReverse", "%I0.3", "反转启动按钮"),
        ("bOverload", "%I0.4", "过载信号（常闭）"),
        ("bReset", "%I0.5", "故障复位按钮"),
    ]:
        v = _add_sub(iv, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), "BOOL")
        _add_sub(v, "address", text=addr)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 接口：输出
    ov = _add_sub(iface, "outputVars")
    for name, addr, desc in [
        ("bForwardOut", "%Q0.0", "正转输出"),
        ("bReverseOut", "%Q0.1", "反转输出"),
        ("bFault", "%Q0.2", "故障指示"),
    ]:
        v = _add_sub(ov, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), "BOOL")
        _add_sub(v, "address", text=addr)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 接口：本地变量
    lv = _add_sub(iface, "localVars")
    for name, typ, desc in [
        ("bSafetyOK", "BOOL", "安全状态位（急停正常时=ON）"),
        ("bFaultLatch", "BOOL", "故障锁存位"),
        ("bRunForward", "BOOL", "正转运行中间位"),
        ("bRunReverse", "BOOL", "反转运行中间位"),
    ]:
        v = _add_sub(lv, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), typ)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 接口：暂未使用的临时变量（timer 等）
    av = _add_sub(iface, "tempVars")
    for name, typ, desc in [
        ("tmrFeedback", "TON", "运行反馈超时定时器"),
    ]:
        v = _add_sub(av, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), typ)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # ── Body: LD ──
    body = _add_sub(pou, "body")
    ld = _add_sub(body, "LD")

    # ── 网络1：急停互锁 ──
    nw1 = LadderNetwork(1, "急停互锁", "急停按钮为常闭触点，按下时切断 bSafetyOK")
    nw1.add_element(LadderElement(1, "contact", "normallyClosed", "bEmergencyStop", 100, 50))
    nw1.add_element(LadderElement(2, "coil", "normal", "bSafetyOK", 250, 50))
    nw1.to_xml(ld)

    # ── 网络2：正转启动（自保持 + 互锁） ──
    nw2 = LadderNetwork(2, "正转自保持 + 反转互锁",
                         "bStartForward 或 bRunForward → bStop → bSafetyOK → NOT bReverseOut → 输出")
    nw2.add_element(LadderElement(3, "contact", "normallyOpen", "bStartForward", 100, 130))
    nw2.add_element(LadderElement(4, "contact", "normallyOpen", "bRunForward", 200, 130))
    nw2.add_element(LadderElement(5, "contact", "normallyClosed", "bStop", 350, 130))
    nw2.add_element(LadderElement(6, "contact", "normallyOpen", "bSafetyOK", 450, 130))
    nw2.add_element(LadderElement(7, "contact", "normallyClosed", "bReverseOut", 550, 130))
    nw2.add_element(LadderElement(8, "coil", "normal", "bForwardOut", 650, 130))
    nw2.to_xml(ld)

    # ── 网络3：反转启动（自保持 + 互锁） ──
    nw3 = LadderNetwork(3, "反转自保持 + 正转互锁",
                         "bStartReverse 或 bRunReverse → bStop → bSafetyOK → NOT bForwardOut → 输出")
    nw3.add_element(LadderElement(9, "contact", "normallyOpen", "bStartReverse", 100, 210))
    nw3.add_element(LadderElement(10, "contact", "normallyOpen", "bRunReverse", 200, 210))
    nw3.add_element(LadderElement(11, "contact", "normallyClosed", "bStop", 350, 210))
    nw3.add_element(LadderElement(12, "contact", "normallyOpen", "bSafetyOK", 450, 210))
    nw3.add_element(LadderElement(13, "contact", "normallyClosed", "bForwardOut", 550, 210))
    nw3.add_element(LadderElement(14, "coil", "normal", "bReverseOut", 650, 210))
    nw3.to_xml(ld)

    # ── 网络4：过载保护 + 故障锁存 ──
    nw4 = LadderNetwork(4, "过载保护 + 故障锁存",
                         "过载断开时置位 bFault，复位按钮+bFault 时复位")
    nw4.add_element(LadderElement(15, "contact", "normallyClosed", "bOverload", 100, 290))
    nw4.add_element(LadderElement(16, "contact", "normallyOpen", "bFaultLatch", 200, 290))
    nw4.add_element(LadderElement(17, "coil", "set", "bFaultLatch", 350, 290))
    nw4.to_xml(ld)

    # ── 网络5：故障复位 ──
    nw5 = LadderNetwork(5, "故障复位",
                         "复位按钮 + 故障锁存 → 复位线圈")
    nw5.add_element(LadderElement(18, "contact", "normallyOpen", "bReset", 100, 370))
    nw5.add_element(LadderElement(19, "contact", "normallyOpen", "bFaultLatch", 200, 370))
    nw5.add_element(LadderElement(20, "coil", "reset", "bFaultLatch", 350, 370))
    nw5.to_xml(ld)

    # ── 网络6：故障→输出映射 ──
    nw6 = LadderNetwork(6, "故障 → 输出灯",
                         "bFaultLatch 驱动故障指示灯")
    nw6.add_element(LadderElement(21, "contact", "normallyOpen", "bFaultLatch", 100, 450))
    nw6.add_element(LadderElement(22, "coil", "normal", "bFault", 250, 450))
    nw6.add_element(LadderElement(23, "coil", "normal", "bFaultLatch", 400, 450))
    nw6.to_xml(ld)

    return _format_xml(ET.ElementTree(root))


def generate_material_cart_xml():
    """生成材料小车的 PLCopen XML (含状态机展开)"""
    root = ET.Element(f"{{{NS}}}project")
    root.set("xmlns:xsi", NS_XSI)
    root.set("xsi:schemaLocation",
             f"{NS} http://www.plcopen.org/xml/tc6_0201")

    now = datetime.now().isoformat()

    # ── fileHeader ──
    fh = _add_sub(root, "fileHeader", {
        "companyName": "AI-PLC-Integration",
        "productName": "AI SCL→LAD Generator",
        "productVersion": "1.0",
        "creationDateTime": now,
    })

    # ── contentHeader ──
    ch = _add_sub(root, "contentHeader", {
        "name": "MaterialCartControl",
        "modificationDateTime": now,
    })
    ci = _add_sub(ch, "coordinateInfo")
    _add_sub(ci, "fbd")
    _add_sub(ci.find(f"{{{NS}}}fbd"), "scaling", {"x": "1", "y": "1"})
    _add_sub(ci, "ld")
    _add_sub(ci.find(f"{{{NS}}}ld"), "scaling", {"x": "2", "y": "2"})
    _add_sub(ci, "sfc")
    _add_sub(ci.find(f"{{{NS}}}sfc"), "scaling", {"x": "1", "y": "1"})

    types = _add_sub(root, "types")
    pous = _add_sub(types, "pous")

    pou = _add_sub(pous, "pou", {"name": "MaterialCartControl", "pouType": "functionBlock"})
    _add_sub(pou, "interface")
    iface = pou.find(f"{{{NS}}}interface")

    # 输入
    iv = _add_sub(iface, "inputVars")
    for name, addr, desc in [
        ("bStart", "%I0.0", "启动"),
        ("bStop", "%I0.1", "停止"),
        ("bReset", "%I0.2", "复位"),
        ("bEmergencyStop", "%I0.3", "急停（常闭）"),
        ("bForwardLimit", "%I0.4", "前限位"),
        ("bReverseLimit", "%I0.5", "后限位"),
        ("bOverload", "%I0.6", "过载（常闭）"),
        ("bManualMode", "%I0.7", "手动模式"),
        ("bManualForward", "%I1.0", "手动正转"),
        ("bManualReverse", "%I1.1", "手动反转"),
    ]:
        v = _add_sub(iv, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), "BOOL")
        _add_sub(v, "address", text=addr)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 输出
    ov = _add_sub(iface, "outputVars")
    for name, addr, desc in [
        ("bForwardOut", "%Q0.0", "正转输出"),
        ("bReverseOut", "%Q0.1", "反转输出"),
        ("bRunning", "%Q0.2", "运行中"),
        ("bFault", "%Q0.3", "故障"),
    ]:
        v = _add_sub(ov, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), "BOOL")
        _add_sub(v, "address", text=addr)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 本地变量
    lv = _add_sub(iface, "localVars")
    for name, typ, desc in [
        ("bSafetyOK", "BOOL", "安全链正常"),
        ("bFaultLatch", "BOOL", "故障锁存"),
        ("iState1", "BOOL", "状态=前进"),
        ("iState2", "BOOL", "状态=卸载"),
        ("iState3", "BOOL", "状态=后退"),
        ("iState4", "BOOL", "状态=装载"),
        ("iState5", "BOOL", "状态=故障"),
    ]:
        v = _add_sub(lv, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), typ)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # 定时器
    tv = _add_sub(iface, "tempVars")
    for name, typ, desc in [
        ("tmrUnload", "TON", "卸载延时 T#5S"),
        ("tmrLoad", "TON", "装载延时 T#3S"),
    ]:
        v = _add_sub(tv, "variable", {"name": name})
        _add_sub(v, "type")
        _add_sub(v.find(f"{{{NS}}}type"), typ)
        _add_sub(v, "documentation")
        _add_sub(v.find(f"{{{NS}}}documentation"), "xhtml", text=desc)

    # ── Body ──
    body = _add_sub(pou, "body")
    ld = _add_sub(body, "LD")

    # 网络1：安全链
    nw1 = LadderNetwork(1, "安全链", "急停 AND 过载 → bSafetyOK")
    nw1.add_element(LadderElement(1, "contact", "normallyClosed", "bEmergencyStop", 100, 50))
    nw1.add_element(LadderElement(2, "contact", "normallyClosed", "bOverload", 200, 50))
    nw1.add_element(LadderElement(3, "coil", "normal", "bSafetyOK", 350, 50))
    nw1.to_xml(ld)

    # 网络2：故障锁存
    nw2 = LadderNetwork(2, "故障锁存", "安全链断开 + NOT bReset → 锁存故障")
    nw2.add_element(LadderElement(4, "contact", "normallyClosed", "bSafetyOK", 100, 130))
    nw2.add_element(LadderElement(5, "coil", "set", "bFaultLatch", 250, 130))
    nw2.to_xml(ld)

    # 网络3：故障复位
    nw3 = LadderNetwork(3, "故障复位", "复位按钮 + 故障锁存 → 清除锁存")
    nw3.add_element(LadderElement(6, "contact", "normallyOpen", "bReset", 100, 210))
    nw3.add_element(LadderElement(7, "contact", "normallyOpen", "bFaultLatch", 200, 210))
    nw3.add_element(LadderElement(8, "coil", "reset", "bFaultLatch", 350, 210))
    nw3.to_xml(ld)

    # 网络4：状态机-前进
    nw4 = LadderNetwork(4, "启动 → 前进 (State=1)",
                         "bStart + NOT bFaultLatch → 进入前进状态")
    nw4.add_element(LadderElement(9, "contact", "normallyOpen", "bStart", 100, 290))
    nw4.add_element(LadderElement(10, "contact", "normallyClosed", "bFaultLatch", 200, 290))
    nw4.add_element(LadderElement(11, "coil", "set", "iState1", 350, 290))
    nw4.to_xml(ld)

    # 网络5：前进输出 + 限位到达 → 转卸载
    nw5 = LadderNetwork(5, "前进运行 + 到达前限位",
                         "State=1 → 正转输出 + 运行指示；前限位到达 → 转卸载 State=2")
    nw5.add_element(LadderElement(12, "contact", "normallyOpen", "iState1", 100, 370))
    nw5.add_element(LadderElement(13, "coil", "normal", "bForwardOut", 200, 370))
    nw5.add_element(LadderElement(14, "coil", "normal", "bRunning", 350, 370))
    nw5.to_xml(ld)

    nw5b = LadderNetwork(5, "前进→前限位到达", "State=1 + ForwardLimit → 转入 State=2 卸载")
    nw5b.add_element(LadderElement(15, "contact", "normallyOpen", "iState1", 100, 450))
    nw5b.add_element(LadderElement(16, "contact", "normallyOpen", "bForwardLimit", 200, 450))
    nw5b.add_element(LadderElement(17, "coil", "reset", "iState1", 350, 450))
    nw5b.add_element(LadderElement(18, "coil", "set", "iState2", 500, 450))
    nw5b.to_xml(ld)

    # 网络6：卸载延时
    nw6 = LadderNetwork(6, "卸载 (State=2) — TON T#5S",
                         "到达前限位 → 等待 5 秒卸载时间")
    nw6.add_element(LadderElement(19, "contact", "normallyOpen", "iState2", 100, 530))
    # 定时器 TON 功能块
    nw6.add_element(LadderElement(20, "block", "TON", "tmrUnload",
                                  250, 520, width=120, height=60,
                                  params={
                                      "inputs": {"IN": "iState2", "PT": "T#5S"},
                                      "outputs": {"Q": "tmrUnloadDone", "ET": "tmrUnloadET"},
                                  }))
    nw6.to_xml(ld)

    # 网络7：卸载完成→后退
    nw7 = LadderNetwork(7, "卸载完成 → 后退 (State=3)",
                         "Timer 超时 → 转入后退状态")
    nw7.add_element(LadderElement(21, "contact", "normallyOpen", "tmrUnloadDone", 100, 610))
    nw7.add_element(LadderElement(22, "coil", "reset", "iState2", 250, 610))
    nw7.add_element(LadderElement(23, "coil", "set", "iState3", 400, 610))
    nw7.to_xml(ld)

    # 网络8：后退 + 后限位
    nw8 = LadderNetwork(8, "后退运行 + 到达后限位",
                         "State=3 → 反转输出；后限位到达 → 转装载")
    nw8.add_element(LadderElement(24, "contact", "normallyOpen", "iState3", 100, 690))
    nw8.add_element(LadderElement(25, "coil", "normal", "bReverseOut", 200, 690))
    nw8.add_element(LadderElement(26, "coil", "normal", "bRunning", 350, 690))
    nw8.to_xml(ld)

    nw8b = LadderNetwork(8, "后退→后限位到达", "State=3 + ReverseLimit → 转入 State=4 装载")
    nw8b.add_element(LadderElement(27, "contact", "normallyOpen", "iState3", 100, 770))
    nw8b.add_element(LadderElement(28, "contact", "normallyOpen", "bReverseLimit", 200, 770))
    nw8b.add_element(LadderElement(29, "coil", "reset", "iState3", 350, 770))
    nw8b.add_element(LadderElement(30, "coil", "set", "iState4", 500, 770))
    nw8b.to_xml(ld)

    # 网络9：装载延时
    nw9 = LadderNetwork(9, "装载 (State=4) — TON T#3S",
                         "到达后限位 → 等待 3 秒装载时间")
    nw9.add_element(LadderElement(31, "contact", "normallyOpen", "iState4", 100, 850))
    nw9.add_element(LadderElement(32, "block", "TON", "tmrLoad",
                                   250, 840, width=120, height=60,
                                   params={
                                       "inputs": {"IN": "iState4", "PT": "T#3S"},
                                       "outputs": {"Q": "tmrLoadDone", "ET": "tmrLoadET"},
                                   }))
    nw9.to_xml(ld)

    # 网络10：装载完成→回到前进/停止
    nw10 = LadderNetwork(10, "装载完成 → 下一轮/停止",
                          "Timer 超时 → 状态回 State=1（前进）继续循环，或停止")
    nw10.add_element(LadderElement(33, "contact", "normallyOpen", "tmrLoadDone", 100, 930))
    nw10.add_element(LadderElement(34, "coil", "reset", "iState4", 250, 930))
    nw10.add_element(LadderElement(35, "coil", "set", "iState1", 400, 930))
    nw10.to_xml(ld)

    # 网络11：故障状态输出
    nw11 = LadderNetwork(11, "故障输出", "bFaultLatch → 故障指示灯")
    nw11.add_element(LadderElement(36, "contact", "normallyOpen", "bFaultLatch", 100, 1010))
    nw11.add_element(LadderElement(37, "coil", "normal", "bFault", 250, 1010))
    nw11.to_xml(ld)

    return _format_xml(ET.ElementTree(root))


# ─── 主入口 ────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PLCopen XML 生成器")
    print("=" * 60)

    # 生成电机控制
    xml1 = generate_motor_control_xml()
    with open("motor_control_plcopen.xml", "w", encoding="utf-8") as f:
        f.write(xml1)
    print(f"  ✅ 电机控制: motor_control_plcopen.xml ({len(xml1)} 字节)")

    # 生成材料小车
    xml2 = generate_material_cart_xml()
    with open("material_cart_plcopen.xml", "w", encoding="utf-8") as f:
        f.write(xml2)
    print(f"  ✅ 材料小车: material_cart_plcopen.xml ({len(xml2)} 字节)")
    print()
    print("在 TIA Portal 中导入方法：")
    print("  文件 → 导入/导出 → 从 PLCopen XML 导入")
    print("  或者直接拖拽 .xml 文件到项目树")
    print()
    print("也可以到这里下载 OpenPLC Editor 查看：")
    print("  https://github.com/thiagoralves/OpenPLC_v3")
