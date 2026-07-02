import re

with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
for i, line in enumerate(lines):
    if 'theme' in line.lower() or 'mode' in line.lower() or 'toggle' in line.lower():
        out_lines.append(f"Line {i+1}: {line.strip()}")

with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/scratch/search_results.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))
print(f"Done, found {len(out_lines)} occurrences.")
