#!/usr/bin/env python
"""Fix trailing commas that create tuple returns in run_acceptance.py"""
import sys
path = r"D:\claude code xiangmu\AI 接入PLC\mcp-servers\tia-mcp\run_acceptance.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all return LadderBlock patterns and check for trailing comma after closing )
# Fix: replace ']),\n\n\ndef ' with '])\n\n\ndef ' (remove comma that makes it a tuple)
content = content.replace('        ]),\n\n\ndef ', '        ])\n\n\ndef ')

# Also fix the MotorControl one (line ~197)
content = content.replace('        ]),\n\n\ndef build_conveyor_ast', '        ])\n\n\ndef build_conveyor_ast')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed!")
