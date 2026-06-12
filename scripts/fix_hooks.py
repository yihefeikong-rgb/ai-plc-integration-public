#!/usr/bin/env python3
"""Fix the corrupted settings.json backup and write a clean version."""
import json, os

user_home = os.path.expanduser("~")
src = os.path.join(user_home, ".claude", "settings.json.invalid-1780573405546-62e4b9")
dst = os.path.join(user_home, ".claude", "settings.json")

with open(src, encoding="utf-8") as f:
    raw = f.read()

# The issue: in inline JS, "root=\"C:\\\\..." breaks JSON because the
# double quote inside the JS closes the JSON string delimiter.

# Fix: replace unescaped double quotes in root path assignments
# Pattern: root="C:\...\" -> root='C:\...'
import re

user_name = os.path.basename(os.path.expanduser("~"))
user_home_slash = os.path.expanduser("~").replace("\\", "/")
plugin_cache = f"{user_home_slash}/.claude/plugins/cache/plc-mcp-kit/plc-mcp-kit/1.0.0/scripts/hooks/"
user_home_backslash_escaped = f"C:\\\\Users\\\\{user_name}"

# Fix both escaped and unescaped versions
raw = raw.replace(f'root="{user_home_backslash_escaped}', f"root='{user_home_backslash_escaped}")
raw = raw.replace('1.0.0";', "1.0.0';")
raw = raw.replace(f'root=\\"{user_home_backslash_escaped}', f"root=\\'{user_home_backslash_escaped}")
raw = raw.replace('1.0.0\\";', "1.0.0\\';")

# Also handle any remaining path issues
old_hooks_path = f"{user_home_slash}/.claude/scripts/hooks/"
raw = raw.replace(old_hooks_path, plugin_cache)

# Validate JSON
try:
    data = json.loads(raw)
    print("JSON is valid!")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Written to {dst}")
    print(f"Total hooks: {sum(len(v) for v in data.get('hooks', {}).values())}")
except json.JSONDecodeError as e:
    print(f"JSON still invalid: {e}")
    print(f"Line {e.lineno}")
    lines = raw.split("\n")
    if e.lineno <= len(lines):
        ln = lines[e.lineno - 1]
        print(f"  {ln[:200]}")
