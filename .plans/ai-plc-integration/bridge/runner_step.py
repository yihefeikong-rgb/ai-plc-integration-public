"""
runner_step.py — Phase 5 受控单步自动化 MVP。

默认以 dry-run 模式运行，只展示将要执行的动作摘要，不调用 CLI。
传入 --execute 且经人工 YES 确认后，才执行实际 CLI 调用。

当前 MVP 支持 NEED_CLAUDE 真实调用 Claude Code。
NEED_CODEX_PLAN 与 NEED_CODEX_REVIEW 仅输出 prompt（暂不支持真实调用）。

Usage:
    python runner_step.py                  # dry-run 模式
    python runner_step.py --execute        # 执行模式（需人工 YES 确认）
    python runner_step.py --copy           # 复制 prompt 到剪贴板（cc-haha GUI 兼容）
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BRIDGE_DIR.parents[2]
ALLOWED_CLAUDE_EXECUTABLES = frozenset({"claude", "claude.exe", "claude.cmd"})


class RunnerCommandError(ValueError):
    """执行命令不满足 Bridge 的受控 CLI 边界。"""


def resolve_claude_command(raw_command: str) -> list[str]:
    """只接受单个、可定位的 Claude CLI 可执行文件，拒绝附带参数。"""
    try:
        parts = shlex.split(raw_command, posix=False)
    except ValueError as exc:
        raise RunnerCommandError(f"CLAUDE_CODE_CMD 无法解析: {exc}") from exc

    if len(parts) != 1 or not parts[0].strip():
        raise RunnerCommandError("CLAUDE_CODE_CMD 只能指定一个 Claude CLI 可执行文件，不可包含参数")

    candidate = parts[0].strip('"')
    if Path(candidate).name.lower() not in ALLOWED_CLAUDE_EXECUTABLES:
        raise RunnerCommandError("CLAUDE_CODE_CMD 必须是 claude、claude.exe 或 claude.cmd")

    resolved = shutil.which(candidate)
    if not resolved:
        raise RunnerCommandError(f"找不到受控 Claude CLI: {candidate}")
    if Path(resolved).name.lower() not in ALLOWED_CLAUDE_EXECUTABLES:
        raise RunnerCommandError("解析后的 CLI 不在受控允许列表中")
    return [resolved]


def run_claude_cli(argv: list[str], prompt: str) -> subprocess.CompletedProcess:
    """在固定项目根目录运行经 allowlist 验证过的 Claude CLI。"""
    return subprocess.run(
        argv,
        input=prompt,
        text=True,
        shell=False,
        cwd=str(PROJECT_ROOT),
        timeout=3600,
    )

from runner_dry_run import (
    STATE_PATH,
    STOP_STAGES,
    build_output,
    build_stop_message,
    load_state,
    validate_state,
)


def show_execution_summary(
    stage: str,
    owner: str,
    next_actor: str,
    cmd_source: str,
    cmd: str | None,
    argv: list[str] | None,
    prompt_summary: str,
) -> None:
    """打印执行摘要."""
    print("=" * 62)
    print("  runner_step — 执行摘要")
    print("=" * 62)
    print(f"  Mode:            {'EXECUTE' if cmd else 'DRY-RUN'}")
    print(f"  State File:      {STATE_PATH}")
    print(f"  Current Stage:   {stage}")
    print(f"  State Owner:     {owner}")
    print(f"  Target Agent:    {next_actor}")
    print(f"  Command Source:  {cmd_source}")
    if argv:
        print(f"  Command:         {argv[0]}")
        if len(argv) > 1:
            print(f"  Arguments:       {argv[1:]}")
    elif cmd:
        print(f"  Command:         {cmd}")
    print(f"  Prompt Summary:  {prompt_summary}")
    print("=" * 62)


def truncate_prompt(prompt: str, max_len: int = 200) -> str:
    """截断 prompt 为单行摘要."""
    one_line = prompt.replace("\n", " ").strip()
    if len(one_line) <= max_len:
        return one_line
    return one_line[:max_len] + "..."


def copy_to_clipboard(text: str) -> bool:
    """使用 Windows clip.exe 将文本复制到系统剪贴板（shell=False，安全参数数组调用）。"""
    try:
        subprocess.run(
            ["clip"],
            input=text,
            text=True,
            shell=False,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        print(f"[runner_step] 错误: 剪贴板复制失败: {exc}")
        return False


def main() -> int:
    execute_mode = "--execute" in sys.argv
    copy_mode = "--copy" in sys.argv

    # 加载和验证状态
    state = load_state()
    stage, owner = validate_state(state)

    # 构建 prompt
    next_actor, prompt = build_output(state, stage)

    # === --copy 模式：将 prompt 复制到剪贴板，不调用 Agent，不写 bridge 文件 ===
    if copy_mode:
        if stage in STOP_STAGES:
            print(f"[runner_step] 当前状态为 {stage}，属于停止态，拒绝复制执行型 prompt。")
            print()
            print(build_stop_message(state, stage))
            return 1
        success = copy_to_clipboard(prompt)
        if success:
            print(f"[runner_step] Prompt 已复制到剪贴板（{len(prompt)} 字符）。")
            print("[runner_step] 可将内容粘贴到 cc-haha 或其他工具中使用。")
        else:
            print("[runner_step] 剪贴板复制失败，请手动复制下方 prompt：")
            print()
            print(prompt)
        return 0 if success else 1

    # 停止态保护（--copy 已前置处理，此处为 --execute / dry-run 做停止态保护）
    if stage in STOP_STAGES:
        print(f"[runner_step] 当前状态为 {stage}，属于停止态，拒绝执行。")
        print(f"[runner_step] 请由人工确认下一步，不要使用 runner_step 自动推进。")
        return 1

    # 确定命令来源和命令
    cmd: str | None = None
    argv: list[str] | None = None
    cmd_source: str

    if stage == "NEED_CLAUDE":
        cmd_source = "env CLAUDE_CODE_CMD"
        cmd = os.environ.get("CLAUDE_CODE_CMD")
        if execute_mode:
            if not cmd:
                print("[runner_step] 错误: CLAUDE_CODE_CMD 环境变量未设置。")
                print("[runner_step] 请设置环境变量后再使用 --execute，例如:")
                print('  export CLAUDE_CODE_CMD="claude"        # Linux/macOS')
                print('  set CLAUDE_CODE_CMD=claude              # Windows cmd')
                print('  $env:CLAUDE_CODE_CMD="claude"           # Windows PowerShell')
                return 1
            try:
                argv = resolve_claude_command(cmd)
            except RunnerCommandError as exc:
                print(f"[runner_step] 错误: {exc}")
                return 1
    elif stage in ("NEED_CODEX_PLAN", "NEED_CODEX_REVIEW"):
        cmd_source = "env CODEX_CMD（未设置，Phase 5 MVP 暂不支持 Codex CLI）"
        if execute_mode:
            print(f"[runner_step] 当前状态 {stage} 在 Phase 5 MVP 中仅支持 dry-run。")
            print("[runner_step] Codex CLI 真实调用将在后续版本支持。")
            print()
            execute_mode = False
        cmd = None
    else:
        cmd_source = "N/A"

    prompt_summary = truncate_prompt(prompt)

    # === Dry-run 模式 ===
    if not execute_mode:
        show_execution_summary(stage, owner, next_actor, cmd_source, cmd, argv, prompt_summary)
        print()
        print("Next Step Suggestion:")
        print(prompt)
        print()
        print("---")
        print("这是 dry-run 模式，未调用任何 CLI。")
        print("使用 --execute 可进入真实执行流程。")
        return 0

    # === 执行模式 ===
    show_execution_summary(stage, owner, next_actor, cmd_source, cmd, argv, prompt_summary)
    print()
    print("即将执行上述 CLI 命令。输入 YES 确认执行，输入其他任意内容取消。")
    confirm = input("> ").strip()
    if confirm != "YES":
        print("[runner_step] 已取消。")
        return 0

    # 执行 CLI（安全参数数组调用，不使用 shell）
    print(f"[runner_step] 正在执行: {argv}")
    print("=" * 62)
    try:
        result = run_claude_cli(argv or [], prompt)
        print("=" * 62)
        if result.returncode == 0:
            print(f"[runner_step] CLI 执行完成 (exit code: {result.returncode})")
        else:
            print(f"[runner_step] CLI 执行异常 (exit code: {result.returncode})")
        return result.returncode
    except subprocess.TimeoutExpired:
        print("[runner_step] 错误: CLI 执行超时（超过 3600 秒）")
        return 1
    except FileNotFoundError as exc:
        prog = argv[0] if argv else "?"
        print(f"[runner_step] 错误: 找不到命令 '{prog}': {exc}")
        return 1
    except OSError as exc:
        print(f"[runner_step] 错误: CLI 执行失败: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
