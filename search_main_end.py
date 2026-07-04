with open('c:/Users/Admin/.gemini/antigravity/scratch/ghn_dashboard/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '</main>' in line:
        print(f"Line {i+1}: {line.strip()}")
        # print 5 lines before and 5 lines after
        start = max(0, i - 5)
        end = min(len(lines), i + 6)
        for j in range(start, end):
            prefix = "-> " if j == i else "   "
            print(f"{prefix}{j+1}: {lines[j].strip()}")
        print("-" * 50)
