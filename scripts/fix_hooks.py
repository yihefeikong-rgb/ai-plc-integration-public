#!/usr/bin/env python3
"""Fix the corrupted settings.json backup and write a clean version."""
import json

src = "C:/Users/huangxinyang/.claude/settings.json.invalid-1780573405546-62e4b9"
dst = "C:/Users/huangxinyang/.claude/settings.json"

with open(src, encoding="utf-8") as f:
    raw = f.read()

# The issue: in inline JS, "root=\"C:\\\\..." breaks JSON because the
# double quote inside the JS closes the JSON string delimiter.

# Fix: replace unescaped double quotes in root path assignments
# Pattern: root="C:\...\" -> root='C:\...'
import re

# Fix both escaped and unescaped versions
raw = raw.replace('root="C:\\\\Users', "root='C:\\\\Users")
raw = raw.replace('1.0.0";', "1.0.0';")
raw = raw.replace('root=\\"C:\\\\Users', "root=\\'C:\\\\Users")
raw = raw.replace('1.0.0\\";', "1.0.0\\';")

# Also handle any remaining path issues
raw = raw.replace(
    'C:/Users/huangxinyang/.claude/scripts/hooks/',
    'C:/Users/huangxinyang/.claude/plugins/cache/plc-mcp-kit/plc-mcp-kit/1.0.0/scripts/hooks/'
)

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
