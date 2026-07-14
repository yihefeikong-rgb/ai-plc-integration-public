from __future__ import annotations

import sys
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
STATE_PATH = BRIDGE_DIR / "state.json"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_state import ACTIVE_STAGES, KNOWN_STAGES, STOP_STAGES, BridgeStateError, read_state, validate_state_shape


def load_state() -> dict:
    try:
        return read_state(STATE_PATH)
    except BridgeStateError as exc:
        raise SystemExit(f"[runner] {exc}") from exc


def validate_state(state: dict) -> tuple[str, str]:
    try:
        return validate_state_shape(state)
    except BridgeStateError as exc:
        raise SystemExit(f"[runner] {exc}") from exc


def _runs_path(run_id: str, filename: str) -> str:
    """生成 runs/ 路径，无 run_id 时降级为 bridge/ 根目录"""
    if run_id:
        return f"`.plans/ai-plc-integration/bridge/runs/{run_id}/{filename}`"
    return f"`.plans/ai-plc-integration/bridge/{filename}`"


def build_codex_plan_prompt(state: dict, run_id: str = "") -> str:
    task = state.get("current_task") or "未命名任务"
    return f"""请作为 Codex 只做规划，不直接执行。

当前任务：{task}
当前状态：NEED_CODEX_PLAN

执行要求：
1. 先读取 `.plans/ai-plc-integration/bridge/state.json`
2. 再读取 {_runs_path(run_id, "task_packet.md")}，确认当前任务目标和限制
3. 只输出施工前规划或新的任务包草案
4. 不直接修改业务代码
5. 不自动调用 Claude Code、Codex CLI 或任何外部 agent
6. 不自动循环，不自动 git add / commit / push
7. 规划完成后，等待人工确认再推进到下一阶段
"""


def build_claude_prompt(state: dict, run_id: str = "") -> str:
    task = state.get("current_task") or "未命名任务"
    return f"""请作为 Claude Code 执行当前桥接任务。

当前任务：{task}
当前状态：NEED_CLAUDE

执行要求：
1. 先读取 `.plans/ai-plc-integration/bridge/state.json`
2. 再读取 {_runs_path(run_id, "task_packet.md")}
3. 严格按任务包的 Scope 和 Out of Scope 执行
4. 禁止触碰业务目录和禁止文件
5. 完成后只按协议回填 {_runs_path(run_id, "claude_result.md")}；不得直接修改 `state.json`
6. 由受控 Bridge 运行者以原子锁将状态切换为 `NEED_CODEX_REVIEW`（含 run_id 和结果哈希）
7. 不做 Codex Review，不自动调用任何 CLI，不自动提交 Git
"""


def build_codex_review_prompt(state: dict, run_id: str = "") -> str:
    task = state.get("current_task") or "未命名任务"
    return f"""请作为 Codex 执行审查。

当前任务：{task}
当前状态：NEED_CODEX_REVIEW

执行要求：
1. 读取 {_runs_path(run_id, "task_packet.md")}、{_runs_path(run_id, "claude_result.md")}、`state.json`
2. 对照验收标准审查范围、产出和状态是否一致
3. 只允许写 {_runs_path(run_id, "codex_review.md")}；不得直接修改 `next_action.md` 或 `state.json`
4. 写出可供人工核验的审查草案，不得自行宣布最终 PASS 或将状态收敛到 DONE
5. 由人类审查人使用 `ack_review.py` 绑定结果哈希、审查产物和决策后，才能进入 DONE 或 BLOCKED
6. 不修改业务代码，不调用任何 CLI，不自动提交 Git
"""


def build_stop_message(state: dict, stage: str) -> str:
    reason = state.get("blocked_reason") or "无"
    task = state.get("current_task") or "未命名任务"
    lines = [
        f"当前任务：{task}",
        f"当前状态：{stage}",
    ]
    if stage in {"BLOCKED", "SAFETY_BLOCK"}:
        lines.append(f"阻塞原因：{reason}")
    lines.extend(
        [
            "",
            "这是停止状态，runner 不会生成推进执行 prompt。",
            "请由人工确认下一步：",
            "- DONE：确认是否创建下一轮任务",
            "- BLOCKED：判断返工、改范围或终止",
            "- SAFETY_BLOCK：禁止继续推进，必须人工复核",
        ]
    )
    return "\n".join(lines)


def build_output(state: dict, stage: str) -> tuple[str, str]:
    run_id = state.get("run_id", "")
    if stage == "NEED_CODEX_PLAN":
        return "codex", build_codex_plan_prompt(state, run_id)
    if stage == "NEED_CLAUDE":
        return "claude_code", build_claude_prompt(state, run_id)
    if stage == "NEED_CODEX_REVIEW":
        return "codex", build_codex_review_prompt(state, run_id)
    return "human", build_stop_message(state, stage)


def main() -> int:
    state = load_state()
    stage, owner = validate_state(state)
    next_actor, prompt = build_output(state, stage)

    print("Mode: DRY-RUN")
    print(f"State File: {STATE_PATH}")
    print(f"Current Stage: {stage}")
    print(f"State Owner: {owner}")
    print(f"Suggested Recipient: {next_actor}")
    print()
    print("Next Step Suggestion:")
    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
