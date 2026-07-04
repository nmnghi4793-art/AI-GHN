with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'function fetchAll' in line:
        print(f"Line {i+1}: {line.strip()}")
        # print 30 lines after
        start = i
        end = min(len(lines), i + 35)
        for j in range(start, end):
            print(f"  {j+1}: {lines[j].strip()}")
