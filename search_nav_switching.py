with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'data-section' in line or 'nav-item' in line or 'switch' in line:
        if 'function' in line or 'addEventListener' in line or '$' in line or 'document' in line:
            print(f"Line {i+1}: {line.strip()}")
