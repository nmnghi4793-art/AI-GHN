with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/styles.css', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if any(cls in line for cls in ['btn-mini', 'filter-tabs', 'active']):
        out.append(f"Line {i+1}: {line.strip()}")

with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/scratch/styles_search.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print(f"Found {len(out)} lines.")
