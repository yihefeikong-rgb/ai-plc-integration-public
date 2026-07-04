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
        raise SystemExit(f"[review-draft] state.json not found: {state_file}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[review-draft] state.json is invalid JSON: {exc}") from exc


def _resolve_run_dir(bridge_dir: Path, state: dict) -> tuple[Path, str]:
    run_id = state.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise SystemExit("[review-draft] state.json missing run_id")

    run_dir = (bridge_dir / "runs" / run_id).resolve(strict=False)
    runs_root = (bridge_dir / "runs").resolve(strict=False)
    try:
        run_dir.relative_to(runs_root)
    except ValueError as exc:
        raise SystemExit(f"[review-draft] run_id escapes runs directory: {run_id}") from exc

    return run_dir, run_id


def _extract_line(content: str, marker: str) -> str:
    for line in content.splitlines():
        if marker in line:
            return line.strip()
    return ""


def _draft_result(claude_result: str) -> tuple[str, list[str], str]:
    summary_line = _extract_line(claude_result, "**Summary**")
    status_line = _extract_line(claude_result, "**status**")
    has_message_complete = "message_complete" in claude_result
    has_denied_permissions = "permission(s) denied" in summary_line or "| ❌ DENY |" in claude_result

    if has_denied_permissions:
        return (
            "CONDITIONAL PASS DRAFT",
            [
                "Session completed, but permissions were denied and require human review.",
                "Bridge artifacts were written for inspection.",
            ],
            "Permissions were denied, so this draft cannot be treated as final approval.",
        )
    if "OK" in status_line and "success" in summary_line and has_message_complete:
        return (
            "PASS DRAFT",
            [
                "Session status is OK.",
                "Result summary is success.",
                "Event log includes message_complete.",
            ],
            "Low-risk bridge execution appears internally consistent.",
        )
    return (
        "BLOCK DRAFT",
        [
            "Review evidence is incomplete or indicates failure.",
            "Human review should inspect claude_result.md before continuing.",
        ],
        "The draft generator could not prove a successful bridge run from the available result.",
    )


def build_review_content(state: dict, run_id: str, claude_result: str) -> str:
    result, passed_items, rationale = _draft_result(claude_result)
    task = state.get("current_task") or "unknown"
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "# Codex Review",
        "",
        f"- **Result**: {result}",
        f"- **Task**: {task}",
        f"- **Date**: {today}",
        f"- **Run ID**: {run_id}",
        "- **Human final decision required**: yes",
        "",
        "## Findings",
        "",
        "| # | Severity | Description |",
        "|---|----------|-------------|",
    ]

    if result == "PASS DRAFT":
        lines.append("| 1 | P2 | No blocking issue found by draft generator. |")
    elif result == "CONDITIONAL PASS DRAFT":
        lines.append("| 1 | P1 | One or more permissions were denied; human must verify the denial was expected. |")
    else:
        lines.append("| 1 | P1 | Draft generator could not prove the run passed. |")

    lines.extend(
        [
            "",
            "## What Passed",
            "",
        ]
    )
    for item in passed_items:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Scope Check",
            "",
            "- Draft generation only reads bridge run artifacts and writes this review draft.",
            "- No business code, git operation, automatic retry, or DONE transition is performed.",
            "",
            "## Decision Rationale",
            "",
            rationale,
            "",
            "## Recommended Follow-up",
            "",
            "- [ ] Human reviewer confirms or edits this draft before final disposition.",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_review_draft(
    bridge_dir: Path = BRIDGE_DIR,
    state_file: Path = STATE_FILE,
) -> Path:
    state = _load_state(state_file)
    if state.get("stage") != "NEED_CODEX_REVIEW":
        raise SystemExit("[review-draft] state must be NEED_CODEX_REVIEW")

    run_dir, run_id = _resolve_run_dir(bridge_dir, state)
    claude_result_path = run_dir / "claude_result.md"
    try:
        claude_result = claude_result_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"[review-draft] claude_result.md not found: {claude_result_path}") from exc

    review_path = run_dir / "codex_review.md"
    if review_path.exists():
        raise SystemExit(f"[review-draft] codex_review.md already exists: {review_path}")

    review_path.write_text(build_review_content(state, run_id, claude_result), encoding="utf-8")
    return review_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a human-reviewable Codex review draft.")
    parser.add_argument("--bridge-dir", default=str(BRIDGE_DIR))
    parser.add_argument("--state-file", default=str(STATE_FILE))
    args = parser.parse_args()

    review_path = generate_review_draft(
        bridge_dir=Path(args.bridge_dir),
        state_file=Path(args.state_file),
    )
    print(f"[review-draft] wrote {review_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
