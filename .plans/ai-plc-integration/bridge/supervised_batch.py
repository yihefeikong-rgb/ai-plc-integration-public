from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
STATE_FILE = BRIDGE_DIR / "state.json"


def load_state(state_file: Path = STATE_FILE) -> dict:
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"[supervised-batch] state.json not found: {state_file}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[supervised-batch] state.json is invalid JSON: {exc}") from exc


def load_task_queue(task_file: Path) -> list[str]:
    try:
        lines = task_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise SystemExit(f"[supervised-batch] task file not found: {task_file}") from exc

    tasks = []
    for line in lines:
        task = line.strip()
        if not task or task.startswith("#"):
            continue
        tasks.append(task)
    return tasks


def evaluate_supervised_gate(state: dict) -> dict:
    session_id = state.get("session_id", "")
    if not isinstance(session_id, str) or not session_id.strip():
        return {
            "allowed": False,
            "code": "MISSING_SESSION",
            "reason": "state.json has no reusable session_id",
        }

    stop_rule = state.get("stop_rule", "")
    if stop_rule and stop_rule != "NONE":
        reason = state.get("blocked_reason") or "stop rule requires human review"
        return {
            "allowed": False,
            "code": "STOP_RULE_ACTIVE",
            "reason": f"{stop_rule}: {reason}",
        }

    stage = state.get("stage", "")
    review_status = state.get("review_status", "")
    if stage == "NEED_CODEX_REVIEW" and review_status != "PASS":
        return {
            "allowed": False,
            "code": "HUMAN_REVIEW_REQUIRED",
            "reason": "current run is still waiting for human/Codex review",
        }

    if stage in {"BLOCKED", "SAFETY_BLOCK"}:
        return {
            "allowed": False,
            "code": "STOP_STAGE",
            "reason": f"state stage is {stage}",
        }

    if review_status not in {"", "PASS"}:
        return {
            "allowed": False,
            "code": "REVIEW_NOT_PASS",
            "reason": f"review_status is {review_status}",
        }

    return {
        "allowed": True,
        "code": "READY",
        "reason": "supervised gate passed",
    }


def build_next_step(state: dict, task_text: str) -> str:
    session_id = state.get("session_id", "")
    quoted_task = shlex.quote(task_text)
    quoted_session = shlex.quote(session_id)
    return (
        "D:/Python3/python.exe .plans/ai-plc-integration/bridge/ws_task_runner.py "
        f"{quoted_task} --session-id {quoted_session}"
    )


def run_supervised_dry_run(state_file: Path = STATE_FILE, task_file: Path | None = None) -> dict:
    if task_file is None:
        raise SystemExit("[supervised-batch] --task-file is required")

    state = load_state(state_file)
    gate = evaluate_supervised_gate(state)
    tasks = load_task_queue(task_file)
    completed = state.get("supervised_completed_tasks", [])
    if not isinstance(completed, list):
        completed = []
    next_task = ""
    for task in tasks:
        if task not in completed:
            next_task = task
            break
    if gate["allowed"] and tasks and not next_task:
        gate = {
            "allowed": False,
            "code": "ALL_TASKS_DONE",
            "reason": "all supervised tasks have been completed",
        }
    next_step = build_next_step(state, next_task) if gate["allowed"] and next_task else ""

    return {
        "allowed": gate["allowed"],
        "code": gate["code"],
        "reason": gate["reason"],
        "task_count": len(tasks),
        "next_task": next_task,
        "next_step": next_step,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="C-19 supervised low-risk batch dry-run gate.")
    parser.add_argument("--state-file", default=str(STATE_FILE))
    parser.add_argument("--task-file", required=True)
    args = parser.parse_args()

    result = run_supervised_dry_run(
        state_file=Path(args.state_file),
        task_file=Path(args.task_file),
    )

    print("Mode: SUPERVISED-DRY-RUN")
    print(f"Allowed: {str(result['allowed']).lower()}")
    print(f"Code: {result['code']}")
    print(f"Reason: {result['reason']}")
    print(f"Task Count: {result['task_count']}")
    if result["next_task"]:
        print(f"Next Task: {result['next_task']}")
    if result["next_step"]:
        print()
        print("Next Step Command:")
        print(result["next_step"])
        print()
        print("人工确认后才可复制执行；本脚本不自动调用 Claude、不循环、不修改 state.json。")
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
