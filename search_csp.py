with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
matches = re.findall(r'(?i)csp|content-security|security|header|middleware', content)
print(f"Matches found: {len(matches)}")
# Let's print any lines containing security/middleware
lines = content.split('\n')
for i, line in enumerate(lines):
    if any(k in line.lower() for k in ['csp', 'content-security', 'security', 'middleware', 'add_middleware']):
        print(f"Line {i+1}: {line.strip()}")
