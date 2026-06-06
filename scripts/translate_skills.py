#!/usr/bin/env python3
"""Translate SKILL.md descriptions from English to Chinese using Google Translate."""

import re
import sys
import time
import random
from pathlib import Path
from deep_translator import GoogleTranslator

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SKILLS_DIR = Path.home() / ".claude" / "skills"

SKIP_DIRS = {
    "superpowers",
    "document-SKILLs",
    "setup-matt-pocock-skills",
}

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def parse_frontmatter(content):
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}, content
    frontmatter_text = match.group(1)
    rest = content[match.end():]

    frontmatter = {}
    current_key = None
    for line in frontmatter_text.split('\n'):
        kv_match = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', line)
        if kv_match:
            current_key = kv_match.group(1)
            value = kv_match.group(2).strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            frontmatter[current_key] = value
        elif current_key and (line.startswith('  ') or line.startswith('\t')):
            frontmatter[current_key] += ' ' + line.strip()
    return frontmatter, rest

def rebuild_frontmatter(frontmatter, body):
    lines = ['---']
    for key, value in frontmatter.items():
        if ':' in value or value.startswith('"'):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f'{key}: {value}')
    lines.append('---')
    if body:
        lines.append(body)
    return '\n'.join(lines)

def translate_text(text, max_retries=3):
    """Translate text with retry logic, handling long text by chunking."""
    text = text.strip()
    if not text:
        return text

    translator = GoogleTranslator(source='en', target='zh-CN')

    # Split into chunks if too long (Google Translate limit ~5000 chars)
    max_chunk = 4500
    if len(text) > max_chunk:
        chunks = []
        while text:
            chunk = text[:max_chunk]
            # Try to break at a sentence boundary
            last_period = chunk.rfind('. ')
            if last_period > max_chunk // 2:
                chunk = text[:last_period + 1]
            chunks.append(chunk)
            text = text[len(chunk):]
        parts = []
        for chunk in chunks:
            for attempt in range(max_retries):
                try:
                    parts.append(translator.translate(chunk))
                    time.sleep(random.uniform(1, 2))
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(3, 5))
                    else:
                        raise
        return ' '.join(parts)
    else:
        for attempt in range(max_retries):
            try:
                return translator.translate(text)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 5))
                else:
                    raise

def process_skill_dir(skill_dir, label=""):
    """Process a single skill directory. Returns (translated, skipped, error)."""
    name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return (0, 1, 0)

    content = skill_file.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)
    if not frontmatter:
        return (0, 1, 0)

    desc = frontmatter.get('description', '')
    if not desc:
        return (0, 1, 0)

    if has_chinese(desc):
        return (0, 1, 0)

    try:
        translated_desc = translate_text(desc)
        if not translated_desc or translated_desc.strip() == '':
            return (0, 1, 0)

        frontmatter['description'] = translated_desc
        skill_file.write_text(rebuild_frontmatter(frontmatter, body), encoding='utf-8')
        print(f"  OK {label}{name}")
        return (1, 0, 0)
    except Exception as e:
        print(f"  ERR {label}{name}: {e}")
        return (0, 0, 1)

def main():
    translated = 0
    skipped = 0
    errors = 0

    # Process main skill directories
    skill_dirs = sorted([d for d in SKILLS_DIR.iterdir() if d.is_dir()])
    for skill_dir in skill_dirs:
        name = skill_dir.name
        if name in SKIP_DIRS:
            print(f"SKIP {name} (in skip list)")
            skipped += 1
            continue
        t, s, e = process_skill_dir(skill_dir)
        translated += t; skipped += s; errors += e
        time.sleep(random.uniform(0.5, 1.5))

    # Process superpowers sub-skills
    super_skills_dir = SKILLS_DIR / "superpowers" / "skills"
    if super_skills_dir.exists():
        sub_dirs = sorted([d for d in super_skills_dir.iterdir() if d.is_dir()])
        for sub_dir in sub_dirs:
            t, s, e = process_skill_dir(sub_dir, label="superpowers:")
            translated += t; skipped += s; errors += e
            time.sleep(random.uniform(0.5, 1.5))

    # Process frontend-design and ppt-master (they are in special paths)
    # These are likely in the .claude/plugins or skills with nested names
    for special in ["frontend-design", "ppt-master"]:
        d = SKILLS_DIR / special
        if d.exists():
            t, s, e = process_skill_dir(d)
            translated += t; skipped += s; errors += e
            time.sleep(random.uniform(0.5, 1.5))

    # Check for kimi-webbridge which had a long description
    for name in ["kimi-webbridge"]:
        d = SKILLS_DIR / name
        if d.exists():
            t, s, e = process_skill_dir(d)
            translated += t; skipped += s; errors += e
            time.sleep(random.uniform(0.5, 1.5))

    print(f"\n{'='*40}")
    print(f"Total translated: {translated}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
