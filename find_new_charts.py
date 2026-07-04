import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'new Chart' in line:
        print(f"Line {i+1}: {line.strip()}")
        # print 2 lines before and 2 lines after
        start = max(0, i - 2)
        end = min(len(lines), i + 3)
        for j in range(start, end):
            prefix = "-> " if j == i else "   "
            print(f"{prefix}{j+1}: {lines[j].strip()}")
        print("-" * 50)
