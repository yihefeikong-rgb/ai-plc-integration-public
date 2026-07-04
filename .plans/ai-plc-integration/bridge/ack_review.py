from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
STATE_FILE = BRIDGE_DIR / "state.json"


def _load_state(state_file: Path) -> dict:
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"[ack-review] state.json not found: {state_file}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[ack-review] state.json is invalid JSON: {exc}") from exc


def _write_next_action(run_dir: Path, decision: str, reason: str) -> None:
    if decision == "PASS":
        current_decision = "Manual review accepted"
        trigger = "C-19 supervised gate may prepare the next low-risk task"
        owner = "human"
    else:
        current_decision = "Manual review blocked"
        trigger = "Human must decide rework, scope change, or stop"
        owner = "human"

    content = "\n".join(
        [
            "# Next Action",
            "",
            f"- **Current Decision**: {current_decision}",
            "- **Manual Step**:",
            f"  - {reason}",
            "- **Implementation Note**:",
            "  - This acknowledgement updates only bridge review state and next_action.md.",
            "  - It does not run Claude, consume a queue, approve future permissions, or touch business code.",
            f"- **Owner**: {owner}",
            f"- **Trigger To Continue**: {trigger}",
            "",
        ]
    )
    (run_dir / "next_action.md").write_text(content, encoding="utf-8")


def _extract_task_text(run_dir: Path) -> str:
    result_path = run_dir / "claude_result.md"
    try:
        lines = result_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""

    in_task = False
    in_block = False
    task_lines = []
    for line in lines:
        if line.strip() == "## Task":
            in_task = True
            continue
        if not in_task:
            continue
        if line.startswith("## ") and task_lines:
            break
        if line.strip() == "```":
            if in_block:
                break
            in_block = True
            continue
        if in_block:
            task_lines.append(line)
    return "\n".join(task_lines).strip()


def _resolve_run_dir(bridge_dir: Path, run_id: str) -> Path:
    runs_root = (bridge_dir / "runs").resolve(strict=False)
    run_dir = (runs_root / run_id).resolve(strict=False)
    try:
        run_dir.relative_to(runs_root)
    except ValueError as exc:
        raise SystemExit(f"[ack-review] run_id escapes runs directory: {run_id}") from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def ack_review(
    bridge_dir: Path = BRIDGE_DIR,
    state_file: Path = STATE_FILE,
    run_id: str = "",
    decision: str = "",
    reason: str = "",
) -> dict:
    decision = decision.upper().strip()
    reason = reason.strip()
    if decision not in {"PASS", "BLOCK"}:
        raise SystemExit("[ack-review] --decision must be PASS or BLOCK")
    if not reason:
        raise SystemExit("[ack-review] --reason is required")

    state = _load_state(state_file)
    current_run_id = state.get("run_id", "")
    if run_id != current_run_id:
        raise SystemExit(f"[ack-review] run_id mismatch: state has {current_run_id}, got {run_id}")

    run_dir = _resolve_run_dir(bridge_dir, run_id)
    previous_stop_rule = state.get("stop_rule", "")

    if decision == "PASS":
        state["stage"] = "DONE"
        state["review_status"] = "PASS"
        state["last_stop_rule"] = previous_stop_rule
        state["stop_rule"] = "NONE"
        state["blocked_reason"] = ""
        task_text = _extract_task_text(run_dir)
        if task_text:
            completed = state.get("supervised_completed_tasks", [])
            if not isinstance(completed, list):
                completed = []
            if task_text not in completed:
                completed.append(task_text)
            state["supervised_completed_tasks"] = completed
    else:
        state["stage"] = "BLOCKED"
        state["review_status"] = "BLOCK"
        state["blocked_reason"] = reason

    state["owner"] = "human"
    state["last_actor"] = "human"
    state["review_ack_reason"] = reason
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d")

    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_next_action(run_dir, decision, reason)
    return {
        "decision": decision,
        "run_id": run_id,
        "state_file": str(state_file),
        "next_action": str(run_dir / "next_action.md"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Acknowledge current Codex review disposition.")
    parser.add_argument("--bridge-dir", default=str(BRIDGE_DIR))
    parser.add_argument("--state-file", default=str(STATE_FILE))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--decision", required=True, choices=["PASS", "BLOCK"])
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    result = ack_review(
        bridge_dir=Path(args.bridge_dir),
        state_file=Path(args.state_file),
        run_id=args.run_id,
        decision=args.decision,
        reason=args.reason,
    )
    print(f"[ack-review] decision={result['decision']} run_id={result['run_id']}")
    print(f"[ack-review] next_action={result['next_action']}")
    print("[ack-review] no Claude task was executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
