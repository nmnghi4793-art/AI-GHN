with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'id=' in line and 'panel' in line:
        print(f"Line {i+1}: {line.strip()}")
