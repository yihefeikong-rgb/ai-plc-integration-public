"""Fix extra closing parentheses in diagnose_renderer.py"""
with open('diagnose_renderer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line that's just ')\n' or '    )\n' preceded by '    ]),\n'
new_lines = []
for i, line in enumerate(lines):
    stripped = line.rstrip()
    # Skip lone ')' or '    )' that follows '    ]),'
    if stripped == ')' and i > 0 and lines[i-1].rstrip() == '    ]),':
        print(f'Skipping line {i+1}: {repr(line)}')
        continue
    new_lines.append(line)

with open('diagnose_renderer.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Done')
