"""
Round Trip 测试: JSON → AST → to_dict() → JSON
验证序列化/反序列化一致性。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from lad_ast import LadderBlock, LadderNetwork, LadderRung, LadderElement
from ladder_renderer import from_cartgen_spec


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_deep_sort(obj):
    """Recursively sort dict keys for comparison."""
    if isinstance(obj, dict):
        return {k: json_deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [json_deep_sort(v) for v in obj]
    return obj


def test_round_trip_conveyor():
    """lad_ConveyorControl.json 往返测试"""
    path = os.path.join(os.path.dirname(__file__), "lad_ConveyorControl.json")
    original = load_json(path)

    # JSON → AST
    block = LadderBlock.from_dict(original)

    # AST → JSON
    regenerated = block.to_dict()

    # 比较关键字段
    assert regenerated["blockName"] == original["blockName"]
    assert regenerated["blockNumber"] == original["blockNumber"]
    assert len(regenerated["networks"]) == len(original["networks"])

    # Network 0: elements 比较
    orig_elems = original["networks"][0]["elements"]
    regen_elems = regenerated["networks"][0].get("elements", [])
    assert len(orig_elems) == len(regen_elems), \
        f"Element count mismatch: {len(orig_elems)} vs {len(regen_elems)}"

    for i, (oe, re) in enumerate(zip(orig_elems, regen_elems)):
        assert oe["type"] == re["type"], \
            f"Element {i}: type mismatch {oe['type']} vs {re['type']}"
        assert oe["operand"] == re["operand"], \
            f"Element {i}: operand mismatch {oe['operand']} vs {re['operand']}"

    print("  [OK] lad_ConveyorControl.json round-trip PASS")


def test_round_trip_cart3cycle():
    """cart_3cycle.json 往返测试（通过 from_cartgen_spec 桥接）"""
    path = os.path.join(os.path.dirname(__file__), "cart_3cycle.json")
    original = load_json(path)

    # 旧格式 → 内部格式
    internal = from_cartgen_spec(original)

    # 对每个 network 验证元素数量
    for i, (orig_net, int_net) in enumerate(zip(original["networks"], internal["networks"])):
        # 旧格式 elements 数量
        orig_count = len(orig_net.get("elements", []))
        # 新格式 rungs[0] 长度
        int_count = len(int_net.get("rungs", [[]])[0])
        assert orig_count == int_count, \
            f"Network {i}: element count mismatch {orig_count} vs {int_count}"

        # 类型验证
        for j, oe in enumerate(orig_net.get("elements", [])):
            ie = int_net["rungs"][0][j]
            assert oe["type"] == ie["type"], \
                f"Network {i} elem {j}: type mismatch {oe['type']} vs {ie['type']}"

    print("  [OK] cart_3cycle.json round-trip (via bridge) PASS")


def test_round_trip_motor_control():
    """MotorControl 往返测试：程序化构建 → to_dict → from_dict"""
    from lad_ast import Contact, Coil, Branch, OperandRef, InterfaceVariable

    # 构建 AST
    block = LadderBlock(
        name="MotorControl",
        number=1,
        inputs=[
            InterfaceVariable(name="bStart", data_type="Bool", address="%I0.0"),
            InterfaceVariable(name="bStop", data_type="Bool", address="%I0.1"),
        ],
        outputs=[
            InterfaceVariable(name="qMotor", data_type="Bool", address="%Q0.0"),
        ],
        networks=[
            LadderNetwork(
                index=1,
                title="Self-Holding",
                rung=LadderRung(elements=[
                    Contact(type="normally_open", operand=OperandRef(name="bStart")),
                    Branch(paths=[
                        [Contact(type="normally_open", operand=OperandRef(name="qMotor"))],
                    ]),
                    Contact(type="normally_closed", operand=OperandRef(name="bStop")),
                    Coil(type="coil", operand=OperandRef(name="qMotor")),
                ]),
            ),
        ],
    )

    # AST → dict
    d = block.to_dict()

    # dict → AST
    block2 = LadderBlock.from_dict(d)

    # 验证
    assert block2.name == block.name
    assert len(block2.networks) == 1
    nw = block2.networks[0]
    assert len(nw.rung.elements) == 4  # bStart, Branch, bStop, qMotor

    # Branch 元素验证
    branch = nw.rung.elements[1]
    assert branch.type == "branch"
    assert len(branch.paths) == 1
    assert len(branch.paths[0]) == 1
    assert branch.paths[0][0].operand.name == "qMotor"

    print("  [OK] MotorControl round-trip PASS")


if __name__ == "__main__":
    print("=" * 60)
    print("Round Trip Tests")
    print("=" * 60)
    test_round_trip_conveyor()
    test_round_trip_cart3cycle()
    test_round_trip_motor_control()
    print("\n[OK] ALL ROUND TRIP TESTS PASSED")
