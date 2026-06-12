#!/usr/bin/env python3
import os, sys

user_home = os.path.expanduser("~")
user_home_backslash = user_home.replace("/", "\\")
user_home_slash = user_home.replace("\\", "/")

# Try multiple path formats
paths = [
    os.path.join(user_home, ".claude", "settings.json"),
    os.path.join(user_home, ".claude", "settings.json"),
    os.path.expanduser("~/.claude/settings.json"),
]

c = None
for p in paths:
    try:
        with open(p, encoding="utf-8") as f:
            c = f.read()
        print(f"Opened: {p}")
        break
    except FileNotFoundError:
        continue

if c is None:
    print("ERROR: Could not open settings.json")
    sys.exit(1)

old = f"{user_home_slash}/.claude/scripts/hooks/"
old_escaped = old.replace("/", "\\")
new = f"{user_home_slash}/.claude/plugins/cache/plc-mcp-kit/plc-mcp-kit/1.0.0/scripts/hooks/"

print(f"old path: {c.count(old)}")
print(f"old escaped: {c.count(old_escaped)}")
print(f"new path: {c.count(new)}")
print(f"ecc refs: {c.count('everything-claude-code')}")
print(f"plc-mcp-kit refs: {c.count('plc-mcp-kit')}")

idx = c.find("scripts/hooks/")
if idx > 0:
    start = max(0, idx - 60)
    print(f"\nSample at {idx}:")
    print(f"...{c[start:idx+60]}...")
