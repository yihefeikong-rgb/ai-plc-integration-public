#!/usr/bin/env python3
"""Translate remaining English skill descriptions using MyMemory API."""
import re, sys, time, random
from pathlib import Path
from translate import Translator

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SKILLS_DIR = Path.home() / ".claude" / "skills"

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def parse_frontmatter(content):
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}, content
    fm = {}
    for line in match.group(1).split('\n'):
        kv = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if kv:
            v = kv.group(2).strip()
            if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                v = v[1:-1]
            fm[kv.group(1)] = v
    return fm, content[match.end():]

def rebuild_frontmatter(fm, body):
    lines = ['---']
    for k, v in fm.items():
        if ':' in v or v.startswith('"'):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f'{k}: {v}')
    lines.append('---')
    if body:
        lines.append(body)
    return '\n'.join(lines)

def translate(text, retries=5):
    # Split if > 450 chars (MyMemory limit)
    text = text.strip()
    if len(text) > 450:
        # Translate in parts
        parts = []
        remaining = text
        while remaining:
            chunk = remaining[:450]
            # Try to break at a sentence
            if len(remaining) > 450:
                last = max(chunk.rfind('. '), chunk.rfind('? '), chunk.rfind('! '), chunk.rfind(';'))
                if last > 100:
                    chunk = remaining[:last+1]
                    remaining = remaining[last+1:]
                else:
                    remaining = remaining[450:]
            else:
                remaining = ''
            for i in range(retries):
                try:
                    t = Translator(to_lang="zh", from_lang="en")
                    parts.append(t.translate(chunk))
                    time.sleep(random.uniform(2, 4))
                    break
                except Exception as e:
                    if i == retries - 1:
                        raise
                    time.sleep(random.uniform(5, 10))
        return ' '.join(parts)
    else:
        for i in range(retries):
            try:
                t = Translator(to_lang="zh", from_lang="en")
                return t.translate(text)
            except Exception as e:
                if i == retries - 1:
                    raise
                time.sleep(random.uniform(5, 10))

def process(path, label=""):
    if not path.exists():
        print(f"SKIP {label}{path.parent.name} (no SKILL.md)")
        return
    content = path.read_text(encoding='utf-8')
    fm, body = parse_frontmatter(content)
    if not fm:
        return
    desc = fm.get('description', '')
    if not desc or has_chinese(desc):
        print(f"SKIP {label}{path.parent.name} (already CN or no desc)")
        return
    try:
        td = translate(desc)
        if td and td.strip():
            fm['description'] = td
            path.write_text(rebuild_frontmatter(fm, body), encoding='utf-8')
            print(f"OK {label}{path.parent.name}")
        else:
            print(f"WARN {label}{path.parent.name} (empty result)")
    except Exception as e:
        print(f"ERR {label}{path.parent.name}: {e}")
    time.sleep(random.uniform(3, 5))

# Skills still in English
remaining = [
    "latency-critical-systems", "production-audit", "safety-guard",
    "csharp-testing", "dotnet-patterns",
]
print("=== Main skills ===")
for name in remaining:
    process(SKILLS_DIR / name / "SKILL.md")

print("\n=== Special path skills ===")
for name in ["frontend-design", "ppt-master"]:
    d = SKILLS_DIR / name
    if d.exists():
        process(d / "SKILL.md", label=f"{name}:")

print("\n=== Superpowers sub-skills ===")
super_dir = SKILLS_DIR / "superpowers" / "skills"
if super_dir.exists():
    for d in sorted(super_dir.iterdir()):
        if d.is_dir():
            process(d / "SKILL.md", label="superpowers:")

print("\nDone!")
