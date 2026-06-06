#!/usr/bin/env python3
"""Translate remaining English descriptions: plugin commands + superpowers."""
import re, sys, time, random
from pathlib import Path
from translate import Translator

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def parse_frontmatter(content):
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}, content[match.end():] if match else content
    fm = {}
    for line in match.group(1).split('\n'):
        kv = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if kv:
            v = kv.group(2).strip()
            if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                v = v[1:-1]
            fm[kv.group(1)] = v
    return fm, content[match.end():]

def rebuild(fm, body):
    lines = ['---']
    for k, v in fm.items():
        if ':' in v or v.startswith('"') or '#' in v:
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f'{k}: {v}')
    lines.append('---')
    if body:
        lines.append(body)
    return '\n'.join(lines)

def translate(text, retries=5):
    text = text.strip()
    if not text:
        return text
    # Split long text
    if len(text) > 450:
        parts = []
        remaining = text
        while remaining:
            chunk = remaining[:450]
            brk = max(chunk.rfind('. '), chunk.rfind('? '), chunk.rfind('! '))
            if brk > 100:
                parts.append(chunk[:brk+1])
                remaining = remaining[brk+1:]
            else:
                parts.append(remaining[:450])
                remaining = remaining[450:]
        results = []
        for p in parts:
            for i in range(retries):
                try:
                    t = Translator(to_lang="zh", from_lang="en")
                    results.append(t.translate(p))
                    time.sleep(random.uniform(2, 4))
                    break
                except Exception as e:
                    if i == retries - 1:
                        print(f"    FAIL: {e}")
                        results.append(p)
                    time.sleep(random.uniform(5, 8))
        return ' '.join(results)
    else:
        for i in range(retries):
            try:
                t = Translator(to_lang="zh", from_lang="en")
                return t.translate(text)
            except Exception as e:
                if i == retries - 1:
                    print(f"    FAIL: {e}")
                    return text
                time.sleep(random.uniform(5, 8))

def process_file(path, label=""):
    if not path.exists():
        return 0
    content = path.read_text(encoding='utf-8')
    fm, body = parse_frontmatter(content)
    if not fm:
        return 0
    desc = fm.get('description', '')
    if not desc or has_chinese(desc):
        return 0
    td = translate(desc)
    if td and td.strip():
        fm['description'] = td
        path.write_text(rebuild(fm, body), encoding='utf-8')
        print(f"  OK {label}{path.parent.name}")
        return 1
    return 0

total = 0

# 1. plc-mcp-kit plugin commands
PLUGIN = Path.home() / ".claude" / "plugins" / "cache" / "plc-mcp-kit" / "plc-mcp-kit" / "1.0.0"
CMD_DIR = PLUGIN / "commands"
print("=== plc-mcp-kit commands ===")
for f in sorted(CMD_DIR.glob("*.md")):
    if f.is_file():
        total += process_file(f)
    time.sleep(random.uniform(0.5, 1.5))

# 2. superpowers sub-skills
SUPER = Path.home() / ".claude" / "plugins" / "cache" / "claude-plugins-official" / "superpowers" / "5.1.0" / "skills"
print("\n=== superpowers sub-skills ===")
for d in sorted(SUPER.iterdir()):
    if d.is_dir():
        total += process_file(d / "SKILL.md", label="superpowers:")
    time.sleep(random.uniform(0.5, 1.5))

print(f"\nTotal translated: {total}")
