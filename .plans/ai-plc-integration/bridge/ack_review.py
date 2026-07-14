from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
STATE_FILE = BRIDGE_DIR / "state.json"

if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_state import (
    REVIEWABLE_STAGE,
    BridgeStateError,
    artifact_sha256,
    locked_state,
    write_text_atomic,
)


RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def _write_next_action(run_dir: Path, decision: str, reason: str, reviewer: str) -> Path:
    if decision == "PASS":
        current_decision = "Manual review accepted"
        trigger = "C-19 supervised gate may prepare the next low-risk task"
    else:
        current_decision = "Manual review blocked"
        trigger = "Human must decide rework, scope change, or stop"

    content = "\n".join(
        [
            "# Next Action",
            "",
            f"- **Current Decision**: {current_decision}",
            f"- **Reviewer**: {reviewer}",
            "- **Manual Step**:",
            f"  - {reason}",
            "- **Implementation Note**:",
            "  - This acknowledgement updates only bridge review state and next_action.md.",
            "  - It does not run Claude, consume a queue, approve future permissions, or touch business code.",
            "- **Owner**: human",
            f"- **Trigger To Continue**: {trigger}",
            "",
        ]
    )
    next_action = run_dir / "next_action.md"
    write_text_atomic(next_action, content)
    return next_action


def _extract_task_text(run_dir: Path) -> str:
    result_path = run_dir / "claude_result.md"
    lines = result_path.read_text(encoding="utf-8").splitlines()

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
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit("[ack-review] run_id format is invalid")

    runs_root = (bridge_dir / "runs").resolve(strict=False)
    run_dir = (runs_root / run_id).resolve(strict=False)
    try:
        run_dir.relative_to(runs_root)
    except ValueError as exc:
        raise SystemExit(f"[ack-review] run_id escapes runs directory: {run_id}") from exc
    if not run_dir.is_dir() or run_dir.is_symlink():
        raise SystemExit(f"[ack-review] run directory not found or unsafe: {run_dir}")
    return run_dir


def _validate_reviewer(reviewer: str) -> str:
    reviewer = reviewer.strip()
    if not reviewer.startswith("human:") or len(reviewer) <= len("human:"):
        raise SystemExit("[ack-review] --reviewer must use the form human:<reviewer-id>")
    if len(reviewer) > 128 or not re.fullmatch(r"human:[A-Za-z0-9_.@-]+", reviewer):
        raise SystemExit("[ack-review] --reviewer contains unsupported characters")
    return reviewer


def _review_artifacts(run_dir: Path, state: dict) -> tuple[Path, Path, str, str]:
    result_path = run_dir / "claude_result.md"
    review_path = run_dir / "codex_review.md"
    if result_path.is_symlink() or review_path.is_symlink():
        raise SystemExit("[ack-review] review artifacts must not be symlinks")
    if not result_path.is_file() or not review_path.is_file():
        raise SystemExit("[ack-review] claude_result.md and codex_review.md are both required")

    expected_result_hash = state.get("claude_result_sha256")
    if not isinstance(expected_result_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_result_hash):
        raise SystemExit("[ack-review] state lacks a valid claude_result_sha256")

    actual_result_hash = artifact_sha256(result_path)
    if actual_result_hash != expected_result_hash:
        raise SystemExit("[ack-review] claude_result.md no longer matches the recorded run evidence")

    review_content = review_path.read_text(encoding="utf-8").strip()
    if not review_content:
        raise SystemExit("[ack-review] codex_review.md is empty")
    return result_path, review_path, actual_result_hash, artifact_sha256(review_path)


def ack_review(
    bridge_dir: Path = BRIDGE_DIR,
    state_file: Path = STATE_FILE,
    run_id: str = "",
    decision: str = "",
    reason: str = "",
    reviewer: str = "",
) -> dict:
    decision = decision.upper().strip()
    reason = reason.strip()
    reviewer = _validate_reviewer(reviewer)
    if decision not in {"PASS", "BLOCK"}:
        raise SystemExit("[ack-review] --decision must be PASS or BLOCK")
    if not reason:
        raise SystemExit("[ack-review] --reason is required")

    try:
        with locked_state(state_file) as state:
            current_run_id = state.get("run_id", "")
            if run_id != current_run_id:
                raise SystemExit(
                    f"[ack-review] run_id mismatch: state has {current_run_id}, got {run_id}"
                )
            if state.get("stage") != REVIEWABLE_STAGE:
                raise SystemExit(
                    f"[ack-review] state must be {REVIEWABLE_STAGE}, got {state.get('stage')!r}"
                )
            if state.get("review_status") not in {"", "PENDING"}:
                raise SystemExit("[ack-review] current run has already received a review disposition")

            run_dir = _resolve_run_dir(bridge_dir, run_id)
            _, review_path, result_hash, review_hash = _review_artifacts(run_dir, state)
            previous_stop_rule = state.get("stop_rule", "")
            if decision == "PASS" and previous_stop_rule != "NONE":
                raise SystemExit(
                    "[ack-review] PASS requires stop_rule=NONE; use BLOCK for any stopped or denied run"
                )

            next_action = _write_next_action(run_dir, decision, reason, reviewer)
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
            state["reviewer"] = reviewer
            state["review_ack_reason"] = reason
            state["claude_result_sha256"] = result_hash
            state["codex_review_sha256"] = review_hash
            state["codex_review_file"] = review_path.name
            state["review_ack_at"] = datetime.now(timezone.utc).isoformat()
            state["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    except BridgeStateError as exc:
        raise SystemExit(f"[ack-review] {exc}") from exc

    return {
        "decision": decision,
        "run_id": run_id,
        "reviewer": reviewer,
        "state_file": str(state_file),
        "next_action": str(next_action),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Acknowledge current Codex review disposition.")
    parser.add_argument("--bridge-dir", default=str(BRIDGE_DIR))
    parser.add_argument("--state-file", default=str(STATE_FILE))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--decision", required=True, choices=["PASS", "BLOCK"])
    parser.add_argument("--reason", required=True)
    parser.add_argument("--reviewer", required=True, help="Human reviewer identity, e.g. human:alice")
    args = parser.parse_args()

    result = ack_review(
        bridge_dir=Path(args.bridge_dir),
        state_file=Path(args.state_file),
        run_id=args.run_id,
        decision=args.decision,
        reason=args.reason,
        reviewer=args.reviewer,
    )
    print(f"[ack-review] decision={result['decision']} run_id={result['run_id']}")
    print(f"[ack-review] reviewer={result['reviewer']}")
    print(f"[ack-review] next_action={result['next_action']}")
    print("[ack-review] no Claude task was executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
