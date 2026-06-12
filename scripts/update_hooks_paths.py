#!/usr/bin/env python3
"""Update settings.json hook paths from global dir to plugin cache."""
import re, os

settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")

with open(settings_path, encoding="utf-8") as f:
    content = f.read()

user_home = os.path.expanduser("~").replace("\\", "\\\\")
user_home_normal = os.path.expanduser("~")

# Old paths in settings.json (mixed \\ and /)
old_base_escaped = f"C:\\\\{user_home[2:]}\\.claude/scripts/hooks/"
new_base_escaped = f"C:\\\\{user_home[2:]}\\.claude/plugins/cache/plc-mcp-kit/plc-mcp-kit/1.0.0/scripts/hooks/"

old_base_normal = f"{user_home_normal}/.claude/scripts/hooks/"
new_base_normal = f"{user_home_normal}/.claude/plugins/cache/plc-mcp-kit/plc-mcp-kit/1.0.0/scripts/hooks/"

content = content.replace(old_base_escaped, new_base_escaped)
content = content.replace(old_base_normal, new_base_normal)

# Replace the Stop hook inline JS root-finding logic
plugin_root = f"{user_home}\\\\.claude\\\\plugins\\\\cache\\\\plc-mcp-kit\\\\plc-mcp-kit\\\\1.0.0"

# Pattern: the const root function that scans for ECC
js_pattern = r'const root=\(\(\)=>\{.*?\}\(\).*?const script=path\.join\(root,rel\);'
replacement = f'const root="{plugin_root}";const script=path.join(root,rel);'

content = re.sub(js_pattern, replacement, content, flags=re.DOTALL)

with open(settings_path, "w", encoding="utf-8") as f:
    f.write(content)

# Count remaining old references
count = content.count("everything-claude-code") + content.count(old_base_escaped) + content.count(old_base_normal)
print(f"Updated. Remaining old references: {count}")
if count == 0:
    print("All paths updated!")
else:
    print("Some old references still present")
