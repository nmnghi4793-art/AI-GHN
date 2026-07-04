with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find all lines containing StaticFiles or Mount or "/app" or index or frontend
lines = content.split('\n')
for i, line in enumerate(lines):
    if any(k in line.lower() for k in ['static', 'mount', 'html', 'css', 'js', 'frontend', 'app.get', 'app.post']):
        print(f"Line {i+1}: {line.strip()}")
