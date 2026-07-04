with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re
canvas_ids = re.findall(r'<canvas\s+[^>]*id=["\']([^"\']+)["\']', content)
print("CANVAS IDS IN HTML:")
for cid in canvas_ids:
    print(f"  - {cid}")
