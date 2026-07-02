with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'function shortKho' in line:
        print(f"Line {i+1}: {line.strip()}")
        # print next 10 lines
        for j in range(1, 12):
            print(f"  {lines[i+j].strip()}")
